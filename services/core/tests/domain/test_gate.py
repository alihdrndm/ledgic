from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.domain.gate import (
    LineAmounts,
    calibrate_fallback,
    check_arithmetic,
    cross_check_line,
    cross_check_total,
    doc_confidence,
    evaluate_gate,
    field_label,
    field_weight,
    is_required,
    review_callout_body,
    review_callout_title,
)

# PR-2214 (photo, smudged qty on line 2). This calibrated field set yields doc confidence exactly 0.880 —
# the value in contracts/fixtures.json — with the smudged qty at 0.71.
PR2214_HEADER = {
    "vendor": "0.95",
    "invoice_number": "0.92",
    "invoice_date": "0.93",
    "total": "0.93",
    "po_ref": "0.86",
    "terms": "0.83",
}
PR2214_LINE_CONF = [  # (qty, unit_price, amount)
    ("0.88", "0.86", "0.87"),
    ("0.71", "0.86", "0.87"),
    ("0.87", "0.85", "0.86"),
    ("0.86", "0.85", "0.86"),
    ("0.87", "0.84", "0.85"),
]


def pr2214_fields() -> dict[str, str]:
    f = dict(PR2214_HEADER)
    for i, (q, u, a) in enumerate(PR2214_LINE_CONF):
        f[f"lines[{i}].qty"], f[f"lines[{i}].unit_price"], f[f"lines[{i}].amount"] = q, u, a
    return f


def pr2214_lines(hero: dict) -> list[LineAmounts]:
    return [LineAmounts.of(ln["qty"], ln["unit_price"], ln["amount"]) for ln in hero["lines"]]


def test_weights_and_labels() -> None:
    assert field_weight("vendor") == 3 and field_weight("vendor_name") == 3
    assert field_weight("po_reference") == 2 and field_weight("terms") == 1
    assert field_weight("lines[3].amount") == 1 and field_weight("lines[0].description") == 0
    assert field_weight("due_date") == 0
    assert is_required("total") and not is_required("po_ref") and is_required("lines[0].qty")
    assert not is_required("lines[0].uom")
    assert field_label("lines[1].qty") == "quantity, line 2"
    assert field_label("invoice_number") == "invoice number"
    assert field_label("due_date") == "due date"


def test_weighted_geometric_mean() -> None:
    # vendor (w3) 0.9, invoice_date (w2) 0.8 → exp((3 ln .9 + 2 ln .8)/5)
    import math

    expected = math.exp((3 * math.log(0.9) + 2 * math.log(0.8)) / 5)
    assert doc_confidence({"vendor": "0.9", "invoice_date": "0.8"}) == Decimal(f"{expected:.3f}")
    assert doc_confidence({"due_date": "0.1"}) == Decimal("0.000")  # nothing weighted
    assert doc_confidence({"vendor": 0.0, "total": "1"}) < Decimal("0.01")  # zero is clamped, not an error


def test_pr2214_smudge_goes_to_review(heroes: dict) -> None:
    hero = heroes["PR-2214"]
    exp = hero["expected"]
    lines = pr2214_lines(hero)
    g = evaluate_gate(pr2214_fields(), lines=lines, total=hero["total"])
    assert g.doc_confidence == Decimal(exp["doc_confidence"])  # 0.88
    assert g.doc_confidence < Decimal("0.90")
    assert not g.passes and g.needs_review and not g.doc_passes and not g.floor_passes
    assert g.arithmetic is not None and g.arithmetic.passes
    assert g.flagged_fields == (exp["flagged_field"],) == ("lines[1].qty",)
    (cc,) = g.cross_checks
    assert cc.text == "$125.00 ÷ $31.25 unit = 4.0" and cc.agrees
    assert review_callout_title(g.flagged_fields) == "One field needs confirmation — quantity, line 2"
    assert review_callout_body("4", exp["flagged_confidence"], cc) == (
        "Model read 4 at confidence 0.71. Cross-check: $125.00 ÷ $31.25 unit = 4.0, "
        "so the arithmetic agrees with the smudged digit."
    )


def test_smudged_qty_alone_is_caught_by_field_floor(heroes: dict) -> None:
    hero = heroes["PR-2214"]
    lines = pr2214_lines(hero)
    fields = {k: "1.0" for k in pr2214_fields()}
    fields["lines[1].qty"] = "0.71"
    g = evaluate_gate(fields, lines=lines, total=hero["total"])
    assert g.doc_passes and not g.floor_passes and not g.passes  # cross-check never overrides the gate


def test_clean_extraction_passes() -> None:
    lines = [LineAmounts.of("2", "10.00", "20.00")]
    fields = {"vendor": 0.98, "invoice_number": 0.97, "invoice_date": 0.97, "total": 0.98}
    fields |= {"lines[0].qty": 0.97, "lines[0].unit_price": 0.97, "lines[0].amount": 0.97}
    g = evaluate_gate(fields, lines=lines, tax="1.50", freight="0.50", total="22.00")
    assert g.passes and g.flagged_fields == () and g.cross_checks == ()


def test_arithmetic_checks() -> None:
    lines = [LineAmounts.of("3", "1.10", "3.30"), LineAmounts.of("3", "1.10", "3.32")]
    a = check_arithmetic(lines, total="6.62")
    assert a.failing_lines == (1,) and a.total_ok and not a.passes
    b = check_arithmetic(lines[:1], tax="0.30", freight="0.03", total="3.63")
    assert b.total_ok and b.total_delta == Decimal("0.00") and b.passes
    c = check_arithmetic(lines[:1], total="3.33")
    assert not c.total_ok and c.total_delta == Decimal("-0.03")
    assert check_arithmetic(lines[:1], total="3.32").total_ok  # within 0.02
    d = check_arithmetic(lines[:1])
    assert d.total_delta is None and d.passes


def test_arithmetic_failure_fails_gate_even_with_high_confidence() -> None:
    lines = [LineAmounts.of("2", "10.00", "25.00")]
    g = evaluate_gate({"vendor": "0.99", "total": "0.99"}, lines=lines, total="25.00")
    assert g.doc_passes and g.floor_passes and not g.passes


def test_cross_checks_for_unit_amount_total() -> None:
    ln = LineAmounts.of("4", "31.25", "125.00")
    u = cross_check_line(ln, "unit_price", index=1)
    assert u is not None and u.text == "$125.00 ÷ 4 qty = $31.25" and u.field == "lines[1].unit_price"
    a = cross_check_line(ln, "amount")
    assert a is not None and a.text == "4 × $31.25 = $125.00" and a.implied_value == Decimal("125.00")
    assert cross_check_line(ln, "description") is None
    assert cross_check_line(LineAmounts.of("0", "1", "0"), "unit_price") is None
    assert cross_check_line(LineAmounts.of("1", "0", "0"), "qty") is None
    t = cross_check_total([ln], total="130.00", tax="5.00")
    assert t.agrees and t.text == "lines $125.00 + tax $5.00 + freight $0.00 = $130.00"


def test_flagged_total_gets_cross_check_and_disagreeing_callout() -> None:
    ln = LineAmounts.of("4", "31.25", "125.00")
    g = evaluate_gate(
        {"vendor": "0.99", "total": "0.60", "lines[0].amount": "0.70"}, lines=[ln], total="152.00"
    )
    assert g.flagged_fields == ("total", "lines[0].amount")
    assert {c.field for c in g.cross_checks} == {"total", "lines[0].amount"}
    total_cc = next(c for c in g.cross_checks if c.field == "total")
    assert not total_cc.agrees
    assert review_callout_title(g.flagged_fields) == "2 fields need confirmation"
    assert review_callout_body("152.00", "0.6", total_cc).endswith(
        "so the arithmetic does not agree — check the value."
    )
    assert review_callout_body("x", "0.5", None) == "Model read x at confidence 0.50."


def test_calibrate_fallback() -> None:
    assert calibrate_fallback(0.95, "agree") == Decimal("0.950")
    assert calibrate_fallback("0.95", "missing") == Decimal("0.760")
    assert calibrate_fallback(Decimal("0.95"), "disagree") == Decimal("0.570")


conf_st = st.integers(min_value=1, max_value=1000).map(lambda n: Decimal(n) / 1000)


@given(
    st.dictionaries(
        st.sampled_from(
            [
                "vendor",
                "invoice_number",
                "invoice_date",
                "total",
                "po_ref",
                "terms",
                "lines[0].qty",
                "lines[0].amount",
            ]
        ),
        conf_st,
        min_size=1,
    )
)
def test_property_doc_conf_between_min_and_max(fields: dict[str, Decimal]) -> None:
    dc = doc_confidence(fields)
    assert min(fields.values()) - Decimal("0.0005") <= dc <= max(fields.values()) + Decimal("0.0005")
