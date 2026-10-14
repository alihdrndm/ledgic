"""03b Screening (01 §4.4–4.5, 06 §7): duplicate similarity + new-vendor/bank fraud screen.

Holds create payment-blocking exceptions (duplicate → AP manager; new_vendor_screen → controller) and
the run parks on the first one. After a decision (release_hold / not_duplicate / merge-kept) the run
re-enters this stage in resume mode and parks on the next open hold, or continues to match.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.domain import DupInvoice, DupLine, FraudInputs, best_match, fmt_money, fraud_screen
from app.repo import exceptions as exc_repo
from app.repo import invoices as inv_repo
from app.repo import journal, master
from app.repo.sql import all_

from ..context import RunRow, StageContext
from ..stages import Stage
from ..transitions import FatalStageError, Transition
from .common import ROLE_LABEL, dec

REMIT_NEW_DAYS = 30


def _norm_addr(s: Any) -> str:
    if isinstance(s, dict):
        s = " ".join(str(v) for k, v in s.items() if k not in ("name",) and v)
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def remit_is_new(vendor: dict[str, Any], invoice_address: str | None, at: datetime) -> bool:
    """Remit-to recently created/changed on the vendor record, or the invoice remits somewhere the
    vendor record does not know."""
    changed = vendor.get("remit_address_changed_at") or vendor.get("created_at")
    if changed is not None and at - changed < timedelta(days=REMIT_NEW_DAYS):
        return True
    known = _norm_addr(vendor.get("remit_address"))
    got = _norm_addr(invoice_address)
    return bool(known and got and got not in known and known not in got)


async def _dup_lines(ctx: StageContext, invoice_ids: list[str]) -> dict[str, tuple[DupLine, ...]]:
    if not invoice_ids:
        return {}
    rows = await all_(
        ctx.conn,
        "select invoice_id::text as invoice_id, description, qty, amount from invoice_lines where invoice_id = any(%s) order by line_no",
        (invoice_ids,),
    )
    out: dict[str, list[DupLine]] = {}
    for r in rows:
        if r["qty"] is None or r["amount"] is None:
            continue
        out.setdefault(r["invoice_id"], []).append(DupLine(r["description"], r["qty"], r["amount"]))
    return {k: tuple(v) for k, v in out.items()}


def _same_hero_other_day(a_meta: dict[str, Any], b_meta: dict[str, Any]) -> bool:
    """Hero invoices replay with stable numbers every demo day; yesterday's copy is not a duplicate."""
    return (
        bool(a_meta.get("hero"))
        and a_meta.get("hero") == b_meta.get("hero")
        and a_meta.get("demo_day") != b_meta.get("demo_day")
    )


async def _park_next(ctx: StageContext, run: RunRow, summary_prefix: str = "Held") -> Transition | None:
    nxt = await exc_repo.next_unresolved(ctx.conn, run.invoice_id or "", exc_repo.HOLD_TYPES)
    if nxt is None:
        return None
    label = "suspected duplicate" if nxt["type"] == "duplicate" else "new vendor screen"
    return Transition.park(
        str(nxt["id"]),
        f"{summary_prefix} — {label}, payment blocked",
        f"{nxt['reason']} · routed to {ROLE_LABEL.get(nxt['assigned_role'], nxt['assigned_role'])}",
        detail={"exception_type": nxt["type"], "amount_at_risk": nxt["amount_at_risk"]},
    )


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    conn = ctx.conn
    if not run.invoice_id:
        raise FatalStageError("screening without invoice")
    if run.context.get("screened"):  # resume after a hold decision
        parked = await _park_next(ctx, run)
        if parked:
            return parked
        return Transition.advance(Stage.MATCH, "Screening cleared — hold released", "continuing to match")

    inv = await inv_repo.get_invoice(conn, run.invoice_id)
    assert inv is not None
    now = ctx.now()
    pol = ctx.policy
    meta = inv.get("source_meta") or {}
    total = dec(inv["total"]) or Decimal(0)
    detail: dict[str, Any] = {}
    exceptions: list[str] = []

    # ---- duplicates
    dup_sim = None
    if inv["vendor_id"]:
        cands = await inv_repo.duplicate_candidates(
            conn,
            org_id=run.org_id,
            vendor_id=str(inv["vendor_id"]),
            invoice_id=run.invoice_id,
            number=inv["invoice_number"],
            total=inv["total"],
            invoice_date=inv["invoice_date"],
            at=inv["received_at"],
        )
        cands = [c for c in cands if not _same_hero_other_day(meta, c.get("source_meta") or {})]
        lines_by = await _dup_lines(ctx, [run.invoice_id, *[c["id"] for c in cands]])
        me = DupInvoice(
            str(inv["vendor_id"]),
            inv["invoice_number"] or "",
            total,
            inv["invoice_date"] or now.date(),
            lines_by.get(run.invoice_id, ()),
            inv["sha256"],
            inv["phash"],
        )
        others = [
            DupInvoice(
                c["vendor_id"],
                c["invoice_number"] or "",
                dec(c["total"]) or Decimal(0),
                c["invoice_date"] or now.date(),
                lines_by.get(c["id"], ()),
                c["sha256"],
                c["phash"],
            )
            for c in cands
        ]
        best = best_match(me, others) if others else None
        if best is not None:
            cand_inv, score = best
            cand = cands[others.index(cand_inv)]
            dup_sim = score.similarity
            detail["duplicate"] = {
                "candidate_invoice_id": cand["id"],
                "similarity": score.similarity,
                "hard": score.hard,
            }
            if score.similarity >= Decimal(pol["dup_suggest_threshold"]):
                evidence = {
                    **score.evidence,
                    "candidate_invoice_id": cand["id"],
                    "weighted_score": score.weighted_score,
                    "components": score.components,
                    "hard": score.hard,
                }
                await inv_repo.insert_duplicate_candidate(
                    conn,
                    org_id=run.org_id,
                    invoice_id=run.invoice_id,
                    candidate_id=cand["id"],
                    similarity=score.similarity,
                    evidence=evidence,
                    at=now,
                )
            if score.similarity >= Decimal(pol["dup_hold_threshold"]):
                when = cand["received_at"].astimezone(_tz(pol)).strftime("%H:%M")
                reason = f"Same invoice as {cand['invoice_number']} received {when} by {cand['channel']}"
                exc_id = await exc_repo.create_exception(
                    conn,
                    org_id=run.org_id,
                    invoice_id=run.invoice_id,
                    run_id=run.id,
                    type="duplicate",
                    reason=reason,
                    amount_at_risk=total,
                    assigned_role="ap_manager",
                    opened_at=now,
                    sla_hours=int(pol["sla_hours"]),
                )
                exceptions.append(exc_id)
                await journal.write_audit(
                    conn,
                    org_id=run.org_id,
                    actor_type="core",
                    actor_id="screening",
                    action="exception.opened",
                    entity_type="exception",
                    entity_id=exc_id,
                    after={
                        "type": "duplicate",
                        "similarity": score.similarity,
                        "candidate_invoice_id": cand["id"],
                        "amount_at_risk": total,
                    },
                    at=now,
                )

    # ---- fraud screen
    vendor = await master.get_vendor(conn, str(inv["vendor_id"])) if inv["vendor_id"] else None
    fraud_score = Decimal(0)
    if vendor is not None:
        fields = await inv_repo.latest_fields(conn, run.invoice_id)
        addr = (fields.get("remit_to_address") or {}).get("value")
        tz = _tz(pol)  # calendar days in the org timezone ("vendor record 4 days old")
        age = max(
            0, (inv["received_at"].astimezone(tz).date() - vendor["created_at"].astimezone(tz).date()).days
        )
        history = await master.vendor_history_totals(
            conn, run.org_id, str(vendor["id"]), inv["received_at"], run.invoice_id
        )
        fr = fraud_screen(
            FraudInputs(
                amount=total,
                vendor_age_days=age,
                has_po=inv["po_id"] is not None,
                invoice_bank_fingerprint=run.context.get("bank_fp"),
                w9_bank_fingerprint=vendor.get("w9_bank_fingerprint"),
                remit_address_new=remit_is_new(vendor, addr, inv["received_at"]),
                history=tuple(history),
            )
        )
        fraud_score = fr.score
        detail["fraud"] = {"score": fr.score, "signals": [s.signal for s in fr.signals]}
        if fr.signals:
            await inv_repo.replace_fraud_signals(
                conn,
                org_id=run.org_id,
                invoice_id=run.invoice_id,
                vendor_id=str(vendor["id"]),
                signals=[
                    {"signal": s.signal, "weight": s.weight, "detail": {"label": s.label, **s.detail}}
                    for s in fr.signals
                ],
                at=now,
            )
        if fr.score >= Decimal(pol["fraud_hold_threshold"]):
            reason = " · ".join(s.label for s in fr.signals[:2])
            exc_id = await exc_repo.create_exception(
                conn,
                org_id=run.org_id,
                invoice_id=run.invoice_id,
                run_id=run.id,
                type="new_vendor_screen",
                reason=reason,
                amount_at_risk=total,
                assigned_role="controller",
                opened_at=now,
                sla_hours=int(pol["sla_hours"]),
            )
            exceptions.append(exc_id)
            await journal.write_audit(
                conn,
                org_id=run.org_id,
                actor_type="core",
                actor_id="screening",
                action="exception.opened",
                entity_type="exception",
                entity_id=exc_id,
                after={
                    "type": "new_vendor_screen",
                    "signal_score": fr.score,
                    "signals": [s.signal for s in fr.signals],
                    "amount_at_risk": total,
                },
                at=now,
            )

    await inv_repo.update_invoice(conn, run.invoice_id, status="screened")
    tr: Transition | None = None
    if exceptions:
        tr = await _park_next(ctx, run)
    if tr is None:
        dup_txt = (
            "no duplicate"
            if dup_sim is None or dup_sim < Decimal(pol["dup_suggest_threshold"])
            else f"possible duplicate {dup_sim:.2f} (below hold)"
        )
        fraud_txt = "no fraud signal" if fraud_score == 0 else f"signal score {fraud_score:.2f}"
        tr = Transition.advance(
            Stage.MATCH, f"Screened — {dup_txt}, {fraud_txt}", "duplicate and new-vendor checks passed"
        )
    tr.context["screened"] = True
    tr.detail.update(detail)
    tr.detail["held"] = bool(exceptions)
    if exceptions:
        tr.detail["held_amount"] = fmt_money(total)
    return tr


def _tz(pol: dict[str, Any]):
    from zoneinfo import ZoneInfo

    return ZoneInfo(pol.get("timezone") or "America/New_York")
