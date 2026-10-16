"""Scheduled jobs. Only the leader (session advisory lock) runs them, so a second replica is harmless.

| job                | when                         | what |
|--------------------|------------------------------|------|
| replay_tick        | every 5 min (REPLAY_ENABLED) | release due demo documents, simulated decisions |
| sla_escalation     | every 15 min                 | open exceptions past `sla_due_at` → escalated, controller |
| nightly            | 03:00 America/New_York       | auto-resolve stale, reset earlier heroes, purge > 30 d, drop files > 7 d |
| refresh_kpis       | every minute if no pg_cron   | `select refresh_kpis()` |
| release_stale_llm  | every 5 min if no pg_cron    | `select llm_budget_release_stale()` |
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from psycopg import AsyncConnection

from app.config import get_settings
from app.db.pool import connection
from app.repo import journal
from app.repo.sql import all_, exists_fn, val

log = logging.getLogger("ledgic.scheduler")
LEADER_KEY = 0x1ED61C  # pg_try_advisory_lock key


async def escalate_due(now: datetime | None = None) -> int:
    """01 §3.9: open exceptions untouched past their SLA → escalated, assigned to controller."""
    now = now or datetime.now(UTC)
    async with connection() as conn, conn.transaction():
        rows = await all_(
            conn,
            "update exceptions set escalated = true, assigned_role = 'controller' "
            "where status in ('open') and not escalated and sla_due_at < %s and first_viewed_at is null "
            "returning id::text as id, org_id::text as org_id, type::text as type, amount_at_risk",
            (now,),
        )
        for r in rows:
            await journal.write_audit(
                conn,
                org_id=r["org_id"],
                actor_type="system",
                actor_id="sla",
                action="exception.escalated",
                entity_type="exception",
                entity_id=r["id"],
                after={"assigned_role": "controller", "reason": "SLA passed"},
            )
    return len(rows)


class Scheduler:
    def __init__(self, *, on_live_docs: Callable[[], None] | None = None) -> None:
        self.settings = get_settings()
        self.sched = AsyncIOScheduler(timezone="UTC")
        self.leader_conn: AsyncConnection | None = None
        self.is_leader = False
        self.on_live_docs = on_live_docs
        self.last_runs: dict[str, Any] = {}
        self.pg_cron = False

    async def _acquire_leader(self) -> bool:
        if self.is_leader:
            return True
        try:
            if self.leader_conn is None or self.leader_conn.closed:
                self.leader_conn = await AsyncConnection.connect(self.settings.database_url, autocommit=True)
            cur = await self.leader_conn.execute("select pg_try_advisory_lock(%s) as ok", (LEADER_KEY,))
            row = await cur.fetchone()
            self.is_leader = bool(row and row[0])
        except Exception as e:
            log.warning("leader election failed: %s", e)
            self.is_leader = False
            self.leader_conn = None
        return self.is_leader

    def _job(self, name: str, fn: Callable[[], Any]) -> Callable[[], Any]:
        async def run() -> None:
            if not await self._acquire_leader():
                return
            try:
                res = await fn()
                self.last_runs[name] = {"at": datetime.now(UTC).isoformat(), "result": res}
            except Exception as e:
                log.exception("job %s failed", name)
                self.last_runs[name] = {"at": datetime.now(UTC).isoformat(), "error": str(e)}

        return run

    async def _replay(self) -> Any:
        from app.demo import replay

        if not await replay.demo_org_exists():
            return "no demo org"
        if replay.reset_in_progress():
            return "demo reset in progress"
        stats = await replay.tick(
            on_live=self.on_live_docs, version=self.settings.orchestrator_version, respect_reset=True
        )
        return {"dropped": len(stats.dropped), "decided": stats.decided}

    async def _nightly(self) -> Any:
        from app.demo import replay

        if not await replay.demo_org_exists():
            return "no demo org"
        stats = await replay.nightly()
        try:  # suggested answers that are missing (first night after a deploy or reset); ~$0 once warm
            from app.ai import copilot

            stats = {**stats, "copilot_cache": await copilot.warm_cache(replay.ORG_ID)}
        except Exception:
            log.exception("nightly: copilot cache warm failed")
        return stats

    async def _refresh(self) -> Any:
        async with connection() as conn:
            if await exists_fn(conn, "refresh_kpis"):
                await conn.execute("select public.refresh_kpis()")
                return "ok"
        return "missing"

    async def _release_stale(self) -> Any:
        async with connection() as conn:
            if await exists_fn(conn, "llm_budget_release_stale"):
                return await val(conn, "select public.llm_budget_release_stale() as n")
        return None

    async def start(self) -> None:
        async with connection() as conn:
            self.pg_cron = bool(
                await val(conn, "select exists(select 1 from pg_extension where extname = 'pg_cron') as e")
            )
        s = self.sched
        if self.settings.replay_enabled:
            s.add_job(
                self._job("replay_tick", self._replay),
                "interval",
                minutes=5,
                id="replay_tick",
                next_run_time=datetime.now(UTC),
                max_instances=1,
                coalesce=True,
            )
        s.add_job(
            self._job("sla_escalation", escalate_due),
            "interval",
            minutes=15,
            id="sla_escalation",
            max_instances=1,
            coalesce=True,
        )
        if self.settings.replay_enabled:
            s.add_job(
                self._job("nightly", self._nightly),
                "cron",
                hour=3,
                minute=0,
                timezone="America/New_York",
                id="nightly",
                max_instances=1,
                coalesce=True,
            )
        if not self.pg_cron:
            s.add_job(
                self._job("refresh_kpis", self._refresh),
                "interval",
                minutes=1,
                id="refresh_kpis",
                max_instances=1,
                coalesce=True,
            )
            s.add_job(
                self._job("release_stale_llm", self._release_stale),
                "interval",
                minutes=5,
                id="release_stale_llm",
                max_instances=1,
                coalesce=True,
            )
        s.start()
        log.info("scheduler started (replay=%s, pg_cron=%s)", self.settings.replay_enabled, self.pg_cron)

    async def stop(self) -> None:
        if self.sched.running:
            self.sched.shutdown(wait=False)
        if self.leader_conn is not None and not self.leader_conn.closed:
            await self.leader_conn.close()
        self.is_leader = False
