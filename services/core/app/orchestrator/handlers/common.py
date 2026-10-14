"""Shared helpers for stage handlers: parsing, copy text (Run inspector lines), small lookups."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from psycopg import AsyncConnection

from app.domain import fmt_money
from app.repo.sql import val

_INVOICE_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://ledgic.dev/invoice")

ROLE_LABEL = {
    "ap_clerk": "AP clerk",
    "ap_manager": "AP manager",
    "controller": "controller",
    "admin": "admin",
    "viewer": "viewer",
}
TYPE_LABEL = {
    "extraction_review": "Below gate",
    "price_variance": "Price variance",
    "qty_mismatch": "Quantity mismatch",
    "no_po": "No PO found",
    "unmatched_line": "Unmatched line",
    "duplicate": "Suspected duplicate",
    "new_vendor_screen": "New vendor screen",
    "posting_failed": "Posting failed",
}
ACTION_LABEL = {
    "confirm_fields": "Fields confirmed",
    "short_pay": "Short-paid",
    "approve_as_is": "Approved as-is",
    "approve_without_po": "Approved without PO",
    "dispute": "Disputed",
    "link_po": "PO linked",
    "merge": "Merged",
    "reject_copy": "Copy rejected",
    "not_duplicate": "Marked not a duplicate",
    "request_w9": "W-9 requested",
    "release_hold": "Hold released",
    "reject_invoice": "Rejected",
    "retry_posting": "Posting retried",
}


def invoice_id_for(document_id: str) -> str:
    """Stable invoice id per document (one document → one invoice; re-extraction reuses it)."""
    return str(uuid.uuid5(_INVOICE_NS, str(document_id)))


def dec(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return v
    try:
        s = str(v).replace(",", "").replace("$", "").strip()
        return Decimal(s) if s else None
    except (InvalidOperation, ValueError):
        return None


def to_date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


def channel_label(channel: str, mime: str | None) -> str:
    if channel == "email":
        return "email PDF" if (mime or "").endswith("pdf") else "email image"
    if channel == "photo":
        return "dock photo"
    if channel == "portal":
        return "portal PDF"
    if channel == "edi":
        return "EDI 810"
    return "upload PDF" if (mime or "").endswith("pdf") else "upload photo"


def money(v: Any) -> str:
    d = dec(v)
    return fmt_money(d) if d is not None else "—"


async def full_name(conn: AsyncConnection, user_id: str | None) -> str | None:
    if not user_id:
        return None
    return await val(conn, "select full_name from profiles where user_id = %s", (user_id,))
