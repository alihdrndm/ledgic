from decimal import Decimal

from app.domain.qty import qty_check


def test_all_equal_passes_with_note() -> None:
    r = qty_check("12", "12", "12")
    assert r.passes and r.verdict == "matched"
    assert r.note == "ordered 12 · received 12 · invoiced 12"
    assert r.payable_qty == Decimal(12)


def test_over_receipt() -> None:
    r = qty_check("12", "10", "12")
    assert r.over_receipt and not r.over_order and r.verdict == "qty_over_receipt"
    assert r.payable_qty == Decimal(10)


def test_over_order_with_and_without_allowance() -> None:
    r = qty_check("13", "13", "12")
    assert r.over_order and not r.over_receipt and r.verdict == "qty_over_order"
    assert r.payable_qty == Decimal(12)
    assert qty_check("13", "13", "12", over_receipt_allowance="0.10").passes


def test_both_failures_report_over_receipt_first() -> None:
    r = qty_check("15", "10", "12")
    assert r.over_receipt and r.over_order and r.verdict == "qty_over_receipt"
    assert r.payable_qty == Decimal(10)


def test_two_way_skips_grn() -> None:
    r = qty_check("12", None, "12", match_mode="two_way")
    assert r.passes and r.received is None
    assert r.note == "ordered 12 · invoiced 12 · two-way, no receipt check"
    assert not qty_check("13", None, "12", match_mode="two_way").passes


def test_three_way_without_grn_means_nothing_received() -> None:
    r = qty_check("5", None, "5")
    assert r.over_receipt and r.received == 0
    assert r.note == "ordered 5 · no receipt · invoiced 5"


def test_no_po_qty_only_checks_grn() -> None:
    r = qty_check("5", "5", None)
    assert r.passes and r.note == "received 5 · invoiced 5"
