"""Reason-bullet templates for recommendations (06 §8). Deterministic text filled from facts only."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .money import fmt_money, fmt_qty, fmt_unit_price

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
NO_RECOMMENDATION = "No recommendation — decide manually"


@dataclass(frozen=True)
class ReasonBullet:
    template_id: str
    text: str
    facts: dict[str, str] = field(default_factory=dict, hash=False)

    def as_json(self) -> dict[str, object]:
        """Shape stored in recommendations.reasons: {template_id, text, facts}."""
        return {"template_id": self.template_id, "text": self.text, "facts": dict(self.facts)}


def _per_uom(price: Decimal, uom: str | None) -> str:
    return f"{fmt_unit_price(price)}/{uom}" if uom else fmt_unit_price(price)


def through_text(effective_to: date | None, reference: date | None) -> str:
    """'through September' (same year as reference) / 'through March 2027' / 'with no end date'."""
    if effective_to is None:
        return "with no end date"
    month = MONTHS[effective_to.month - 1]
    if reference is not None and reference.year != effective_to.year:
        return f"through {month} {effective_to.year}"
    return f"through {month}"


def contract_price_bullet(
    contract_unit: Decimal,
    uom: str | None,
    effective_to: date | None,
    invoice_unit: Decimal,
    reference_date: date | None,
) -> ReasonBullet:
    text = (
        f"The agreement on file fixes this item at {_per_uom(contract_unit, uom)} "
        f"{through_text(effective_to, reference_date)}; the invoice bills {fmt_unit_price(invoice_unit)}."
    )
    return ReasonBullet(
        "contract_price",
        text,
        {
            "contract_unit": str(contract_unit),
            "uom": uom or "",
            "invoice_unit": str(invoice_unit),
            "effective_to": effective_to.isoformat() if effective_to else "",
        },
    )


def po_price_bullet(po_unit: Decimal, uom: str | None, invoice_unit: Decimal) -> ReasonBullet:
    text = (
        f"The purchase order prices this item at {_per_uom(po_unit, uom)}; "
        f"the invoice bills {fmt_unit_price(invoice_unit)}."
    )
    return ReasonBullet(
        "po_price", text, {"po_unit": str(po_unit), "uom": uom or "", "invoice_unit": str(invoice_unit)}
    )


def no_contract_bullet() -> ReasonBullet:
    return ReasonBullet(
        "no_contract", "There is no contract price on file, so the purchase order price is the reference."
    )


def _join(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def prior_short_pays_bullet(prior: Sequence[Decimal]) -> ReasonBullet | None:
    """Omitted for zero prior; singular for one; 'twice' / 'N times' otherwise."""
    n = len(prior)
    if n == 0:
        return None
    amounts = _join([fmt_money(p) for p in prior])
    if n == 1:
        text = f"The same variance appeared once this quarter ({amounts}). It was short-paid and accepted."
    elif n == 2:
        text = (
            f"The same variance appeared twice this quarter ({amounts}). "
            "Both were short-paid and both were accepted."
        )
    else:
        text = (
            f"The same variance appeared {n} times this quarter ({amounts}). "
            "All were short-paid and all were accepted."
        )
    return ReasonBullet(
        "prior_short_pays", text, {"count": str(n), "amounts": ",".join(str(p) for p in prior)}
    )


def grn_full_bullet() -> ReasonBullet:
    return ReasonBullet(
        "grn_full", "Goods were received in full, so there is no quantity basis to dispute — only price."
    )


def vendor_notice_bullet(clause_ref: str | None) -> ReasonBullet:
    if clause_ref:
        return ReasonBullet(
            "vendor_notice",
            "A vendor notice is drafted with the clause reference attached.",
            {"clause_ref": clause_ref},
        )
    return ReasonBullet(
        "vendor_notice", "A vendor notice is drafted with the purchase order reference attached."
    )


def received_short_bullet(received: Decimal, invoiced: Decimal) -> ReasonBullet:
    text = f"The goods receipt shows {fmt_qty(received)} received against {fmt_qty(invoiced)} invoiced."
    return ReasonBullet("received_short", text, {"received": str(received), "invoiced": str(invoiced)})


def pay_received_bullet() -> ReasonBullet:
    return ReasonBullet(
        "pay_received", "Short-pay covers what was received; the vendor can bill the balance on delivery."
    )


def no_po_bullet() -> ReasonBullet:
    return ReasonBullet("no_po", "No purchase order is referenced on the invoice.")


def po_candidate_bullet(po_number: str, score: Decimal) -> ReasonBullet:
    text = f"{po_number} is an open purchase order for this vendor and amount (match score {score:.2f})."
    return ReasonBullet("po_candidate", text, {"po_number": po_number, "score": str(score)})


def no_po_candidate_bullet() -> ReasonBullet:
    return ReasonBullet("no_po_candidate", "No open purchase order matches this vendor and amount.")


def approve_without_po_bullet() -> ReasonBullet:
    return ReasonBullet("approve_without_po", "Approving without a PO needs an AP manager and a comment.")
