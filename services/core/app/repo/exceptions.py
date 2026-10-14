"""exceptions + recommendations + erp_postings."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection

from .sql import J, all_, one

MONEY_TYPES = ("price_variance", "qty_mismatch", "no_po", "unmatched_line")
HOLD_TYPES = ("duplicate", "new_vendor_screen")
UNRESOLVED = ("open", "escalated", "disputed", "awaiting_vendor")


async def create_exception(
    conn: AsyncConnection,
    *,
    org_id: str,
    invoice_id: str,
    run_id: str | None,
    type: str,
    reason: str,
    amount_at_risk: Decimal,
    assigned_role: str,
    opened_at: datetime,
    sla_hours: int,
) -> str:
    """Idempotent per (invoice, type): an unresolved exception of the same type is reused."""
    existing = await one(
        conn,
        "select id::text as id from exceptions where invoice_id = %s and type = %s and status <> 'resolved' "
        "order by opened_at desc limit 1",
        (invoice_id, type),
    )
    if existing:
        return existing["id"]
    row = await one(
        conn,
        "insert into exceptions (org_id, invoice_id, run_id, type, status, amount_at_risk, reason, assigned_role, "
        " opened_at, sla_due_at) values (%s, %s, %s, %s, 'open', %s, %s, %s, %s, %s) returning id::text as id",
        (
            org_id,
            invoice_id,
            run_id,
            type,
            amount_at_risk,
            reason,
            assigned_role,
            opened_at,
            opened_at + timedelta(hours=sla_hours),
        ),
    )
    assert row is not None
    return row["id"]


async def upsert_recommendation(
    conn: AsyncConnection,
    *,
    exception_id: str,
    action: str,
    pay_amount: Decimal | None,
    hold_amount: Decimal | None,
    confidence: Decimal,
    reasons: list[dict[str, Any]],
) -> None:
    await conn.execute(
        "insert into recommendations (exception_id, action, pay_amount, hold_amount, confidence, reasons) "
        "values (%s, %s, %s, %s, %s, %s) on conflict (exception_id) do update set action = excluded.action, "
        " pay_amount = excluded.pay_amount, hold_amount = excluded.hold_amount, confidence = excluded.confidence, "
        " reasons = excluded.reasons",
        (exception_id, action, pay_amount, hold_amount, confidence, J(reasons)),
    )


async def get_exception(conn: AsyncConnection, exception_id: str) -> dict[str, Any] | None:
    return await one(conn, "select * from exceptions where id = %s", (exception_id,))


async def next_unresolved(
    conn: AsyncConnection, invoice_id: str, types: tuple[str, ...]
) -> dict[str, Any] | None:
    return await one(
        conn,
        "select * from exceptions where invoice_id = %s and type = any(%s) and status = any(%s) "
        "order by case type when 'duplicate' then 0 when 'new_vendor_screen' then 1 else 2 end, opened_at limit 1",
        (invoice_id, list(types), list(UNRESOLVED)),
    )


async def invoice_exceptions(conn: AsyncConnection, invoice_id: str) -> list[dict[str, Any]]:
    return await all_(
        conn, "select * from exceptions where invoice_id = %s order by opened_at", (invoice_id,)
    )


# ------------------------------------------------------------------------------------------- postings


async def posting_row(conn: AsyncConnection, invoice_id: str, system: str) -> dict[str, Any] | None:
    return await one(
        conn, "select * from erp_postings where invoice_id = %s and system = %s", (invoice_id, system)
    )


async def upsert_posting(
    conn: AsyncConnection,
    *,
    org_id: str,
    invoice_id: str,
    system: str,
    status: str,
    request: dict[str, Any],
    response: dict[str, Any] | None,
    external_id: str | None,
    error: str | None,
    posted_at: datetime | None,
) -> int:
    row = await one(
        conn,
        "insert into erp_postings (org_id, invoice_id, system, status, external_id, request, response, attempts, posted_at, error) "
        "values (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s) on conflict (invoice_id, system) do update set "
        " status = excluded.status, external_id = coalesce(excluded.external_id, erp_postings.external_id), "
        " request = excluded.request, response = excluded.response, attempts = erp_postings.attempts + 1, "
        " posted_at = coalesce(excluded.posted_at, erp_postings.posted_at), error = excluded.error "
        "returning attempts",
        (
            org_id,
            invoice_id,
            system,
            status,
            external_id,
            J(request),
            J(response) if response is not None else None,
            posted_at,
            error,
        ),
    )
    assert row is not None
    return int(row["attempts"])
