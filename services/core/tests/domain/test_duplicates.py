from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.domain.duplicates import (
    DupInvoice,
    DupLine,
    best_match,
    normalize_invoice_number,
    phash_similarity,
    score,
    trigram_similarity,
)

PHASH_A = "8f373714acfcf4d0"
PHASH_B = f"{int(PHASH_A, 16) ^ 0x7FF:016x}"  # 11 bits differ → 1 − 11/64 = 0.828

PR2201_LINES = (
    DupLine.of("Romaine hearts 24ct", "5", "92.00"),
    DupLine.of("Heirloom tomato 10lb", "4", "125.00"),
    DupLine.of("Lemons 115ct case", "3", "128.40"),
    DupLine.of("Shallots 5lb bag", "6", "119.40"),
    DupLine.of("Flat-leaf parsley 60ct", "6", "147.60"),
)


def pr2201(channel: str, **kw: object) -> DupInvoice:
    base = dict(
        vendor_id="produce",
        invoice_number="PR-2201" if channel == "email" else "pr 2201",
        total=Decimal("612.40"),
        invoice_date=date(2026, 7, 12),
        lines=PR2201_LINES,
        sha256="a41f" if channel == "email" else "c890",
        phash=PHASH_A if channel == "email" else PHASH_B,
    )
    base.update(kw)
    return DupInvoice(**base)  # type: ignore[arg-type]


def test_normalize_invoice_number() -> None:
    assert normalize_invoice_number("pr-2201") == normalize_invoice_number("PR 2201") == "PR2201"
    assert normalize_invoice_number("INV-000123") == "123"
    assert normalize_invoice_number("#00042") == "42"
    assert normalize_invoice_number("000") == "0"
    assert normalize_invoice_number("INVOICE") == "INVOICE"
    assert normalize_invoice_number(None) == ""


def test_pr2201_hard_duplicate_with_exact_evidence(heroes: dict) -> None:
    exp = heroes["PR-2201"]["expected"]
    assert sum(ln.amount for ln in PR2201_LINES) == Decimal(heroes["PR-2201"]["total"])
    s = score(pr2201("photo"), pr2201("email"))
    assert s.hard and s.similarity == Decimal("1.000")
    assert s.similarity >= Decimal(exp["similarity_min"])
    assert s.hold and not s.suggest
    assert s.evidence == exp["evidence"]
    assert s.weighted_score >= Decimal("0.90")


def test_soft_score_components_without_number_match() -> None:
    a = pr2201("photo", vendor_id="other")
    s = score(a, pr2201("email"))
    assert not s.hard
    # 0.30 + 0.20 + 0.30 + 0.10 + 0.10 × 0.828 = 0.983
    assert s.similarity == Decimal("0.983") == s.weighted_score
    assert s.components["image_sim"] == Decimal("0.828")


def test_near_miss_different_amount_below_suggest() -> None:
    other = pr2201(
        "photo",
        invoice_number="PR-2201A",
        total=Decimal("640.10"),
        invoice_date=date(2026, 7, 15),
        lines=PR2201_LINES[:3] + (DupLine.of("Shallots 5lb bag", "8", "159.20"),),
        phash=None,
    )
    s = score(other, pr2201("email"))
    assert s.similarity < Decimal("0.75") and not s.hold and not s.suggest
    assert s.evidence["amount"] == "Differs by $27.70"
    assert s.evidence["invoice_date"] == "3 days apart"
    assert s.evidence["line_items"] == "3 of 5 overlap"
    assert s.evidence["file"] == "Differs"
    assert s.evidence["invoice_number"] == "Similar · 0.67"
    assert not s.hard


def test_suggest_band_and_misc_evidence() -> None:
    other = pr2201("photo", invoice_number="ZZ-9", invoice_date=date(2026, 7, 13), sha256="a41f")
    s = score(other, pr2201("email"))
    # 0.30 + 0.20 × 6/7 + 0.30 + 0 + 0.10 × 0.828 ≈ 0.854
    assert s.suggest and not s.hold
    assert s.evidence["invoice_number"] == "Differs"
    assert s.evidence["invoice_date"] == "1 day apart"
    assert s.evidence["file"] == "Identical file"


def test_helpers() -> None:
    assert trigram_similarity("", "") == 0
    assert trigram_similarity("PR2201", "PR2201") == 1
    assert phash_similarity(None, PHASH_A) is None
    assert phash_similarity(0, 0) == 1
    assert score(pr2201("photo", lines=()), pr2201("email", lines=())).lines_compared == 0


def test_best_match() -> None:
    inv = pr2201("photo", vendor_id="x")
    far = pr2201("email", total=Decimal("1.00"), invoice_number="Q-1", lines=())
    near = pr2201("email")
    best = best_match(inv, [far, near])
    assert best is not None and best[0] is near
    assert best_match(inv, []) is None


money = st.integers(min_value=0, max_value=100_000).map(lambda n: Decimal(n).scaleb(-2))


@given(money, money, st.integers(0, 30), st.text(max_size=8), st.text(max_size=8))
def test_property_score_bounded_and_symmetric(t1: Decimal, t2: Decimal, days: int, n1: str, n2: str) -> None:
    a = DupInvoice("v", n1, t1, date(2026, 1, 1))
    b = DupInvoice("v", n2, t2, date(2026, 1, 1 + days % 28))
    s1, s2 = score(a, b), score(b, a)
    assert Decimal(0) <= s1.similarity <= Decimal(1)
    assert s1.similarity == s2.similarity
