"""Deterministic parser for extracted invoice payment terms.

Extraction captures `terms` as free text ("2/10 net 30"). This module turns the
common real-world formats into structured values so early-payment discounts can
be computed and surfaced downstream. No LLM, Decimal only, and it never raises:
unparseable text returns None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaymentTerms:
    discount_pct: Decimal | None  # ratio: Decimal("0.02") means a 2% discount
    discount_days: int | None  # pay within this many days to earn the discount
    net_days: int | None  # full amount due within this many days; 0 = on receipt


# "2/10 net 30" — discount pct / discount days, then the net period.
_SLASH = re.compile(
    r"^(?P<pct>\d+(?:\.\d+)?)\s*/\s*(?P<discount_days>\d+)\s*,?\s*net\s*(?P<net_days>\d+)(?:\s*days)?$"
)
# "2% 10 Net 30" — the same terms with an explicit percent sign.
_PERCENT = re.compile(
    r"^(?P<pct>\d+(?:\.\d+)?)\s*%\s*,?\s*(?P<discount_days>\d+)\s*,?\s*net\s*(?P<net_days>\d+)(?:\s*days)?$"
)
# "Net 14" — no discount, just a net period.
_NET_ONLY = re.compile(r"^net\s*(?P<net_days>\d+)(?:\s*days)?$")
# Due immediately.
_ON_RECEIPT = frozenset({"due on receipt", "cod", "cash on delivery", "payable on receipt"})


def parse_payment_terms(text: str | None) -> PaymentTerms | None:
    """Parse free-text payment terms, or return None when they don't parse.

    Accepts "2/10 net 30", "2% 10 Net 30", "Net 14" and "Due on receipt"
    (case-insensitive, tolerant of extra spaces and a trailing "days").
    Anything else — including a bare "2/10" with no net period — returns None
    rather than guessing.
    """
    if not text:
        return None
    normalised = " ".join(text.split()).strip().lower()
    if not normalised:
        return None
    if normalised in _ON_RECEIPT:
        return PaymentTerms(discount_pct=None, discount_days=None, net_days=0)
    match = _NET_ONLY.match(normalised)
    if match:
        return PaymentTerms(discount_pct=None, discount_days=None, net_days=int(match["net_days"]))
    for pattern in (_SLASH, _PERCENT):
        match = pattern.match(normalised)
        if match:
            return PaymentTerms(
                discount_pct=Decimal(match["pct"]) / 100,
                discount_days=int(match["discount_days"]),
                net_days=int(match["net_days"]),
            )
    return None
