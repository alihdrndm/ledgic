"""Extraction review (01 §3.2): park on an `extraction_review` exception; on confirm, re-score and continue.

`rpc_confirm_fields` writes human field versions (confidence 1.0), sets gate_passed, increments
human_touches and resumes the run; this stage then re-scores (06 §5.4) and moves on to enrichment.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain import doc_confidence
from app.domain.gate import review_callout_title
from app.domain.money import fmt_conf
from app.repo import exceptions as exc_repo
from app.repo import invoices as inv_repo
from app.repo import journal

from ..context import RunRow, StageContext
from ..stages import Stage
from ..transitions import FatalStageError, Transition
from .common import full_name, plural


async def rescore(ctx: StageContext, invoice_id: str) -> Decimal:
    fields = await inv_repo.latest_fields(ctx.conn, invoice_id)
    confs: dict[str, Decimal] = {}
    for k in ("vendor_name", "invoice_number", "invoice_date", "total", "po_reference", "terms"):
        f = fields.get(k)
        if f and f["value"] is not None:
            confs[k] = Decimal(f["confidence"])
    for ln in await inv_repo.lines(ctx.conn, invoice_id):
        c = ln.get("confidences") or {}
        for part in ("qty", "unit_price", "amount"):
            if ln.get(part) is not None:
                confs[f"lines[{ln['line_no'] - 1}].{part}"] = Decimal(str(c.get(part, 0)))
    return doc_confidence(confs)


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    if not run.invoice_id:
        raise FatalStageError("review without invoice")
    if ctx.decision and ctx.decision.get("action") == "confirm_fields":
        dc = await rescore(ctx, run.invoice_id)
        who = await full_name(ctx.conn, ctx.decision.get("actor_id")) or "a reviewer"
        await journal.write_audit(
            ctx.conn,
            org_id=run.org_id,
            actor_type="core",
            actor_id="orchestrator",
            action="invoice.rescored",
            entity_type="invoice",
            entity_id=run.invoice_id,
            after={"doc_confidence": dc, "gate_passed": True},
            at=ctx.now(),
        )
        return Transition.advance(
            Stage.ENRICHMENT,
            f"Re-scored — conf {fmt_conf(dc)} after review",
            f"confirmed by {who}",
            detail={"doc_confidence": dc, "rescored": True, "actor_id": ctx.decision.get("actor_id")},
        )

    flagged = list(run.context.get("flagged") or [])
    reason = run.context.get("review_reason") or (
        review_callout_title(flagged)
        if flagged
        else "Document confidence below the gate — confirm the fields"
    )
    inv = await inv_repo.get_invoice(ctx.conn, run.invoice_id)
    exc_id = await exc_repo.create_exception(
        ctx.conn,
        org_id=run.org_id,
        invoice_id=run.invoice_id,
        run_id=run.id,
        type="extraction_review",
        reason=reason,
        amount_at_risk=Decimal(0),
        assigned_role="ap_clerk",
        opened_at=ctx.now(),
        sla_hours=int(ctx.policy["sla_hours"]),
    )
    await journal.write_audit(
        ctx.conn,
        org_id=run.org_id,
        actor_type="core",
        actor_id="orchestrator",
        action="exception.opened",
        entity_type="exception",
        entity_id=exc_id,
        after={"type": "extraction_review", "reason": reason, "invoice_id": run.invoice_id},
        at=ctx.now(),
    )
    sub = (
        f"{plural(len(flagged), 'field')} flagged · routed to extraction review"
        if flagged
        else "routed to extraction review"
    )
    return Transition.park(
        exc_id,
        f"Below gate — {reason[0].lower() + reason[1:]}"
        if not reason.startswith("AI")
        else f"Below gate — {reason}",
        sub,
        detail={
            "exception_type": "extraction_review",
            "flagged_fields": flagged,
            "doc_confidence": inv["doc_confidence"] if inv else None,
        },
    )
