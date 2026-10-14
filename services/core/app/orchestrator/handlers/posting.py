"""06 Posting (06 §9): create the ERP bill via the entity's adapter (mock QuickBooks / NetSuite).

Short-pays post the expected amounts (contract/PO price or received qty) and carry the hold in the memo.
Failures retry with backoff (10/30/60/120/300 s); after 5 attempts a `posting_failed` exception is
opened and the run parks until someone retries or rejects (01 §3.8). Duplicate copies never post.

Failure injection (tests/demos): `pipeline_runs.context.inject.posting_failures = N` makes the mock
fail while the invoice has fewer than N posting attempts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain import cents, fmt_money
from app.posting import BillLine, BillRequest, PostingRefused, adapter_for
from app.repo import exceptions as exc_repo
from app.repo import invoices as inv_repo
from app.repo import journal
from app.repo.sql import all_

from ..context import RunRow, StageContext
from ..routing import payment_terms
from ..stages import Stage
from ..transitions import FatalStageError, Transition
from .common import ROLE_LABEL, dec

ZERO = Decimal(0)


def payable_lines(
    lines: list[dict[str, Any]], match_rows: dict[str, dict[str, Any]], hold: Decimal
) -> list[Decimal]:
    """Per-line payable amounts. With a hold, failing lines pay their expected amount (price) or the
    received quantity (qty); any rounding remainder lands on the largest failing line."""
    amounts = [dec(ln["amount"]) or ZERO for ln in lines]
    if hold <= 0:
        return amounts
    target = sum(amounts, ZERO) - hold
    failing: list[int] = []
    for i, ln in enumerate(lines):
        mr = match_rows.get(ln["sid"])
        if not mr or mr["verdict"] in ("matched", "favorable"):
            continue
        failing.append(i)
        if mr["verdict"] == "price_variance" and mr["expected_amount"] is not None:
            amounts[i] = min(amounts[i], dec(mr["expected_amount"]) or amounts[i])
        elif (
            mr["verdict"] in ("qty_over_receipt", "qty_over_order")
            and mr["grn_qty"] is not None
            and ln["unit_price"] is not None
        ):
            amounts[i] = min(amounts[i], cents(dec(mr["grn_qty"]) * dec(ln["unit_price"])))
        elif mr["verdict"] == "unmatched_line":
            amounts[i] = ZERO
    diff = target - sum(amounts, ZERO)
    if diff != 0:
        idx = max(failing or range(len(amounts)), key=lambda i: amounts[i])
        amounts[idx] = cents(amounts[idx] + diff)
    return amounts


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    conn = ctx.conn
    if not run.invoice_id:
        raise FatalStageError("posting without invoice")
    inv = await inv_repo.get_invoice(conn, run.invoice_id)
    assert inv is not None
    if inv["status"] in ("duplicate", "rejected") or inv["duplicate_of"]:
        return Transition.advance(
            Stage.CLOSE, "Posting blocked — invoice is not payable", f"status {inv['status']}"
        )

    system = inv["entity_erp"] if inv["entity_erp"] in ("quickbooks", "netsuite") else "quickbooks"
    adapter = adapter_for(
        system, latency=ctx.options.erp_latency and not ctx.options.fast and not ctx.clock.virtual
    )
    total = dec(inv["total"]) or ZERO
    pay_s, hold_s = payment_terms(list(run.context.get("decisions") or []))
    hold = cents(Decimal(hold_s)) if hold_s else ZERO
    pay = cents(Decimal(pay_s)) if pay_s else total
    lines = await inv_repo.lines(conn, run.invoice_id)
    match_rows = await inv_repo.match_hold_by_line(conn, run.invoice_id)
    amounts = payable_lines(lines, match_rows, hold)
    gls = {
        str(r["id"]): r
        for r in await all_(conn, "select id, number, name from gl_accounts where org_id = %s", (run.org_id,))
    }
    bill_lines = tuple(
        BillLine(
            ln["line_no"],
            ln["description"],
            dec(ln["qty"]),
            dec(ln["unit_price"]),
            amt,
            gls.get(str(ln["gl_account_id"]), {}).get("number"),
            gls.get(str(ln["gl_account_id"]), {}).get("name"),
        )
        for ln, amt in zip(lines, amounts, strict=True)
    )
    memo = f"Ledgic invoice {run.invoice_id}"
    if hold > 0:
        memo += f" · short-paid, {fmt_money(hold)} held per vendor notice"
    req = BillRequest(
        invoice_id=run.invoice_id,
        posting_key=f"ledgic-{run.invoice_id}",
        vendor_id=str(inv["vendor_id"]) if inv["vendor_id"] else None,
        vendor_name=inv["vendor_name"],
        entity_short_code=inv["entity_short_code"],
        entity_ref=None,
        location_code=inv["location_code"],
        invoice_number=inv["invoice_number"],
        invoice_date=inv["invoice_date"],
        due_date=inv["due_date"],
        lines=bill_lines,
        pay_amount=pay,
        hold_amount=hold,
        memo=memo,
        duplicate_of=str(inv["duplicate_of"]) if inv["duplicate_of"] else None,
    )
    existing = await exc_repo.posting_row(conn, run.invoice_id, system)
    prior_attempts = int(existing["attempts"]) if existing else 0
    inject = int((run.context.get("inject") or {}).get("posting_failures") or 0)
    try:
        res = await adapter.create_bill(req, fail=prior_attempts < inject)
    except PostingRefused as e:
        return Transition.advance(Stage.CLOSE, "Posting blocked — duplicate copy", str(e))
    now = ctx.now()
    if existing and existing["status"] == "posted":  # idempotent re-post
        res_ok_ext = existing["external_id"]
    else:
        res_ok_ext = None
    await inv_repo.update_invoice(conn, run.invoice_id, status="posting")
    await exc_repo.upsert_posting(
        conn,
        org_id=run.org_id,
        invoice_id=run.invoice_id,
        system=system,
        status="posted" if res.ok else "failed",
        request=req.as_json(system),
        response=res.response,
        external_id=res.external_id or res_ok_ext,
        error=res.error,
        posted_at=now if res.ok else None,
    )
    if not res.ok:
        return Transition.retry(
            res.error or "ERP error",
            duration_ms=res.latency_ms,
            detail={"system": system, "latency_ms": res.latency_ms},
        )

    await inv_repo.update_invoice(conn, run.invoice_id, status="posted", posted_at=now)
    await journal.write_audit(
        conn,
        org_id=run.org_id,
        actor_type="core",
        actor_id="posting",
        action="invoice.posted",
        entity_type="invoice",
        entity_id=run.invoice_id,
        after={
            "system": system,
            "external_id": res.external_id,
            "pay_amount": pay,
            "hold_amount": hold,
            "mock": True,
        },
        at=now,
    )
    label = "QuickBooks" if system == "quickbooks" else "NetSuite"
    gl_counts: dict[str, int] = {}
    for bl in bill_lines:
        if bl.gl_number:
            k = f"{bl.gl_number} {bl.gl_name}"
            gl_counts[k] = gl_counts.get(k, 0) + 1
    gl = max(gl_counts, key=gl_counts.get) if gl_counts else "uncoded"
    sub = f"{inv['entity_name'] or 'no entity'} · loc {inv['location_code'] or '—'} · GL {gl}"
    if hold > 0:
        sub += f" · held {fmt_money(hold)}"
    return Transition.advance(
        Stage.CLOSE,
        f"Posted — {label}, {res.display_ref}",
        sub,
        detail={
            "system": system,
            "external_id": res.external_id,
            "pay_amount": pay,
            "hold_amount": hold,
            "mock": True,
            "latency_ms": res.latency_ms,
        },
        duration_ms=res.latency_ms,
    )


async def exhausted(ctx: StageContext, run: RunRow, error: str) -> Transition:
    """After 5 failed attempts: open a posting_failed exception and park (manager can retry)."""
    assert run.invoice_id
    inv = await inv_repo.get_invoice(ctx.conn, run.invoice_id)
    assert inv is not None
    system = inv["entity_erp"] if inv["entity_erp"] in ("quickbooks", "netsuite") else "quickbooks"
    label = "QuickBooks" if system == "quickbooks" else "NetSuite"
    pay_s, _ = payment_terms(list(run.context.get("decisions") or []))
    at_risk = cents(Decimal(pay_s)) if pay_s else (dec(inv["total"]) or ZERO)
    now = ctx.now()
    exc_id = await exc_repo.create_exception(
        ctx.conn,
        org_id=run.org_id,
        invoice_id=run.invoice_id,
        run_id=run.id,
        type="posting_failed",
        reason=f"{label} rejected the bill — {error}"[:300],
        amount_at_risk=at_risk,
        assigned_role="ap_manager",
        opened_at=now,
        sla_hours=int(ctx.policy["sla_hours"]),
    )
    await journal.write_audit(
        ctx.conn,
        org_id=run.org_id,
        actor_type="core",
        actor_id="posting",
        action="exception.opened",
        entity_type="exception",
        entity_id=exc_id,
        after={"type": "posting_failed", "system": system, "error": error},
        at=now,
    )
    return Transition.park(
        exc_id,
        f"Posting failed — {label} unavailable",
        f"{fmt_money(at_risk)} not posted · routed to {ROLE_LABEL['ap_manager']}",
        detail={"exception_type": "posting_failed", "system": system, "error": error},
    )
