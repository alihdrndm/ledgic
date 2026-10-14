"""documents + pipeline_runs: creation, claiming (FOR UPDATE SKIP LOCKED + lease), updates, dead letters."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import AsyncConnection

from .sql import J, all_, one

NOTIFY_CHANNEL = "ledgic_runs"


async def find_document_by_sha(conn: AsyncConnection, org_id: str, sha256: str) -> dict[str, Any] | None:
    return await one(conn, "select * from documents where org_id = %s and sha256 = %s", (org_id, sha256))


async def get_document(conn: AsyncConnection, document_id: str) -> dict[str, Any] | None:
    return await one(conn, "select * from documents where id = %s", (document_id,))


async def insert_document(
    conn: AsyncConnection,
    *,
    org_id: str,
    channel: str,
    storage_path: str,
    sha256: str,
    mime: str,
    received_at: datetime,
    page_count: int | None = None,
    phash: str | None = None,
    original_filename: str | None = None,
    source_meta: dict[str, Any] | None = None,
    preprocessing: dict[str, Any] | None = None,
    document_id: str | None = None,
) -> dict[str, Any] | None:
    """Insert a document; returns None when the same sha256 already exists in the org (re-delivery)."""
    return await one(
        conn,
        "insert into documents (id, org_id, channel, storage_path, sha256, mime, page_count, phash, "
        " original_filename, source_meta, preprocessing, received_at) "
        "values (coalesce(%s::uuid, gen_random_uuid()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "on conflict do nothing returning *",
        (
            document_id,
            org_id,
            channel,
            storage_path,
            sha256,
            mime,
            page_count,
            phash,
            original_filename,
            J(source_meta or {}),
            J(preprocessing) if preprocessing is not None else None,
            received_at,
        ),
    )


async def create_run(
    conn: AsyncConnection,
    *,
    org_id: str,
    document_id: str,
    started_at: datetime,
    context: dict[str, Any] | None = None,
    workflow_version: str = "v1",
    lease_owner: str | None = None,
    lease_until: datetime | None = None,
    notify: bool = True,
) -> dict[str, Any]:
    run = await one(
        conn,
        "insert into pipeline_runs (org_id, document_id, workflow_version, status, current_stage, next_stage, "
        " attempt, next_attempt_at, context, started_at, lease_owner, lease_until) "
        "values (%s, %s, %s, 'running', 'intake', 'intake', 0, %s, %s, %s, %s, %s) returning *",
        (
            org_id,
            document_id,
            workflow_version,
            started_at,
            J(context or {}),
            started_at,
            lease_owner,
            lease_until,
        ),
    )
    assert run is not None
    if notify:
        await notify_run(conn, str(run["id"]))
    return run


async def notify_run(conn: AsyncConnection, run_id: str) -> None:
    await conn.execute("select pg_notify(%s, %s)", (NOTIFY_CHANNEL, run_id))


async def claim_next(conn: AsyncConnection, owner: str, lease_seconds: int = 60) -> dict[str, Any] | None:
    """Claim one runnable run (running, due, lease free). The row lock is held until the txn ends."""
    return await one(
        conn,
        "update pipeline_runs r set lease_owner = %s, lease_until = now() + make_interval(secs => %s) "
        "where r.id = (select id from pipeline_runs "
        "  where status = 'running' and next_attempt_at <= now() "
        "    and (lease_until is null or lease_until < now()) "
        "  order by next_attempt_at limit 1 for update skip locked) "
        "returning r.*",
        (owner, lease_seconds),
    )


async def lock_run(conn: AsyncConnection, run_id: str, *, skip_locked: bool = False) -> dict[str, Any] | None:
    return await one(
        conn,
        "select * from pipeline_runs where id = %s for update" + (" skip locked" if skip_locked else ""),
        (run_id,),
    )


async def get_run(conn: AsyncConnection, run_id: str) -> dict[str, Any] | None:
    return await one(conn, "select * from pipeline_runs where id = %s", (run_id,))


async def latest_run_for_document(conn: AsyncConnection, document_id: str) -> dict[str, Any] | None:
    return await one(
        conn,
        "select * from pipeline_runs where document_id = %s order by started_at desc limit 1",
        (document_id,),
    )


_RUN_COLUMNS = {
    "status",
    "current_stage",
    "next_stage",
    "attempt",
    "next_attempt_at",
    "lease_owner",
    "lease_until",
    "wait_exception_id",
    "context",
    "last_error",
    "finished_at",
    "invoice_id",
    "orchestrator_version",
}


async def update_run(conn: AsyncConnection, run_id: str, **fields: Any) -> None:
    bad = set(fields) - _RUN_COLUMNS
    if bad:
        raise ValueError(f"unknown run columns: {bad}")
    if not fields:
        return
    cols = list(fields)
    params = [J(fields[c]) if c == "context" else fields[c] for c in cols]
    sets = ", ".join(f"{c} = %s" for c in cols)
    await conn.execute(f"update pipeline_runs set {sets} where id = %s", (*params, run_id))


async def insert_dead_letter(
    conn: AsyncConnection, *, org_id: str, run_id: str, stage: str, error: str, payload: dict[str, Any]
) -> None:
    await conn.execute(
        "insert into dead_letters (org_id, run_id, stage, error, payload) values (%s, %s, %s, %s, %s)",
        (org_id, run_id, stage, error, J(payload)),
    )


async def run_events(conn: AsyncConnection, run_id: str) -> list[dict[str, Any]]:
    """Timeline rows; prefers B's v_run_timeline view, falls back to the raw table."""
    try:
        async with conn.transaction():
            return await all_(
                conn, "select * from v_run_timeline where run_id = %s order by at, event_id", (run_id,)
            )
    except Exception:  # view not there yet (B's migrations)
        return await all_(
            conn,
            "select org_id, run_id, id as event_id, at, stage, status, duration_ms, summary, detail "
            "from pipeline_events where run_id = %s order by at, id",
            (run_id,),
        )
