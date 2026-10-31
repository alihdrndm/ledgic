"""Pure pieces of the orchestrator: routing, backoff, gate inputs, payable lines, remit check, mock ERP."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.demo.corpus import build_catalog, hero_docs
from app.domain import evaluate_gate
from app.orchestrator.handlers.extraction import _normalize, gate_inputs, modeled_extraction_ms
from app.orchestrator.handlers.posting import bill_lines, payable_lines
from app.orchestrator.handlers.screening import _same_hero_other_day, remit_is_new
from app.orchestrator.routing import PARK, payment_terms, route_resume
from app.orchestrator.stages import ORDER, Stage, next_of
from app.orchestrator.transitions import BACKOFF_SECONDS, backoff
from app.posting import BillLine, BillRequest, MockErp, PostingRefused, PostingValidationError

DAY = date(2026, 10, 14)


def test_stage_order() -> None:
    assert [s.value for s in ORDER] == [
        "intake",
        "extraction",
        "review",
        "enrichment",
        "screening",
        "match",
        "approval",
        "posting",
        "close",
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
    rows = {
        "l1": {"verdict": "qty_over_receipt", "expected_amount": Decimal("100.00"), "grn_qty": Decimal(8)}
    }
    assert payable_lines(lines, rows, Decimal("20.00")) == [Decimal("80.00")]


def test_remit_is_new() -> None:
    now = datetime(2026, 10, 14, 14, tzinfo=UTC)
    old = {
        "created_at": now - timedelta(days=500),
        "remit_address_changed_at": None,
        "remit_address": {"name": "X", "line1": "10 Port Rd", "city_state_zip": "Secaucus, NJ 07094"},
    }
    assert not remit_is_new(old, "10 Port Rd, Secaucus, NJ 07094", now)
    assert remit_is_new(old, "PO Box 4411, Dover, DE 19901", now)
    young = {**old, "created_at": now - timedelta(days=4)}
    assert remit_is_new(young, "10 Port Rd, Secaucus, NJ 07094", now)


def test_same_hero_other_day_is_not_a_duplicate() -> None:
    assert _same_hero_other_day(
        {"hero": "PR-2201", "demo_day": "2026-10-14"}, {"hero": "PR-2201", "demo_day": "2026-10-13"}
    )
    assert not _same_hero_other_day(
        {"hero": "PR-2201", "demo_day": "2026-10-14"}, {"hero": "PR-2201", "demo_day": "2026-10-14"}
    )
    assert not _same_hero_other_day({}, {"hero": "PR-2201"})


def _req(**over) -> BillRequest:  # type: ignore[no-untyped-def]
    base = dict(
        invoice_id="inv-1",
        posting_key="ledgic-inv-1",
        vendor_id="v",
        vendor_name="Broadline Distributor",
        entity_short_code="E2",
        entity_ref=None,
        location_code="BS",
        invoice_number="BD-104882",
        invoice_date=DAY,
        due_date=DAY,
        lines=(BillLine(1, "Oil", Decimal(4), Decimal("38.17"), Decimal("152.68"), "5000", "COGS-Food"),),
        pay_amount=Decimal("152.68"),
        hold_amount=Decimal(0),
        memo="m",
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


def _line(no: int, amount: str) -> dict[str, Any]:
    return {
        "sid": f"s{no}",
        "line_no": no,
        "description": f"item {no}",
        "qty": 1,
        "unit_price": Decimal(amount),
        "amount": Decimal(amount),
        "gl_account_id": 1,
    }


def _chart() -> dict[str, dict[str, Any]]:
    return {
        "1": {"id": 1, "number": "5000", "name": "COGS-Food"},
        "2": {"id": 2, "number": "2200", "name": "Sales Tax Payable"},
        "3": {"id": 3, "number": "6300", "name": "Freight In"},
        "4": {"id": 4, "number": "9999", "name": "Rounding"},
    }


def test_bill_lines_sum_to_the_total_with_tax_and_freight() -> None:
    lines = [_line(1, "824.00"), _line(2, "820.80")]
    tax, freight = Decimal("41.12"), Decimal("60.00")
    total = sum((ln["amount"] for ln in lines), Decimal(0)) + tax + freight

    full = bill_lines(lines, {}, Decimal(0), tax, freight, _chart(), total)
    assert sum((bl.amount for bl in full), Decimal(0)) == total
    # Purchase tax is allocated across the goods lines, which keep their own GL; it never posts to
    # Sales Tax Payable (2200). Freight gets its own coded line.
    assert [bl.description for bl in full] == ["item 1", "item 2", "Freight"]
    assert [(bl.gl_number, bl.gl_name) for bl in full] == [
        ("5000", "COGS-Food"),
        ("5000", "COGS-Food"),
        ("6300", "Freight In"),
    ]
    assert full[2].amount == freight

    hold = Decimal("88.00")
    short = bill_lines(lines, {}, hold, tax, freight, _chart(), total - hold)
    assert sum((bl.amount for bl in short), Decimal(0)) == total - hold


def test_bill_lines_allocate_tax_across_goods_lines_pro_rata() -> None:
    lines = [_line(1, "100.00"), _line(2, "50.00"), _line(3, "50.00")]
    tax = Decimal("10.00")
    total = sum((ln["amount"] for ln in lines), Decimal(0)) + tax

    out = bill_lines(lines, {}, Decimal(0), tax, Decimal(0), _chart(), total)

    # 10.00 splits 5.00 / 2.50 / 2.50 by amount.
    assert [(bl.description, bl.amount) for bl in out] == [
        ("item 1", Decimal("105.00")),
        ("item 2", Decimal("52.50")),
        ("item 3", Decimal("52.50")),
    ]
    assert sum((bl.amount for bl in out), Decimal(0)) == total


def test_bill_lines_put_a_small_remainder_on_a_rounding_line() -> None:
    out = bill_lines(
        [_line(1, "100.00")], {}, Decimal(0), Decimal("8.25"), Decimal(0), _chart(), Decimal("108.26")
    )
    assert [(bl.description, bl.amount) for bl in out] == [
        ("item 1", Decimal("108.25")),
        ("Rounding", Decimal("0.01")),
    ]
    assert out[-1].gl_number == "9999"
    assert sum((bl.amount for bl in out), Decimal(0)) == Decimal("108.26")


def test_bill_lines_fold_missing_accounts_into_the_largest_goods_line() -> None:
    """Charts seeded before 6300/9999 existed keep posting: freight and the remainder land on the
    largest goods line, which keeps its own GL, and the lines still sum to the total."""
    chart = {"1": {"id": 1, "number": "5000", "name": "COGS-Food"}}
    lines = [_line(1, "100.00"), _line(2, "40.00")]
    freight = Decimal("15.00")
    total = sum((ln["amount"] for ln in lines), Decimal(0)) + freight
    pay = total + Decimal("0.02")  # a confirmed total drifting by the gate tolerance

    out = bill_lines(lines, {}, Decimal(0), Decimal(0), freight, chart, pay)

    assert [bl.description for bl in out] == ["item 1", "item 2"]
    assert [(bl.gl_number, bl.gl_name) for bl in out] == [("5000", "COGS-Food")] * 2
    assert out[0].amount == Decimal("115.02")  # largest line: freight 15.00 + remainder 0.02
    assert out[1].amount == Decimal("40.00")
    assert sum((bl.amount for bl in out), Decimal(0)) == pay


def test_bill_lines_refuse_a_total_the_lines_cannot_reach() -> None:
    with pytest.raises(PostingValidationError):
        bill_lines([_line(1, "100.00")], {}, Decimal(0), Decimal(0), Decimal(0), _chart(), Decimal("140.00"))


def test_bill_lines_refuse_a_hold_bigger_than_the_goods_lines() -> None:
    with pytest.raises(PostingValidationError):
        bill_lines([_line(1, "100.00")], {}, Decimal("120.00"), Decimal(0), Decimal(0), _chart(), Decimal(0))


def test_bill_lines_refuse_tax_without_goods_lines_to_carry_it() -> None:
    with pytest.raises(PostingValidationError):
        bill_lines([], {}, Decimal(0), Decimal("8.25"), Decimal(0), _chart(), Decimal("8.25"))


def _ctx() -> Any:
    return SimpleNamespace(
        conn=None,
        clock=SimpleNamespace(virtual=True),
        options=SimpleNamespace(erp_latency=False, fast=True),
        policy={"sla_hours": 24},
        now=lambda: datetime(2026, 10, 14, 13, tzinfo=UTC),
    )


def _run() -> Any:
    return SimpleNamespace(
        id="run-1",
        run_number=1,
        org_id="org",
        document_id="doc",
        invoice_id="inv-1",
        status="posting",
        current_stage="posting",
        next_stage=None,
        attempt=1,
        context={},
        wait_exception_id=None,
        started_at=None,
    )


def _posting_env(monkeypatch: pytest.MonkeyPatch, *, total: str = "1745.92") -> dict[str, Any]:
    """Stub every repository the posting handler touches, and capture what it writes."""
    from app.repo import exceptions as exc_repo
    from app.repo import invoices as inv_repo
    from app.repo import journal

    inv = {
        "status": "new",
        "duplicate_of": None,
        "entity_erp": "quickbooks",
        "entity_name": "E",
        "entity_short_code": "E2",
        "location_code": "BS",
        "vendor_id": "v",
        "vendor_name": "V",
        "invoice_number": "BD-1",
        "invoice_date": DAY,
        "due_date": DAY,
        "total": total,
        "tax": "41.12",
        "freight": "60.00",
    }
    lines = [_line(1, "824.00"), _line(2, "820.80")]
    captured: dict[str, Any] = {"exceptions": [], "postings": [], "events": []}

    async def get_invoice(conn: Any, invoice_id: str) -> dict[str, Any]:
        return inv

    async def get_lines(conn: Any, invoice_id: str) -> list[dict[str, Any]]:
        return lines

    async def match_hold(conn: Any, invoice_id: str) -> dict[str, Any]:
        return {}

    async def chart(conn: Any, sql: str, params: Any) -> list[dict[str, Any]]:
        return list(_chart().values())

    async def no_posting(conn: Any, invoice_id: str, system: str) -> None:
        return None

    async def update_invoice(conn: Any, invoice_id: str, **cols: Any) -> None:
        return None

    async def upsert(conn: Any, **kw: Any) -> None:
        captured["postings"].append(kw)

    async def create_exception(conn: Any, **kw: Any) -> str:
        captured["exceptions"].append(kw)
        return "exc-1"

    async def audit(conn: Any, **kw: Any) -> None:
        return None

    async def event(conn: Any, **kw: Any) -> int:
        captured["events"].append(kw)
        return 1

    monkeypatch.setattr(inv_repo, "get_invoice", get_invoice)
    monkeypatch.setattr(inv_repo, "lines", get_lines)
    monkeypatch.setattr(inv_repo, "match_hold_by_line", match_hold)
    monkeypatch.setattr(inv_repo, "update_invoice", update_invoice)
    monkeypatch.setattr(exc_repo, "posting_row", no_posting)
    monkeypatch.setattr(exc_repo, "upsert_posting", upsert)
    monkeypatch.setattr(exc_repo, "create_exception", create_exception)
    monkeypatch.setattr(journal, "write_audit", audit)
    monkeypatch.setattr(journal, "emit_event", event)
    import app.orchestrator.handlers.posting as posting_mod

    monkeypatch.setattr(posting_mod, "all_", chart)
    return captured


async def test_the_posted_bill_total_matches_the_sum_of_its_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.orchestrator.handlers.posting import handle

    captured = _posting_env(monkeypatch)
    t = await handle(_ctx(), _run())
    assert t.kind == "advance"
    body = captured["postings"][0]["request"]
    line_sum = sum((Decimal(ln["Amount"]) for ln in body["Line"]), Decimal(0))
    assert Decimal(body["TotalAmt"]) == line_sum
    assert all(ln["AccountBasedExpenseLineDetail"]["AccountRef"]["name"] for ln in body["Line"])


async def test_a_bill_the_erp_would_reject_is_never_posted(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.orchestrator.handlers.posting import handle

    captured = _posting_env(monkeypatch, total="1800.00")

    async def never(req: Any, *, fail: bool = False) -> Any:  # pragma: no cover - must not run
        raise AssertionError("posted a bill whose lines cannot reach its total")

    import app.orchestrator.handlers.posting as posting_mod

    monkeypatch.setattr(posting_mod, "adapter_for", lambda system, **kw: SimpleNamespace(create_bill=never))
    t = await handle(_ctx(), _run())
    assert t.kind == "park" and t.detail.get("exception_type") == "posting_failed"
    assert captured["events"][-1]["detail"]["retryable"] is False


async def test_a_non_retryable_posting_failure_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.orchestrator.handlers.posting import handle
    from app.posting import PostingResult

    dead = PostingResult(
        False, "quickbooks", None, None, {"status": 422}, "validation failed", 5, retryable=False
    )
    captured = _posting_env(monkeypatch)

    async def create_bill(req: Any, *, fail: bool = False) -> Any:
        return dead

    import app.orchestrator.handlers.posting as posting_mod

    monkeypatch.setattr(
        posting_mod, "adapter_for", lambda system, **kw: SimpleNamespace(create_bill=create_bill)
    )
    t = await handle(_ctx(), _run())
    assert t.kind == "park" and t.detail.get("exception_type") == "posting_failed"
    assert len(captured["exceptions"]) == 1
    assert captured["events"][-1]["duration_ms"] == 5


async def test_a_retryable_posting_failure_still_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.orchestrator.handlers.posting import handle
    from app.posting import PostingResult

    async def create_bill(req: Any, *, fail: bool = False) -> Any:
        return PostingResult(
            False, "quickbooks", None, None, {"status": 503}, "503 outage", 5, retryable=True
        )

    import app.orchestrator.handlers.posting as posting_mod

    _posting_env(monkeypatch)
    monkeypatch.setattr(
        posting_mod, "adapter_for", lambda system, **kw: SimpleNamespace(create_bill=create_bill)
    )
    t = await handle(_ctx(), _run())
    assert t.kind == "retry"
