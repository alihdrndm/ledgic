from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from app.ai import resolution
from app.ai.rag.retrieve import Chunk
from app.ai.resolution import (
    DraftFacts,
    draft_for_exception,
    money_figures,
    money_guard,
    recorded_draft,
    template_draft,
)

from .conftest import HEROES_DIR

C42 = Chunk(
    "c-42",
    "d-1",
    "Protein Supplier — Vendor agreement 2026",
    "contract",
    "… > 4.2 Pricing",
    "4.2",
    "Shrimp 16/20 IQF 2lb × 10 is priced at **$3.68 per lb** for the Term.",
)


def ps88214_facts() -> DraftFacts:
    lines: list[dict[str, Any]] = [
        {
            "line_no": 1,
            "description": "Shrimp 16/20 IQF 2lb × 10",
            "qty": "200.000",
            "uom": "lb",
            "unit_price": "4.1200",
            "amount": "824.00",
            "grn_qty": "200.000",
            "expected_unit_price": "3.6800",
            "expected_source": "contract",
            "expected_amount": "736.00",
            "delta_amount": "88.00",
            "allowed_amount": "14.72",
            "verdict": "price_variance",
            "clause_ref": "4.2",
            "contract_title": "Vendor agreement 2026",
            "contract_effective_to": "2027-03-31",
            "po_unit_price": "3.6800",
            "po_amount": "736.00",
        },
        {
            "line_no": 2,
            "description": "Cod loin 10lb case",
            "qty": "12",
            "uom": "cs",
            "unit_price": "68.40",
            "amount": "820.80",
            "verdict": "matched",
        },
        {
            "line_no": 3,
            "description": "Scallops U-10 dry 2lb",
            "qty": "8",
            "uom": "ea",
            "unit_price": "54.25",
            "amount": "434.00",
            "verdict": "matched",
        },
        {
            "line_no": 4,
            "description": "Crab claw meat 5lb",
            "qty": "6",
            "uom": "ea",
            "unit_price": "71.90",
            "amount": "431.40",
            "verdict": "matched",
        },
        {
            "line_no": 5,
            "description": "Oysters select 1gal",
            "qty": "4",
            "uom": "ea",
            "unit_price": "84.35",
            "amount": "337.40",
            "verdict": "matched",
        },
    ]
    return DraftFacts(
        org_id="org",
        exception={
            "exception_id": "e-1",
            "type": "price_variance",
            "status": "open",
            "reason": "shrimp 12% over contract",
            "amount_at_risk": "88.00",
        },
        invoice={
            "id": "i-1",
            "invoice_number": "PS-88214",
            "invoice_date": "2026-10-14",
            "total": "2847.60",
            "subtotal": "2847.60",
            "tax": "0.00",
            "vendor_name": "Protein Supplier",
            "po_number": "PO-RS-1873",
            "po_total": "2759.60",
        },
        recommendation={
            "action": "short_pay",
            "pay_amount": "2759.60",
            "hold_amount": "88.00",
            "confidence": "0.940",
            "reasons": ["The agreement on file fixes this item at $3.68/lb."],
        },
        lines=lines,
        po={
            "purchase_order": {"po_number": "PO-RS-1873", "total": "2759.60"},
            "lines": [],
            "goods_receipts": [{"grn_number": "GRN-RS-4410"}],
            "received_in_full": True,
        },
        prior_short_pays=[
            {"invoice_number": "PS-87710", "hold_amount": "61.60", "pay_amount": "1900.00"},
            {"invoice_number": "PS-87102", "hold_amount": "47.20", "pay_amount": "2010.15"},
        ],
        contract_chunks=[C42],
    )


def test_money_figures_parsing() -> None:
    text = "Pay $2,759.60 and hold $88.00 (USD 14.72; 3.68 USD; $3.6800/lb; 12% over; 200 lb; clause 4.2)"
    assert money_figures(text) == ["2,759.60", "88.00", "14.72", "3.68", "3.6800"]


def test_guard_accepts_allowed_and_rejects_altered_amount() -> None:
    allowed = ps88214_facts().allowed_figures()
    ok = money_guard("We pay $2,759.60 and hold $88.00; contract $3.68/lb vs $4.12 billed.", allowed)
    assert ok.passed and ok.figures == ["2759.6", "88", "3.68", "4.12"]
    bad = money_guard("We pay $2,795.60 and hold $88.00.", allowed)  # transposed digits
    assert not bad.passed and bad.rejected == ["2,795.60"]
    computed = money_guard("That is $0.44 per lb more than agreed.", allowed)  # LLM-computed figure
    assert not computed.passed


def test_template_drafts_pass_guard() -> None:
    f = ps88214_facts()
    for kind in ("vendor_notice", "explanation"):
        body = template_draft(kind, f)
        g = money_guard(body, f.allowed_figures())
        assert g.passed, (kind, g.rejected, body)
    notice = template_draft("vendor_notice", f)
    assert "**$2,759.60**" in notice and "**$88.00**" in notice and "clause 4.2" in notice
    assert "GRN-RS-4410" in notice and "[1]" in notice


def test_recorded_hero_draft_passes_guard() -> None:
    assert (HEROES_DIR / "PS-88214.draft.json").is_file()
    f = ps88214_facts()
    for kind in ("vendor_notice", "explanation"):
        body = recorded_draft(kind, f)
        assert body and "{{" not in body
        g = money_guard(body, f.allowed_figures())
        assert g.passed, (kind, g.rejected)
    assert "through March 31, 2027" in (recorded_draft("vendor_notice", f) or "")


def test_recorded_draft_rejected_without_prior_short_pays() -> None:
    f = ps88214_facts()
    f.prior_short_pays = []
    body = recorded_draft("explanation", f) or ""
    assert not money_guard(body, f.allowed_figures()).passed  # $61.60 / $47.20 no longer allowed


@pytest.fixture
def facts(monkeypatch: pytest.MonkeyPatch) -> DraftFacts:
    f = ps88214_facts()

    async def fake_gather(exception_id: str) -> DraftFacts:
        return f

    monkeypatch.setattr(resolution, "gather_facts", fake_gather)
    return f


async def test_live_draft_with_altered_amount_falls_back(facts, live_gateway, monkeypatch) -> None:
    async def fake_live(kind, f, api_key, gw):
        return "We will pay $2,795.60 and hold $52.00 [1].", [], "gpt-4.1-mini", Decimal("0.0011")

    monkeypatch.setattr(resolution, "_draft_live", fake_live)
    d = await draft_for_exception("e-1", persist=False)
    assert d.mode == "recorded" and d.model is None
    assert d.guard["passed"] and d.guard["fallback"] and d.guard["reason"] == "money_guard"
    assert set(d.guard["rejected"]) == {"2,795.60", "52.00"}
    assert "$2,795.60" not in d.body_md and "$2,759.60" in d.body_md
    assert d.citations and d.citations[0]["clause_ref"] == "4.2"


async def test_live_draft_passing_guard_is_kept(facts, live_gateway, monkeypatch) -> None:
    body = "**Subject:** PS-88214\n\nWe pay $2,759.60 and hold $88.00 per clause 4.2 [1]."
    cites = [{"n": 1, "chunk_id": "c-42", "clause_ref": "4.2"}]

    async def fake_live(kind, f, api_key, gw):
        return body, cites, "gpt-4.1-mini", Decimal("0.0011")

    monkeypatch.setattr(resolution, "_draft_live", fake_live)
    d = await draft_for_exception("e-1", kind="explanation", persist=False)
    assert d.mode == "live" and d.model == "gpt-4.1-mini" and d.body_md == body
    assert d.guard == {
        "passed": True,
        "figures": ["2759.6", "88"],
        "fallback": False,
        "rejected": [],
        "reason": None,
    }
    assert json.loads(json.dumps(d.to_dict()))["cost_usd"] == "0.0011"


async def test_fixture_mode_uses_recorded_draft(facts, fixture_gateway, no_network: None) -> None:
    d = await draft_for_exception("e-1", persist=False)
    assert d.mode == "recorded" and d.guard["passed"] and d.guard["reason"] == "fixture mode"
    assert d.body_md.startswith("**Subject:** Short payment on invoice PS-88214")


async def test_draft_live_agent_wiring(live_gateway, store, monkeypatch) -> None:
    from types import SimpleNamespace

    from app.ai import runtime

    f = ps88214_facts()

    async def fake_run_agent(agent, input, meter, *, context, **kw):
        assert "kind=vendor_notice" in input and '"pay_amount": "2759.60"' in input
        assert "K1" in context.chunks and agent.output_type is resolution.DraftOut
        meter.add_agents_usage(
            SimpleNamespace(input_tokens=2500, output_tokens=200, requests=1, input_tokens_details=None)
        )
        return SimpleNamespace(final_output=resolution.DraftOut(body_md="Hold $88.00 per clause 4.2 [K1]."))

    monkeypatch.setattr(runtime, "run_agent", fake_run_agent)
    body, cites, model, cost = await resolution._draft_live("vendor_notice", f, None, live_gateway)
    assert body == "Hold $88.00 per clause 4.2 [1]." and cites[0]["chunk_id"] == "c-42"
    assert model == "gpt-4.1-mini" and cost == Decimal("0.001320")
    assert store.ledger[0]["meta"]["purpose"] == "resolution.vendor_notice"
