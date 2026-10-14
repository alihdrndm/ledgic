"""05 Approval: park on the open money exception until a person decides (rpc_decide_exception)."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from app.repo import exceptions as exc_repo

from ..context import RunRow, StageContext
from ..stages import Stage
from ..transitions import FatalStageError, Transition
from .common import ROLE_LABEL, TYPE_LABEL, money


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    if not run.invoice_id:
        raise FatalStageError("approval without invoice")
    exc = await exc_repo.next_unresolved(ctx.conn, run.invoice_id, exc_repo.MONEY_TYPES + ("posting_failed",))
    if exc is None:
        return Transition.advance(Stage.POSTING, "Approved — no open exception", "continuing to posting")
    role = ROLE_LABEL.get(exc["assigned_role"], exc["assigned_role"])
    return Transition.park(
        str(exc["id"]),
        f"Waiting for {role} — {TYPE_LABEL.get(exc['type'], exc['type']).lower()}",
        f"{money(exc['amount_at_risk'])} at risk · SLA {exc['sla_due_at'].astimezone(ZoneInfo(ctx.policy.get('timezone') or 'America/New_York')):%a %H:%M}",
        detail={
            "exception_type": exc["type"],
            "amount_at_risk": exc["amount_at_risk"],
            "assigned_role": exc["assigned_role"],
        },
    )
