"""07 Close: touchless / human touches / final status; the run succeeds."""

from __future__ import annotations

from app.repo import invoices as inv_repo
from app.repo import journal

from ..context import RunRow, StageContext
from ..transitions import Transition
from .common import plural


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    if not run.invoice_id:
        return Transition.finish("Closed — no invoice", run_status="cancelled")
    inv = await inv_repo.get_invoice(ctx.conn, run.invoice_id)
    assert inv is not None
    now = ctx.now()
    touches = int(inv["human_touches"] or 0)
    status = inv["status"]
    if status == "posted":
        touchless = touches == 0
        summary = (
            "Closed — touchless"
            if touchless
            else f"Closed — {plural(touches, 'human touch', 'human touches')}"
        )
        sub = "received → posted with no human action" if touchless else "posted after review"
    else:
        touchless = False
        if status not in ("duplicate", "rejected"):
            # merge/reject decisions set the status in the RPC; anything else reaching close is rejected
            await inv_repo.update_invoice(ctx.conn, run.invoice_id, status="rejected")
            status = "rejected"
        summary = "Closed — duplicate copy, never paid" if status == "duplicate" else "Closed — rejected"
        sub = f"{plural(touches, 'human touch', 'human touches')} · payment blocked"
    await inv_repo.update_invoice(ctx.conn, run.invoice_id, touchless=touchless)
    await journal.write_audit(
        ctx.conn,
        org_id=run.org_id,
        actor_type="core",
        actor_id="orchestrator",
        action="run.closed",
        entity_type="pipeline_run",
        entity_id=run.id,
        after={
            "invoice_id": run.invoice_id,
            "invoice_status": status,
            "touchless": touchless,
            "human_touches": touches,
        },
        at=now,
    )
    return Transition.finish(
        summary, sub, detail={"touchless": touchless, "human_touches": touches, "invoice_status": status}
    )
