"""Worker loop: claim runnable runs (FOR UPDATE SKIP LOCKED + 60 s lease), step them, repeat.

Wakeups come from `LISTEN ledgic_runs` (RPC decisions, ingest, wake endpoint all `pg_notify`), with a
2 s poll as fallback (and for retries whose `next_attempt_at` comes due).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any

from psycopg import AsyncConnection

from app.config import get_settings
from app.db.pool import connection
from app.repo import runs as runs_repo

from .context import Clock
from .engine import Engine, run_after_commit

log = logging.getLogger("ledgic.worker")


class Worker:
    def __init__(
        self, engine: Engine, *, concurrency: int = 3, poll_seconds: float = 2.0, lease_seconds: int = 60
    ) -> None:
        self.engine = engine
        self.concurrency = concurrency
        self.poll_seconds = poll_seconds
        self.lease_seconds = lease_seconds
        self.owner = f"{socket.gethostname()}:{os.getpid()}"
        self.last_tick_at: datetime | None = None
        self.steps = 0
        self._wake = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._running = False

    @property
    def alive(self) -> bool:
        if not self._running or not self._tasks or all(t.done() for t in self._tasks):
            return False
        return self.last_tick_at is not None and (
            datetime.now(UTC) - self.last_tick_at
        ).total_seconds() < max(30, self.poll_seconds * 10)

    def wake(self) -> None:
        self._wake.set()

    async def start(self) -> None:
        self._running = True
        self._tasks = [asyncio.create_task(self._listen(), name="ledgic-listen")]
        self._tasks += [
            asyncio.create_task(self._loop(i), name=f"ledgic-worker-{i}") for i in range(self.concurrency)
        ]
        log.info("worker %s started (%d loops)", self.owner, self.concurrency)

    async def stop(self) -> None:
        self._running = False
        self._wake.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def _listen(self) -> None:
        delay = 1.0
        while self._running:
            try:
                conn = await AsyncConnection.connect(get_settings().database_url, autocommit=True)
                async with conn:
                    await conn.execute(f"listen {runs_repo.NOTIFY_CHANNEL}")
                    delay = 1.0
                    async for _ in conn.notifies():
                        self._wake.set()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("LISTEN connection lost (%s); retrying in %.0fs", e, delay)
                await asyncio.sleep(delay)
                delay = min(30.0, delay * 2)

    async def _loop(self, i: int) -> None:
        while self._running:
            self.last_tick_at = datetime.now(UTC)
            try:
                did = await self.tick_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("worker loop %d error", i)
                did = False
            if not did:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=self.poll_seconds)
                except TimeoutError:
                    pass
                self._wake.clear()

    async def tick_once(self) -> bool:
        """Claim and step one run. Returns False when nothing was runnable."""
        clock = Clock()
        callbacks: list[Any] = []
        failed: BaseException | None = None
        run_id: str | None = None
        async with connection() as conn:
            try:
                async with conn.transaction():
                    row = await runs_repo.claim_next(conn, self.owner, self.lease_seconds)
                    if row is None:
                        return False
                    run_id = str(row["id"])
                    res = await self.engine.step(conn, row, clock)
                    callbacks = res.after_commit
            except Exception as e:
                failed = e
            if failed is not None and run_id is not None:
                log.warning("run %s failed a step: %s", run_id, failed)
                async with conn.transaction():
                    await self.engine.record_failure(conn, run_id, failed, clock)
            elif failed is not None:
                raise failed
        self.steps += 1
        await run_after_commit(callbacks)
        return True
