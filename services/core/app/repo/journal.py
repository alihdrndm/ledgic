"""pipeline_events, audit_log and cost_ledger writers (06 §1: every stage writes all three in its txn)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection

from .sql import J


async def emit_event(
    conn: AsyncConnection,
    *,
    org_id: str,
    run_id: str,
    stage: str,
    status: str,
    at: datetime,
    summary: str | None = None,
    sub: str | None = None,
    duration_ms: int | None = None,
    detail: dict[str, Any] | None = None,
) -> int:
    d = dict(detail or {})
    if sub is not None:
        d["sub"] = sub
    cur = await conn.execute(
        "insert into pipeline_events (org_id, run_id, stage, status, at, duration_ms, summary, detail) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s) returning id",
        (org_id, run_id, stage, status, at, duration_ms, summary, J(d)),
    )
    row = await cur.fetchone()
    return int(row["id"])  # type: ignore[index]


async def write_audit(
    conn: AsyncConnection,
    *,
    org_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str | None = None,
    before: Any = None,
    after: Any = None,
    at: datetime | None = None,
) -> None:
    """Append to the hash-chained audit log (the trigger fills prev_hash/hash)."""
    await conn.execute(
        "insert into audit_log (org_id, at, actor_type, actor_id, action, entity_type, entity_id, before, after) "
        "values (%s, coalesce(%s, clock_timestamp()), %s, %s, %s, %s, %s, %s, %s)",
        (
            org_id,
            at,
            actor_type,
            actor_id,
            action,
            entity_type,
            str(entity_id),
            J(before) if before is not None else None,
            J(after) if after is not None else None,
        ),
    )


async def record_cost(
    conn: AsyncConnection,
    *,
    org_id: str,
    run_id: str | None,
    kind: str,
    amount_usd: Decimal,
    at: datetime,
    meta: dict[str, Any] | None = None,
) -> None:
    await conn.execute(
        "insert into cost_ledger (org_id, run_id, kind, amount_usd, meta, at) values (%s, %s, %s, %s, %s, %s)",
        (org_id, run_id, kind, amount_usd, J(meta or {}), at),
    )
