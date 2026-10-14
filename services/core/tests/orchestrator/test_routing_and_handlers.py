"""Pure pieces of the orchestrator: routing, backoff, gate inputs, payable lines, remit check, mock ERP."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.demo.corpus import build_catalog, hero_docs
from app.domain import evaluate_gate
from app.orchestrator.handlers.extraction import _normalize, gate_inputs, modeled_extraction_ms
from app.orchestrator.handlers.posting import payable_lines
from app.orchestrator.handlers.screening import _same_hero_other_day, remit_is_new
from app.orchestrator.routing import PARK, payment_terms, route_resume
from app.orchestrator.stages import ORDER, Stage, next_of
from app.orchestrator.transitions import BACKOFF_SECONDS, backoff
from app.posting import BillLine, BillRequest, MockErp, PostingRefused

DAY = date(2026, 10, 14)


def test_stage_order() -> None:
    assert [s.value for s in ORDER] == [
        "intake", "extraction", "review", "enrichment", "screening", "match", "approval", "posting", "close",
    ]
    assert next_of(Stage.MATCH) == Stage.APPROVAL and next_of(Stage.CLOSE) is None


def test_route_resume_table() -> None:
    assert route_resume("dispute") == PARK
    assert route_resume("request_w9") == PARK
    assert route_resume("merge", invoice_status="duplicate") == Stage.CLOSE
    assert route_resume("merge", invoice_status="screened") == Stage.SCREENING
    with pytest.raises(ValueError):
        route_resume("nope")


def test_payment_terms_latest_money_decision_wins() -> None:
    sp = {"action": "short_pay", "pay_amount": "2759.60", "hold_amount": "88.00"}
    assert payment_terms([sp]) == ("2759.60", "88.00")
    assert payment_terms([sp, {"action": "retry_posting"}]) == ("2759.60", "88.00")
    assert payment_terms([{"action": "release_hold"}]) == (None, None)
    assert payment_terms([sp, {"action": "approve_as_is"}]) == (None, None)


def test_backoff_schedule() -> None:
    assert [int(backoff(i).total_seconds()) for i in range(1, 7)] == [*BACKOFF_SECONDS, BACKOFF_SECONDS[-1]]


def _hero(key: str, channel: str | None = None):  # type: ignore[no-untyped-def]
    cat = build_catalog(DAY)
    return next(d for d in hero_docs(cat, DAY) if d.hero == key and (channel is None or d.channel == channel))


def test_pr2214_fixture_fails_gate_on_smudged_qty() -> None:
    data = _normalize(_hero("PR-2214").simulated_extraction)
    fields, lines, complete = gate_inputs(data)
    assert complete and "po_reference" in fields
    g = evaluate_gate(fields, lines=lines, total=data["total"]["value"], tax=data["tax"]["value"])
    assert not g.passes
    assert g.flagged_fields == ("lines[1].qty",)
    assert g.doc_confidence == Decimal("0.880")
    assert g.cross_checks[0].text == "$125.00 ÷ $31.25 unit = 4.0"


def test_bd104882_fixture_passes_gate() -> None:
    data = _normalize(_hero("BD-104882").simulated_extraction)
    fields, lines, _ = gate_inputs(data)
    g = evaluate_gate(fields, lines=lines, total=data["total"]["value"], tax=data["tax"]["value"])
    assert g.passes and g.doc_confidence == Decimal("0.970")
    assert len(lines) == 14


def test_null_optional_fields_are_skipped() -> None:
    data = _normalize(_hero("NV-0001").simulated_extraction)
    fields, _, _ = gate_inputs(data)
    assert "po_reference" not in fields  # no PO printed


def test_modeled_extraction_latency_is_deterministic() -> None:
    a = modeled_extraction_ms("d1", "email", 2)
    assert a == modeled_extraction_ms("d1", "email", 2)
    assert 2600 <= a <= 2600 + 900 + 2400


def test_payable_lines_short_pay_hero() -> None:
    lines = [
        {"sid": "l1", "amount": Decimal("824.00"), "unit_price": Decimal("4.12")},
        {"sid": "l2", "amount": Decimal("820.80"), "unit_price": Decimal("68.40")},
    ]
    rows = {
        "l1": {"verdict": "price_variance", "expected_amount": Decimal("736.00"), "grn_qty": Decimal(200)},
        "l2": {"verdict": "matched", "expected_amount": Decimal("820.80"), "grn_qty": Decimal(12)},
    }
    assert payable_lines(lines, rows, Decimal("88.00")) == [Decimal("736.00"), Decimal("820.80")]
    assert payable_lines(lines, rows, Decimal(0)) == [Decimal("824.00"), Decimal("820.80")]


def test_payable_lines_qty_short() -> None:
    lines = [{"sid": "l1", "amount": Decimal("100.00"), "unit_price": Decimal("10.00")}]
    rows = {"l1": {"verdict": "qty_over_receipt", "expected_amount": Decimal("100.00"), "grn_qty": Decimal(8)}}
    assert payable_lines(lines, rows, Decimal("20.00")) == [Decimal("80.00")]


def test_remit_is_new() -> None:
    now = datetime(2026, 10, 14, 14, tzinfo=UTC)
    old = {"created_at": now - timedelta(days=500), "remit_address_changed_at": None,
           "remit_address": {"name": "X", "line1": "10 Port Rd", "city_state_zip": "Secaucus, NJ 07094"}}
    assert not remit_is_new(old, "10 Port Rd, Secaucus, NJ 07094", now)
    assert remit_is_new(old, "PO Box 4411, Dover, DE 19901", now)
    young = {**old, "created_at": now - timedelta(days=4)}
    assert remit_is_new(young, "10 Port Rd, Secaucus, NJ 07094", now)


def test_same_hero_other_day_is_not_a_duplicate() -> None:
    assert _same_hero_other_day({"hero": "PR-2201", "demo_day": "2026-10-14"}, {"hero": "PR-2201", "demo_day": "2026-10-13"})
    assert not _same_hero_other_day({"hero": "PR-2201", "demo_day": "2026-10-14"}, {"hero": "PR-2201", "demo_day": "2026-10-14"})
    assert not _same_hero_other_day({}, {"hero": "PR-2201"})


def _req(**over) -> BillRequest:  # type: ignore[no-untyped-def]
    base = dict(
        invoice_id="inv-1", posting_key="ledgic-inv-1", vendor_id="v", vendor_name="Broadline Distributor",
        entity_short_code="E2", entity_ref=None, location_code="BS", invoice_number="BD-104882",
        invoice_date=DAY, due_date=DAY, lines=(BillLine(1, "Oil", Decimal(4), Decimal("38.17"), Decimal("152.68"), "5000", "COGS-Food"),),
        pay_amount=Decimal("152.68"), hold_amount=Decimal(0), memo="m",
    )
    base.update(over)
    return BillRequest(**base)


async def test_mock_quickbooks_is_deterministic() -> None:
    erp = MockErp("quickbooks", latency=False)
    a, b = await erp.create_bill(_req()), await erp.create_bill(_req())
    assert a.ok and a.external_id == b.external_id
    assert a.display_ref.startswith("Bill ") and "," in a.display_ref
    assert 300 <= a.latency_ms <= 900
    assert a.response["mock"] is True
    body = _req().as_json("quickbooks")
    assert body["Line"][0]["AccountBasedExpenseLineDetail"]["ClassRef"]["name"] == "BS"


async def test_mock_netsuite_and_failure_and_duplicate_block() -> None:
    erp = MockErp("netsuite", latency=False)
    ok = await erp.create_bill(_req())
    assert ok.display_ref.startswith("vendorBill ")
    bad = await erp.create_bill(_req(), fail=True)
    assert not bad.ok and "503" in (bad.error or "")
    with pytest.raises(PostingRefused):
        await erp.create_bill(_req(duplicate_of="inv-0"))
