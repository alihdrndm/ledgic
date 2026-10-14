"""Per-step context handed to stage handlers: connection, clock, run, options, caches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg import AsyncConnection


class Clock:
    """Real time by default. The backfill/catch-up driver uses a virtual clock so history gets
    realistic timestamps (events, approvals, postings land at the time they 'happened')."""

    def __init__(self, start: datetime | None = None) -> None:
        self._virtual = start

    @property
    def virtual(self) -> bool:
        return self._virtual is not None

    def now(self) -> datetime:
        return self._virtual if self._virtual is not None else datetime.now(UTC)

    def advance(self, delta: timedelta) -> None:
        if self._virtual is not None:
            self._virtual = self._virtual + delta

    def set(self, at: datetime) -> None:
        if self._virtual is not None:
            self._virtual = at


@dataclass
class Options:
    fast: bool = False  # no sleeps (mock ERP latency), no background drafts
    drafts: bool = True  # enqueue resolution-agent drafts for money exceptions
    erp_latency: bool = True
    owner: str = "core"
    hold_lease: bool = False  # sync driver keeps a 'sync' lease between steps
    version: str = "v1"


@dataclass
class RunRow:
    id: str
    run_number: int
    org_id: str
    document_id: str
    invoice_id: str | None
    status: str
    current_stage: str
    next_stage: str | None
    attempt: int
    context: dict[str, Any]
    wait_exception_id: str | None
    started_at: datetime
    workflow_version: str

    @classmethod
    def of(cls, row: dict[str, Any]) -> RunRow:
        return cls(
            id=str(row["id"]),
            run_number=int(row["run_number"]),
            org_id=str(row["org_id"]),
            document_id=str(row["document_id"]),
            invoice_id=str(row["invoice_id"]) if row.get("invoice_id") else None,
            status=row["status"],
            current_stage=row["current_stage"],
            next_stage=row.get("next_stage"),
            attempt=int(row.get("attempt") or 0),
            context=dict(row.get("context") or {}),
            wait_exception_id=str(row["wait_exception_id"]) if row.get("wait_exception_id") else None,
            started_at=row["started_at"],
            workflow_version=row.get("workflow_version") or "v1",
        )


@dataclass
class StageContext:
    conn: AsyncConnection
    clock: Clock
    options: Options
    policy: dict[str, Any]
    decision: dict[str, Any] | None = None  # the decision that resumed this step, if any
    byok_key: str | None = None  # X-OpenAI-Key passed at ingest (memory only)
    after_commit: list[Callable[[], Any]] = field(default_factory=list)

    def now(self) -> datetime:
        return self.clock.now()
