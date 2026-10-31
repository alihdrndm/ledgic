"""06 Posting (06 §9): create the ERP bill via the entity's adapter (mock QuickBooks / NetSuite).

Short-pays post the expected amounts (contract/PO price or received qty) and carry the hold in the memo.
Failures retry with backoff (10/30/60/120/300 s); after 5 attempts a `posting_failed` exception is
opened and the run parks until someone retries or rejects (01 §3.8). Duplicate copies never post.

Failure injection (tests/demos): `pipeline_runs.context.inject.posting_failures = N` makes the mock
fail while the invoice has fewer than N posting attempts.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.domain import cents, fmt_money
from app.domain.gate import TOTAL_TOLERANCE
from app.posting import (
    BillLine,
    BillRequest,
    PostingRefused,
    PostingValidationError,
    adapter_for,
)
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

# QBO and NetSuite require an account on every expense line. Purchase-side sales tax is part of the
# cost of what was bought, so it is allocated across the goods lines (each keeps its own GL) rather
# than posted to Sales Tax Payable (2200): debiting that liability would understate what the
# business owes the state. Freight and the rounding remainder get their own lines when the chart has
# the account, and otherwise fold into the largest goods line so charts seeded before those accounts
# existed keep posting.
DEFAULT_FREIGHT_GL = "6300"  # Freight In
DEFAULT_ROUNDING_GL = "9999"  # Rounding
# The gate lets lines + tax + freight sit up to 0.02 off the total and a short-pay 0.01 more; any
# bigger remainder is a data problem, not rounding.
MAX_ROUNDING = TOTAL_TOLERANCE + Decimal("0.01")


def _allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` pro rata across `weights`, in cents. The rounding remainder lands on the
    largest weight, so the shares always sum to `total` exactly."""
    shares = [ZERO for _ in weights]
    denom = sum(weights, ZERO)
    if total == 0 or denom == 0:
        return shares
    shares = [cents(total * w / denom) for w in weights]
    idx = max(range(len(weights)), key=lambda i: weights[i])
    shares[idx] = cents(shares[idx] + total - sum(shares, ZERO))
    return shares


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


def bill_lines(
    lines: list[dict[str, Any]],
    match_rows: dict[str, dict[str, Any]],
    hold: Decimal,
    tax: Decimal,
    freight: Decimal,
    gls: dict[str, dict[str, Any]],
    pay: Decimal,
) -> tuple[BillLine, ...]:
    """The bill's lines: the invoice's goods lines (short-paid per hold, with purchase tax allocated
    across them), then freight and the rounding remainder — as their own coded lines when the chart
    has the account, folded into the largest goods line when it does not.

    The ERP checks `TotalAmt` (= pay) against the sum of the line amounts, so the invariant here is
    Σ amounts = pay. The gate guarantees lines + tax + freight = total, but a confirmed total can
    drift by up to the gate tolerance and a short-pay by a cent more; that remainder lands on a
    rounding line (or the largest line), and anything larger is refused before posting."""
    goods_total = sum((dec(ln["amount"]) or ZERO for ln in lines), ZERO)
    if hold > goods_total:
        raise PostingValidationError(
            f"a {fmt_money(hold)} hold exceeds the goods lines ({fmt_money(goods_total)})"
        )
    amounts = payable_lines(lines, match_rows, hold)
    if any(amount < 0 for amount in amounts):
        raise PostingValidationError("the short-pay allocation drives a line below zero")
    out = [
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
    ]
    chart = {str(row["number"]): row for row in gls.values()}

    def fold(label: str, amount: Decimal) -> None:
        """Put `amount` on the largest line, which keeps that line's own GL account."""
        if not out:
            raise PostingValidationError(f"the invoice has {label.lower()} but no goods line to carry it")
        idx = max(range(len(out)), key=lambda i: out[i].amount)
        out[idx] = replace(out[idx], amount=cents(out[idx].amount + amount))

    def coded(label: str, gl_number: str, amount: Decimal) -> BillLine:
        account = chart[gl_number]
        line_no = max((bl.line_no for bl in out), default=0) + 1
        return BillLine(line_no, label, None, None, amount, account["number"], account["name"])

    if tax:
        # Pro rata by payable amount, so a short-paid line carries less tax. Fall back to the
        # invoice amounts when every line is held in full, and to the largest line when even those
        # are zero.
        weights = [bl.amount for bl in out]
        if sum(weights, ZERO) == 0:
            weights = [dec(ln["amount"]) or ZERO for ln in lines]
        if sum(weights, ZERO) == 0:
            fold("sales tax", tax)
        else:
            for i, share in enumerate(_allocate(tax, weights)):
                if share:
                    out[i] = replace(out[i], amount=cents(out[i].amount + share))
    if freight:
        if DEFAULT_FREIGHT_GL in chart:
            out.append(coded("Freight", DEFAULT_FREIGHT_GL, freight))
        else:
            fold("freight", freight)
    remainder = cents(pay - sum((bl.amount for bl in out), ZERO))
    if remainder:
        if abs(remainder) > MAX_ROUNDING:
            lines_sum = sum((bl.amount for bl in out), ZERO)
            raise PostingValidationError(
                f"the bill lines sum to {fmt_money(lines_sum)} but the bill total is {fmt_money(pay)}"
            )
        if DEFAULT_ROUNDING_GL in chart:
            out.append(coded("Rounding", DEFAULT_ROUNDING_GL, remainder))
        else:
            fold("rounding", remainder)
    return tuple(out)


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
    gls = {
        str(r["id"]): r
        for r in await all_(conn, "select id, number, name from gl_accounts where org_id = %s", (run.org_id,))
    }
    existing = await exc_repo.posting_row(conn, run.invoice_id, system)
    prior_attempts = int(existing["attempts"]) if existing else 0
    label = "QuickBooks" if system == "quickbooks" else "NetSuite"
    try:
        bill_lines_ = bill_lines(
            lines,
            match_rows,
            hold,
            cents(dec(inv["tax"]) or ZERO),
            cents(dec(inv["freight"]) or ZERO),
            gls,
            pay,
        )
    except PostingValidationError as e:
        await journal.emit_event(
            conn,
            org_id=run.org_id,
            run_id=run.id,
            stage=Stage.POSTING.value,
            status="failed",
            at=ctx.now(),
            summary=f"Posting rejected — {label} cannot accept the bill",
            sub=str(e)[:200],
            detail={
                "system": system,
                "attempt": prior_attempts + 1,
                "error": str(e),
                "retryable": False,
            },
        )
        return await exhausted(ctx, run, str(e), summary=f"Posting rejected — {label} validation error")
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
        lines=bill_lines_,
        pay_amount=pay,
        hold_amount=hold,
        memo=memo,
        duplicate_of=str(inv["duplicate_of"]) if inv["duplicate_of"] else None,
    )
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
        if not res.retryable:  # a validation-type rejection: retrying it five times cannot help
            err = res.error or "ERP error"
            await journal.emit_event(
                conn,
                org_id=run.org_id,
                run_id=run.id,
                stage=Stage.POSTING.value,
                status="failed",
                at=now,
                duration_ms=res.latency_ms,
                summary=f"Posting rejected — {label} validation error",
                sub=err[:200],
                detail={
                    "system": system,
                    "attempt": prior_attempts + 1,
                    "error": err,
                    "retryable": False,
                },
            )
            return await exhausted(ctx, run, err, summary=f"Posting rejected — {label} validation error")
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
    gl_counts: dict[str, int] = {}
    for bl in bill_lines_:
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


async def exhausted(ctx: StageContext, run: RunRow, error: str, *, summary: str | None = None) -> Transition:
    """Open a posting_failed exception and park (manager can retry): after 5 failed attempts, or
    straight away when the ERP rejects the bill as invalid."""
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
        summary or f"Posting failed — {label} unavailable",
        f"{fmt_money(at_risk)} not posted · routed to {ROLE_LABEL['ap_manager']}",
        detail={"exception_type": "posting_failed", "system": system, "error": error},
    )
