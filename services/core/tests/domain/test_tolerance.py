from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.domain.tolerance import line_tolerance, tolerance_sentence


def test_hero_shrimp_fails(heroes: dict) -> None:
    exp = heroes["PS-88214"]["expected"]
    r = line_tolerance("3.68", "200", "824.00")
    assert r.expected_ext == Decimal(exp["expected_ext"])
    assert r.amount == Decimal(exp["invoice_ext"])
    assert r.delta == Decimal(exp["delta"])
    assert r.allowed == Decimal(exp["allowed"])
    assert r.delta_pct == Decimal("0.11957")
    assert r.delta_pct_display == exp["delta_pct_display"] == "+12.0%"
    assert not r.passes and not r.favorable
    assert r.exceeds_pct and r.exceeds_abs
    assert tolerance_sentence(1, r) == (
        "Line 1 is +12.0% against a ±2% limit and $88.00 against a $25 limit — it fails both, "
        "so the invoice holds for approval."
    )


def test_exactly_two_percent_passes() -> None:
    # expected 500.00, 2% = 10.00 < 25 → allowed 10.00
    assert line_tolerance("5.00", "100", "510.00").passes
    assert not line_tolerance("5.00", "100", "510.01").passes


def test_exactly_25_dollars_passes() -> None:
    # expected 2000.00, 2% = 40 > 25 → allowed 25.00 (min selects abs)
    r = line_tolerance("20.00", "100", "2025.00")
    assert r.allowed == Decimal("25.00") and r.passes
    r2 = line_tolerance("20.00", "100", "2025.01")
    assert not r2.passes
    assert tolerance_sentence(3, r2).endswith("it fails the $25 limit, so the invoice holds for approval.")


def test_min_selects_pct_when_lower() -> None:
    r = line_tolerance("10.00", "10", "103.00")  # exp 100, 2% = 2.00
    assert r.allowed == Decimal("2.00")
    assert not r.passes and r.exceeds_pct and not r.exceeds_abs
    assert "it fails the ±2% limit" in tolerance_sentence(2, r)


def test_favorable_delta_always_passes() -> None:
    r = line_tolerance("10.00", "100", "900.00")
    assert r.passes and r.favorable and r.delta == Decimal("-100.00")
    assert tolerance_sentence(1, r).endswith("so it passes as favorable.")


def test_within_tolerance_sentence() -> None:
    r = line_tolerance("10.00", "10", "101.00")
    assert r.passes
    assert tolerance_sentence(1, r).endswith("— it is within tolerance.")


def test_rounding_expected_ext_half_up() -> None:
    r = line_tolerance("0.125", "3", "0.38")  # 0.375 → 0.38
    assert r.expected_ext == Decimal("0.38") and r.delta == 0


def test_zero_expected() -> None:
    r = line_tolerance("0", "5", "0")
    assert r.delta_pct is None and r.delta_pct_display == "n/a" and r.passes


def test_custom_policy() -> None:
    r = line_tolerance("10", "10", "104", pct="0.05", abs_amount="3")
    assert r.allowed == Decimal("3.00") and not r.passes


cents_amount = st.integers(min_value=0, max_value=10_000_000).map(lambda n: Decimal(n).scaleb(-2))
unit_price = st.integers(min_value=1, max_value=1_000_000).map(lambda n: Decimal(n).scaleb(-4))
qty = st.integers(min_value=1, max_value=2000).map(Decimal)


@given(unit_price, qty, cents_amount)
def test_property_passes_iff_within_min_limit(u: Decimal, q: Decimal, amount: Decimal) -> None:
    r = line_tolerance(u, q, amount)
    exp = r.expected_ext
    limit = min(Decimal("0.02") * exp, Decimal("25.00"))
    delta = amount - exp
    assert r.passes == (delta < 0 or abs(delta) <= limit)
    assert r.allowed <= Decimal("25.00")
    assert r.expected_ext.as_tuple().exponent == -2
