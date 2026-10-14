"""Price tolerance (01 §4.1): ±pct or abs, whichever is lower."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .money import D, Numberish, cents, fmt_money, fmt_money_short, fmt_pct, fmt_pct_limit, quantize

DEFAULT_PCT = Decimal("0.02")
DEFAULT_ABS = Decimal("25.00")


@dataclass(frozen=True)
class ToleranceResult:
    expected_unit: Decimal
    qty: Decimal
    amount: Decimal
    expected_ext: Decimal
    delta: Decimal
    allowed: Decimal  # min(pct×expected_ext, abs), rounded to cents for display/storage
    delta_pct: Decimal | None  # ratio, 5 dp (numeric(8,5)); None when expected_ext is 0
    passes: bool
    favorable: bool  # delta < 0 (always passes)
    exceeds_pct: bool  # |delta| > pct×expected_ext
    exceeds_abs: bool  # |delta| > abs
    pct_limit: Decimal
    abs_limit: Decimal

    @property
    def delta_pct_display(self) -> str:
        return fmt_pct(self.delta_pct) if self.delta_pct is not None else "n/a"


def line_tolerance(
    expected_unit: Numberish,
    qty: Numberish,
    amount: Numberish,
    pct: Numberish = DEFAULT_PCT,
    abs_amount: Numberish = DEFAULT_ABS,
) -> ToleranceResult:
    """Canonical check. `passes` compares against the exact min(pct×expected_ext, abs);
    `allowed` is that value rounded to cents for display/storage."""
    eu, q, amt, p, a = D(expected_unit), D(qty), D(amount), D(pct), D(abs_amount)
    expected_ext = cents(eu * q)
    delta = amt - expected_ext
    pct_allowed = p * expected_ext
    allowed_exact = min(pct_allowed, a)
    favorable = delta < 0
    passes = favorable or abs(delta) <= allowed_exact
    delta_pct = quantize(delta / expected_ext, 5) if expected_ext != 0 else None
    return ToleranceResult(
        expected_unit=eu,
        qty=q,
        amount=amt,
        expected_ext=expected_ext,
        delta=delta,
        allowed=cents(allowed_exact),
        delta_pct=delta_pct,
        passes=passes,
        favorable=favorable,
        exceeds_pct=abs(delta) > pct_allowed,
        exceeds_abs=abs(delta) > a,
        pct_limit=p,
        abs_limit=a,
    )


def tolerance_sentence(line_no: int, r: ToleranceResult) -> str:
    """'Line 1 is +12.0% against a ±2% limit and $88.00 against a $25 limit — it fails both, so the
    invoice holds for approval.' When only one limit is exceeded the sentence names it."""
    head = (
        f"Line {line_no} is {r.delta_pct_display} against a ±{fmt_pct_limit(r.pct_limit)} limit and "
        f"{fmt_money(r.delta)} against a {fmt_money_short(r.abs_limit)} limit"
    )
    if r.passes:
        if r.favorable and (r.exceeds_pct or r.exceeds_abs):
            return f"{head} — it is under the expected amount, so it passes as favorable."
        return f"{head} — it is within tolerance."
    if r.exceeds_pct and r.exceeds_abs:
        which = "it fails both"
    elif r.exceeds_pct:
        which = f"it fails the ±{fmt_pct_limit(r.pct_limit)} limit"
    else:
        which = f"it fails the {fmt_money_short(r.abs_limit)} limit"
    return f"{head} — {which}, so the invoice holds for approval."
