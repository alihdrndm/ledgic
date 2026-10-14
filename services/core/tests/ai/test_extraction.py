from __future__ import annotations

import base64
import io
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from app.ai import extraction
from app.ai.extraction import (
    MAX_SIDE,
    ExtractionUnavailable,
    extract_document,
    load_hero_fixture,
    prepare_pages,
)
from app.ai.schemas import ExtractionResult, normalize_extraction
from app.domain.gate import evaluate_gate

from .conftest import HEROES_DIR, REPO, MemoryBudgetStore, load_hero

HEROES = ["PS-88214", "PR-2214", "PR-2201", "PR-2201-photo", "NV-0001", "BD-104882"]


# ------------------------------------------------------------------------------------------ schema
def _norm_schema(s: Any, defs: dict[str, Any]) -> Any:
    """Resolve $refs, drop titles/descriptions, express nullable unions as type lists."""
    if isinstance(s, list):
        return [_norm_schema(x, defs) for x in s]
    if not isinstance(s, dict):
        return s
    if "$ref" in s:
        return _norm_schema(defs[s["$ref"].split("/")[-1]], defs)
    if "anyOf" in s:
        opts = [_norm_schema(o, defs) for o in s["anyOf"]]
        non_null = [o for o in opts if o.get("type") != "null"]
        if len(non_null) == 1 and len(opts) == 2:
            merged = dict(non_null[0])
            merged["type"] = [non_null[0]["type"], "null"]
            return merged
        return {"anyOf": opts}
    out = {
        k: _norm_schema(v, defs)
        for k, v in s.items()
        if k not in ("title", "description", "$defs", "default")
    }
    if out.get("type") == "string" and "enum" in out:
        out["enum"] = sorted(out["enum"])
    if "required" in out:
        out["required"] = sorted(out["required"])
    return out


def test_pydantic_schema_matches_contract() -> None:
    from agents.agent_output import AgentOutputSchema

    contract = json.loads((REPO / "contracts" / "extraction.schema.json").read_text(encoding="utf-8"))
    contract = {k: v for k, v in contract.items() if not k.startswith("$")}
    sent = AgentOutputSchema(ExtractionResult, strict_json_schema=True)
    assert sent.is_strict_json_schema()
    ours = sent.json_schema()
    assert _norm_schema(ours, ours.get("$defs", {})) == _norm_schema(contract, {})


@pytest.mark.parametrize("name", HEROES)
def test_hero_fixtures_validate(name: str) -> None:
    data = load_hero(name)
    result = ExtractionResult.model_validate(data["extraction"])  # strict: extra keys forbidden
    assert result.document_type == "invoice"
    assert result.invoice_number.value == name.removesuffix("-photo")
    for fv in [getattr(result, k) for k in ("total", "vendor_name", "invoice_number")]:
        assert fv.value is not None and fv.bbox is not None and 0 < fv.confidence <= 1


def _gate(result: ExtractionResult):
    from app.domain.gate import LineAmounts

    lines = [LineAmounts.of(ln.qty.value, ln.unit_price.value, ln.amount.value) for ln in result.lines]
    return evaluate_gate(
        result.gate_fields(),
        lines=lines,
        tax=result.tax.value,
        freight=result.freight.value,
        total=result.total.value,
    )


def test_pr2214_smudge_goes_to_review() -> None:
    r = ExtractionResult.model_validate(load_hero("PR-2214")["extraction"])
    assert r.lines[1].qty.confidence == pytest.approx(0.71)
    g = _gate(r)
    assert g.doc_confidence == Decimal("0.880")
    assert g.flagged_fields == ("lines[1].qty",)
    assert not g.passes


@pytest.mark.parametrize(("name", "conf"), [("BD-104882", "0.970"), ("PS-88214", "0.980")])
def test_clean_heroes_pass_gate(name: str, conf: str) -> None:
    r = ExtractionResult.model_validate(load_hero(name)["extraction"])
    g = _gate(r)
    assert g.doc_confidence == Decimal(conf)
    assert g.passes


def test_ps88214_values_match_fixtures() -> None:
    fixtures = json.loads((REPO / "contracts" / "fixtures.json").read_text(encoding="utf-8"))
    hero = fixtures["heroes"]["PS-88214"]
    r = ExtractionResult.model_validate(load_hero("PS-88214")["extraction"])
    assert r.total.value == hero["total"]
    assert [ln.amount.value for ln in r.lines] == [ln["amount"] for ln in hero["lines"]]
    assert r.lines[0].unit_price.value == "4.12" and r.po_reference.value == "PO-RS-1873"


def test_normalize_accepts_corpus_shape() -> None:
    from app.demo.corpus.catalog import build_catalog
    from app.demo.corpus.invoices import hero_docs

    day = date(2026, 10, 14)
    doc = next(d for d in hero_docs(build_catalog(day), day) if d.hero == "NV-0001")
    sim = doc.simulated_extraction
    assert "bank_details" in sim  # 06 §5.1 nested shape
    r = normalize_extraction(sim)
    assert r.bank_routing.value == sim["bank_details"]["value"]["routing"]
    assert r.remit_to_name.value == sim["remit_to"]["value"]["name"]


# ------------------------------------------------------------------------------------------ pages
def _png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="JPEG")
    return buf.getvalue()


def test_prepare_pages_downscales_and_caps() -> None:
    urls = prepare_pages([_png(3200, 2400)] * 5, "image/jpeg")
    assert len(urls) == 3
    img = Image.open(io.BytesIO(base64.b64decode(urls[0].split(",", 1)[1])))
    assert max(img.size) == MAX_SIDE and img.size == (1600, 1200)
    assert urls[0].startswith("data:image/png;base64,")


def test_prepare_pages_renders_pdf() -> None:
    pdf = REPO / "tools" / "corpus" / "out" / "Invoice_BD-104882.pdf"
    if not pdf.is_file():
        pytest.skip("corpus PDF not generated")
    urls = prepare_pages([pdf.read_bytes()], "application/pdf")
    assert len(urls) == 2  # BD-104882 is a 2-page invoice
    img = Image.open(io.BytesIO(base64.b64decode(urls[0].split(",", 1)[1])))
    assert max(img.size) <= MAX_SIDE


# ------------------------------------------------------------------------------------------ entrypoint
async def test_fixture_mode_uses_recorded_hero(fixture_gateway, no_network: None) -> None:
    out = await extract_document([b"ignored"], mime="application/pdf", hero="PS-88214", org_id="o")
    assert out.mode == "recorded" and out.cost_usd == 0 and out.model is None
    assert out.prompt_version == "p-1" and out.fallback_reason == "fixture mode"
    assert out.result.total.value == "2847.60"


async def test_fixture_mode_prefers_caller_fixture(fixture_gateway, no_network: None) -> None:
    fx = load_hero_fixture("PR-2214")
    assert fx is not None
    out = await extract_document([], mime="image/jpeg", fixture=fx, hero="PS-88214")
    assert out.mode == "simulated" and out.result.invoice_number.value == "PR-2214"


async def test_fixture_mode_without_fixture_raises(fixture_gateway, no_network: None) -> None:
    with pytest.raises(ExtractionUnavailable):
        await extract_document([b"x"], mime="image/png")


async def test_live_extraction_metered(live_gateway, store: MemoryBudgetStore, monkeypatch) -> None:
    from app.ai import runtime

    seen: dict[str, Any] = {}

    async def fake_run_agent(agent, input, meter, **kw):
        seen["images"] = [c for c in input[0]["content"] if c["type"] == "input_image"]
        seen["output_type"] = agent.output_type
        meter.add_agents_usage(
            SimpleNamespace(
                input_tokens=5200,
                output_tokens=1800,
                requests=1,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            )
        )
        return SimpleNamespace(
            final_output=ExtractionResult.model_validate(load_hero("PS-88214")["extraction"])
        )

    monkeypatch.setattr(runtime, "run_agent", fake_run_agent)
    out = await extract_document([_png(2000, 2600)], mime="image/jpeg", org_id="org-1", fixture={"x": 1})
    assert out.mode == "live" and out.model == "gpt-4.1-mini" and out.pages_sent == 1
    assert out.cost_usd == Decimal("0.004960")  # 5200 × 0.40/1M + 1800 × 1.60/1M
    assert seen["output_type"] is ExtractionResult and len(seen["images"]) == 1
    assert store.ledger[0]["meta"]["purpose"] == "extraction"


async def test_live_over_budget_falls_back_to_fixture(monkeypatch) -> None:
    from app.ai.gateway import LlmGateway

    from .conftest import make_settings

    gw = LlmGateway(
        make_settings(llm_mode="live", openai_api_key="sk"), MemoryBudgetStore(cap=Decimal("0.0001"))
    )
    out = await extract_document([_png(100, 100)], mime="image/png", hero="BD-104882", gateway=gw)
    assert out.mode == "recorded" and out.fallback_reason and out.fallback_reason.startswith("budget")


def test_prompt_file_present() -> None:
    text = extraction.extraction_prompt()
    assert "never infer" in text.lower() or "never derive" in text.lower()
    assert (HEROES_DIR / "PS-88214.json").is_file()
