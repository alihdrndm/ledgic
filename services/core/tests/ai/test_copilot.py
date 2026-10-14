from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai import copilot
from app.ai.copilot import (
    _StreamRewriter,
    answer_retrieval_only,
    ask,
    finalize_citations,
    invoice_ref_in,
    normalize_question,
    q_hash,
    sse,
    stream_ask,
)
from app.ai.rag.retrieve import Chunk
from app.ai.tools import AgentCtx

from .conftest import needs_db

ORG = "992e72b7-9d9b-5104-9051-f5ef581c99e0"
C42 = Chunk(
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
    "Protein Supplier — Vendor agreement 2026",
    "contract",
    "Protein Supplier — Vendor agreement 2026 > 4. Pricing > 4.2 Pricing: Shrimp 16/20 IQF",
    "4.2",
    "Shrimp 16/20 IQF 2lb × 10 is priced at **$3.68 per lb** for the Term. The price applies to every\n"
    "location and every delivery, whatever the quantity ordered.",
)
POLICY = Chunk(
    "33333333-3333-3333-3333-333333333333",
    "44444444-4444-4444-4444-444444444444",
    "Accounts payable policy",
    "policy",
    "Accounts payable policy > 2. Price tolerance",
    "2",
    "2.1 A line passes price matching when the difference is within ±2% or $25.00, whichever is lower.",
)


@pytest.fixture
def mocked_kb(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    queries: list[str] = []

    async def fake_search(org_id: str, query: str, k: int = 6, **kw: Any) -> list[Chunk]:
        queries.append(query)
        return [C42, POLICY][:k]

    async def no_cache(*a: Any, **k: Any) -> None:
        return None

    monkeypatch.setattr(copilot, "search_kb", fake_search)
    monkeypatch.setattr(copilot, "cache_get", no_cache)
    monkeypatch.setattr(copilot, "cache_put", no_cache)
    return queries


def test_normalize_and_hash() -> None:
    assert normalize_question("  What does   clause 4.2 say?? ") == "what does clause 4.2 say"
    assert q_hash("What does clause 4.2 say?") == q_hash("what does clause 4.2 say")
    assert invoice_ref_in("Why is PS-88214 on hold?") == "PS-88214"
    assert invoice_ref_in("check PO-RS-1873") is None


async def test_retrieval_only_cites_clause_42(
    mocked_kb: list[str], fixture_gateway, no_network: None
) -> None:
    ans = await ask(ORG, "What is the contract price for shrimp?")
    assert ans.mode == "retrieval_only" and ans.cost_usd == 0 and ans.model is None
    assert ans.citations[0]["clause_ref"] == "4.2"
    assert ans.citations[0]["chunk_id"] == C42.chunk_id
    assert "$3.68" in ans.citations[0]["quote"]
    assert "§4.2" in ans.answer_md and "[1]" in ans.answer_md
    assert ans.notice and "off" in ans.notice
    d = ans.to_dict()
    assert d["cost_usd"] == "0" and d["mode"] == "retrieval_only"


async def test_retrieval_only_budget_notice(mocked_kb: list[str], store, monkeypatch) -> None:
    from app.ai.gateway import LlmGateway

    from .conftest import MemoryBudgetStore, make_settings

    gw = LlmGateway(
        make_settings(llm_mode="live", openai_api_key="sk"), MemoryBudgetStore(cap=Decimal("0.0001"))
    )
    ans = await ask(ORG, "What is the contract price for shrimp?", gateway=gw)
    assert ans.mode == "retrieval_only" and "budget" in (ans.notice or "")


async def test_retrieval_only_includes_exception_facts(mocked_kb, fixture_gateway, monkeypatch) -> None:
    async def fake_exc(org_id: str, ref: str) -> dict[str, Any]:
        assert ref == "PS-88214"
        return {
            "exception": {
                "type": "price_variance",
                "status": "open",
                "reason": "shrimp 12% over contract",
                "amount_at_risk": "88.00",
            },
            "invoice": {"invoice_number": "PS-88214", "vendor_name": "Protein Supplier", "total": "2847.60"},
            "recommendation": {
                "action": "short_pay",
                "pay_amount": "2759.60",
                "hold_amount": "88.00",
                "confidence": "0.940",
                "reasons": ["Goods were received in full."],
            },
            "latest_decision": None,
            "lines": [{"clause_ref": "4.2"}],
        }

    monkeypatch.setattr(copilot, "get_exception", fake_exc)
    ans = await answer_retrieval_only(ORG, "Why is PS-88214 on hold?")
    assert "pay $2,759.60, hold $88.00" in ans.answer_md
    assert "shrimp 12% over contract" in ans.answer_md
    assert "clause 4.2" in mocked_kb[-1]  # KB query is steered to the clause on the exception
    assert ans.citations[0]["clause_ref"] == "4.2"


def test_finalize_citations_renumbers() -> None:
    ctx = AgentCtx(org_id=ORG)
    ctx.ref_for(POLICY, "q")  # K1 never cited
    ctx.ref_for(C42, "shrimp price")  # K2
    body, cites = finalize_citations("Shrimp is $3.68/lb [K2]. Also [K2, K9]. Bogus [K7].", ctx)
    assert body == "Shrimp is $3.68/lb [1]. Also [1]. Bogus ."
    assert [c["n"] for c in cites] == [1] and cites[0]["clause_ref"] == "4.2"


def test_stream_rewriter_handles_split_refs() -> None:
    ctx = AgentCtx(org_id=ORG)
    ctx.ref_for(C42, "q")
    rw = _StreamRewriter(ctx)
    out = rw.feed("Price is $3.68 [") + rw.feed("K1") + rw.feed("] per lb") + rw.flush()
    assert out == "Price is $3.68 [1] per lb"


async def test_live_answer_with_tool_citations(mocked_kb, live_gateway, store, monkeypatch) -> None:
    from app.ai import runtime

    async def fake_run_agent(
        agent, input, meter, *, context: AgentCtx, max_turns: int, max_tokens: int, **kw
    ):
        assert max_tokens == 1500 and max_turns == 8
        assert {t.name for t in agent.tools} >= {"search_kb", "get_exception", "get_kpis"}
        context.tool_calls.append({"name": "search_kb", "args": {"query": "shrimp"}})
        context.ref_for(C42, "shrimp contract price")
        meter.add_agents_usage(
            SimpleNamespace(
                input_tokens=3000,
                output_tokens=120,
                requests=2,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            )
        )
        return SimpleNamespace(final_output="Clause 4.2 fixes shrimp at $3.68/lb [K1].")

    monkeypatch.setattr(runtime, "run_agent", fake_run_agent)
    ans = await ask(ORG, "What is the contract price for shrimp?")
    assert ans.mode == "live" and ans.answer_md.endswith("[1].")
    assert ans.citations[0]["clause_ref"] == "4.2"
    assert ans.cost_usd == Decimal("0.001392")
    assert ans.tool_calls == [{"name": "search_kb", "args": {"query": "shrimp"}}]


async def test_live_error_degrades(mocked_kb, live_gateway, monkeypatch) -> None:
    from app.ai import runtime

    async def broken(*a, **k):
        raise RuntimeError("upstream 500")

    monkeypatch.setattr(runtime, "run_agent", broken)
    ans = await ask(ORG, "What is the contract price for shrimp?")
    assert ans.mode == "retrieval_only" and "did not respond" in (ans.notice or "")


async def test_tool_call_cap() -> None:
    from app.ai.tools import _budget

    ctx = SimpleNamespace(context=AgentCtx(org_id=ORG, max_tool_calls=2))
    assert _budget(ctx, "a", {}) is None and _budget(ctx, "b", {}) is None
    assert "limit" in (_budget(ctx, "c", {}) or "")
    assert len(ctx.context.tool_calls) == 2


async def test_stream_events_retrieval_only(mocked_kb, fixture_gateway) -> None:
    events = [e async for e in stream_ask(ORG, "What is the contract price for shrimp?")]
    kinds = [e["event"] for e in events]
    assert kinds[0] == "status" and kinds[-1] == "done" and "token" in kinds and "citation" in kinds
    text = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert text == events[-1]["data"]["answer_md"]
    frame = sse(events[-1])
    assert frame.startswith("event: done\ndata: {") and frame.endswith("\n\n")


@needs_db
async def test_copilot_db_fts_path_and_cache(kb_org: str) -> None:
    ans = await ask(kb_org, "What is the contract price for shrimp?")
    assert ans.mode == "retrieval_only"
    assert ans.citations and ans.citations[0]["clause_ref"] == "4.2"
    assert "$3.68" in ans.citations[0]["quote"]
    await copilot.cache_put(kb_org, "What is the contract price for shrimp?", ans)
    hit = await ask(kb_org, "what is the contract price for SHRIMP")
    assert hit.mode == "cached" and hit.citations[0]["clause_ref"] == "4.2"
