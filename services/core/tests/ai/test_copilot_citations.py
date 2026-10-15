"""Ask Ledgic citations: ref-format tolerance, deterministic clause citations from data tools, streaming
parity, and cache hygiene. No live LLM calls: agent runs are faked and tools are monkeypatched."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai import copilot, tools
from app.ai.copilot import _StreamRewriter, ask, finalize_citations, q_hash, stream_ask
from app.ai.rag.retrieve import Chunk
from app.ai.tools import AgentCtx

ORG = "992e72b7-9d9b-5104-9051-f5ef581c99e0"
CONTRACT_ID = "55555555-5555-5555-5555-555555555555"
C42 = Chunk(
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
    "Protein Supplier — Vendor agreement 2026",
    "contract",
    "Protein Supplier — Vendor agreement 2026 > 4. Pricing > 4.2 Pricing: Shrimp 16/20 IQF",
    "4.2",
    "Shrimp 16/20 IQF 2lb × 10 is priced at **$3.68 per lb** for the Term.",
    contract_id=CONTRACT_ID,
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

PS_88214 = {
    "exception": {
        "exception_id": "7d0c9a52-3f0e-4b8e-9a51-0f2b8e6c1a11",
        "type": "price_variance",
        "status": "open",
        "reason": "Shrimp billed $4.12/lb vs contract $3.68/lb",
        "amount_at_risk": "88.00",
    },
    "invoice": {"invoice_number": "PS-88214", "vendor_name": "Protein Supplier", "total": "2847.60"},
    "recommendation": {
        "action": "short_pay",
        "pay_amount": "2759.60",
        "hold_amount": "88.00",
        "confidence": "0.940",
        "reasons": [],
    },
    "latest_decision": None,
    "lines": [
        {"line_no": 1, "description": "Salmon", "verdict": "matched", "clause_ref": "4.1", "contract_id": CONTRACT_ID},
        {
            "line_no": 2,
            "description": "Shrimp 16/20 IQF",
            "verdict": "price_variance",
            "clause_ref": "4.2",
            "contract_id": CONTRACT_ID,
        },
    ],
}


def _ctx(*chunks: Chunk) -> AgentCtx:
    ctx = AgentCtx(org_id=ORG)
    for c in chunks:
        ctx.ref_for(c, "q")
    return ctx


# ------------------------------------------------------------------------------------ ref formats (cause 2)
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Shrimp is $3.68/lb [K1].", "Shrimp is $3.68/lb [1]."),
        ("Shrimp is $3.68/lb [k1].", "Shrimp is $3.68/lb [1]."),
        ("Shrimp is $3.68/lb (K1).", "Shrimp is $3.68/lb [1]."),
        ("Shrimp is $3.68/lb 【K1】.", "Shrimp is $3.68/lb [1]."),
        ("Shrimp is $3.68/lb [K1 clause 4.2].", "Shrimp is $3.68/lb [1]."),
        ("Shrimp is $3.68/lb [K1, clause 4.2].", "Shrimp is $3.68/lb [1]."),
        ("Tolerance and price [K2][K1].", "Tolerance and price [1][2]."),
        ("Tolerance and price [K2; K1].", "Tolerance and price [1][2]."),
        ("Tolerance and price [K2 and K1].", "Tolerance and price [1][2]."),
    ],
)
def test_ref_variants_become_numbered_citations(raw: str, expected: str) -> None:
    body, cites = finalize_citations(raw, _ctx(C42, POLICY))
    assert body == expected
    assert cites and all(c["chunk_id"] in {C42.chunk_id, POLICY.chunk_id} for c in cites)


@pytest.mark.parametrize(
    "text",
    ["Within tolerance (2%).", "See clause (4.2) of the agreement.", "Footnote [1] stays.", "A [note] here."],
)
def test_non_refs_are_left_alone(text: str) -> None:
    body, cites = finalize_citations(text, _ctx(C42))
    assert body == text and cites == []


def test_unknown_refs_are_dropped_never_invented() -> None:
    body, cites = finalize_citations("Made up [K7] and (K9).", _ctx(C42))
    assert body == "Made up  and ." and cites == []


@pytest.mark.parametrize(
    "raw",
    [
        "Shrimp is $3.68/lb [K1 clause 4.2] and tolerance is 2% (K2).",
        "Both apply 【K2】[k1]. Again [K1, K2].",
        "Nothing cited (see policy) [note].",
    ],
)
def test_stream_rewriter_matches_finalize_char_by_char(raw: str) -> None:
    ctx = _ctx(C42, POLICY)
    rw = _StreamRewriter(ctx)
    streamed = "".join(rw.feed(ch) for ch in raw) + rw.flush()
    body, cites = finalize_citations(raw, _ctx(C42, POLICY))
    assert streamed == body
    assert rw.citations() == cites


# ------------------------------------------------------------------ get_exception-only answers (cause 1)
@pytest.fixture
def ps88214_tools(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str | None]]:
    lookups: list[tuple[str, str | None]] = []

    async def fake_get_exception(org_id: str, ref: str) -> dict[str, Any]:
        return json.loads(json.dumps(PS_88214))

    async def fake_clause_chunk(org_id: str, clause_ref: str, contract_id: str | None) -> Chunk | None:
        lookups.append((clause_ref, contract_id))
        return C42 if clause_ref == "4.2" else None

    monkeypatch.setattr(tools, "get_exception", fake_get_exception)
    monkeypatch.setattr(tools, "clause_chunk", fake_clause_chunk)
    return lookups


async def test_get_exception_registers_the_held_lines_clause(ps88214_tools) -> None:
    ctx = AgentCtx(org_id=ORG)
    out = json.loads(await tools.run_get_exception(ctx, "PS-88214"))
    assert ps88214_tools == [("4.2", CONTRACT_ID)]  # only the line that is actually held, not matched ones
    assert out["contract_clauses"] == [
        {"ref": "K1", "clause": "4.2", "title": C42.title, "text": C42.content}
    ]
    assert ctx.chunks["K1"] is C42 and ctx.data_tools_used


async def test_missing_clause_chunk_registers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_exception(org_id: str, ref: str) -> dict[str, Any]:
        return json.loads(json.dumps(PS_88214))

    async def none(*a: Any) -> None:
        return None

    monkeypatch.setattr(tools, "get_exception", fake_get_exception)
    monkeypatch.setattr(tools, "clause_chunk", none)
    ctx = AgentCtx(org_id=ORG)
    out = json.loads(await tools.run_get_exception(ctx, "PS-88214"))
    assert "contract_clauses" not in out and ctx.chunks == {}
    body, cites = finalize_citations("PS-88214 breaks clause 4.2.", ctx)
    assert cites == [] and body == "PS-88214 breaks clause 4.2."


@pytest.mark.parametrize(
    "answer",
    [
        "PS-88214 is on hold because shrimp was billed above the clause 4.2 contract price.",
        "PS-88214 is on hold: a price variance of $88.00 on shrimp.",  # names the invoice, not the clause
        "Exception 7d0c9a52-3f0e-4b8e-9a51-0f2b8e6c1a11 is a price variance.",  # raw id only, as seen live
    ],
)
async def test_answer_about_the_exception_cites_its_clause_without_a_k_ref(ps88214_tools, answer: str) -> None:
    ctx = AgentCtx(org_id=ORG)
    await tools.run_get_exception(ctx, "PS-88214")
    body, cites = finalize_citations(answer, ctx)
    assert [c["clause_ref"] for c in cites] == ["4.2"]
    assert body == answer + " [1]"


async def test_model_ref_to_the_clause_is_not_duplicated(ps88214_tools) -> None:
    ctx = AgentCtx(org_id=ORG)
    await tools.run_get_exception(ctx, "PS-88214")
    body, cites = finalize_citations("Held under clause 4.2 [K1].", ctx)
    assert body == "Held under clause 4.2 [1]." and len(cites) == 1


async def test_unrelated_answer_gets_no_clause_citation(ps88214_tools) -> None:
    ctx = AgentCtx(org_id=ORG)
    await tools.run_get_exception(ctx, "PS-88214")
    body, cites = finalize_citations("I can only help with accounts payable.", ctx)
    assert cites == [] and "[" not in body


# ---------------------------------------------------------------------- live + streaming parity (paths)
def _usage() -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=3000, output_tokens=120, requests=2, input_tokens_details=SimpleNamespace(cached_tokens=0)
    )


ANSWER = "PS-88214 is on hold: shrimp was billed above the contract price (K1 clause 4.2)."


@pytest.fixture
def no_cache(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    writes: list[str] = []

    async def miss(*a: Any, **k: Any) -> None:
        return None

    async def put(org_id: str, question: str, ans: Any) -> None:
        writes.append(question)

    monkeypatch.setattr(copilot, "cache_get", miss)
    monkeypatch.setattr(copilot, "cache_put", put)
    return writes


async def test_live_and_stream_give_identical_citations(
    ps88214_tools, no_cache, live_gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents import RawResponsesStreamEvent, Runner

    from app.ai import runtime

    async def fake_run_agent(agent, input, meter, *, context: AgentCtx, **kw):
        await tools.run_get_exception(context, "PS-88214")
        meter.add_agents_usage(_usage())
        return SimpleNamespace(final_output=ANSWER)

    class FakeStream:
        def __init__(self, context: AgentCtx) -> None:
            self.ctx = context
            self.final_output = ANSWER
            self.context_wrapper = SimpleNamespace(usage=_usage())

        async def stream_events(self):
            await tools.run_get_exception(self.ctx, "PS-88214")
            for i in range(0, len(ANSWER), 7):
                delta = SimpleNamespace(type="response.output_text.delta", delta=ANSWER[i : i + 7])
                yield RawResponsesStreamEvent(data=delta)

    monkeypatch.setattr(runtime, "run_agent", fake_run_agent)
    monkeypatch.setattr(Runner, "run_streamed", lambda agent, input, *, context, **kw: FakeStream(context))

    live = await ask(ORG, "Why is PS-88214 on hold?")
    events = [e async for e in stream_ask(ORG, "Why is PS-88214 on hold?")]
    done = events[-1]["data"]
    streamed = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    chips = [e["data"] for e in events if e["event"] == "citation"]

    assert live.mode == "live" and done["mode"] == "live"
    assert live.answer_md == done["answer_md"] == streamed
    assert live.citations == done["citations"] == chips
    assert [c["clause_ref"] for c in chips] == ["4.2"] and "[1]" in streamed
    assert no_cache == []  # data-tool answers are never cached


OTHER_PAGE = {"invoice_id": "0f1e2d3c-0000-4000-8000-000000000001"}  # the invoice open on /match


@pytest.mark.parametrize(
    ("question", "keeps_page"),
    [("Why is PS-88214 on hold?", False), ("Why is this invoice on hold?", True)],
)
def test_invoice_named_in_the_question_beats_the_page_context(question: str, keeps_page: bool) -> None:
    assert copilot.scoped_context(question, OTHER_PAGE) == (OTHER_PAGE if keeps_page else None)


async def test_live_and_stream_ignore_the_page_when_the_question_names_an_invoice(
    ps88214_tools, no_cache, live_gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents import Runner

    from app.ai import runtime

    inputs: list[str] = []

    async def fake_run_agent(agent, input, meter, *, context: AgentCtx, **kw):
        inputs.append(input)
        meter.add_agents_usage(_usage())
        return SimpleNamespace(final_output=ANSWER)

    class FakeStream:
        final_output = ANSWER
        context_wrapper = SimpleNamespace(usage=_usage())

        async def stream_events(self):
            return
            yield

    def fake_streamed(agent, input, *, context, **kw):
        inputs.append(input)
        return FakeStream()

    monkeypatch.setattr(runtime, "run_agent", fake_run_agent)
    monkeypatch.setattr(Runner, "run_streamed", fake_streamed)

    await ask(ORG, "Why is PS-88214 on hold?", OTHER_PAGE)
    [e async for e in stream_ask(ORG, "Why is PS-88214 on hold?", OTHER_PAGE)]
    await ask(ORG, "Why is this invoice on hold?", OTHER_PAGE)

    assert len(inputs) == 3
    assert all("looking at" not in i for i in inputs[:2])
    assert OTHER_PAGE["invoice_id"] in inputs[2]


async def test_retrieval_only_looks_up_the_named_invoice_not_the_page(
    real_kb: list[Chunk], fixture_gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    refs: list[str] = []

    async def exc(org_id: str, ref: str) -> dict[str, Any]:
        refs.append(ref)
        return json.loads(json.dumps(PS_88214))

    monkeypatch.setattr(copilot, "get_exception", exc)
    ans = await ask(ORG, "Why is PS-88214 on hold?", OTHER_PAGE)
    assert refs == ["PS-88214"]
    assert ans.citations[0]["clause_ref"] == "4.2"


# ------------------------------------------------------------------------------------- cache (cause 3)
async def test_uncited_or_data_answers_are_not_cached(ps88214_tools, no_cache, live_gateway, monkeypatch) -> None:
    from app.ai import runtime

    outputs = iter(["Shrimp is $3.68/lb.", "Shrimp is $3.68/lb [K1]."])

    async def kb_only(agent, input, meter, *, context: AgentCtx, **kw):
        context.ref_for(C42, "shrimp")
        meter.add_agents_usage(_usage())
        return SimpleNamespace(final_output=next(outputs))

    monkeypatch.setattr(runtime, "run_agent", kb_only)
    first = await ask(ORG, "What is the contract price for shrimp?")
    assert first.citations == [] and no_cache == []  # an uncited answer is never frozen into the cache
    second = await ask(ORG, "What is the contract price for shrimp?")
    assert second.citations and no_cache == ["What is the contract price for shrimp?"]


async def test_refresh_skips_the_cache_read_but_keeps_the_write_rules(
    ps88214_tools, live_gateway, monkeypatch
) -> None:
    from app.ai import runtime

    reads: list[str] = []
    writes: list[str] = []

    async def get(org_id: str, question: str) -> None:
        reads.append(question)

    async def put(org_id: str, question: str, ans: Any) -> None:
        writes.append(question)

    async def data_answer(agent, input, meter, *, context: AgentCtx, **kw):
        await tools.run_get_exception(context, "PS-88214")
        meter.add_agents_usage(_usage())
        return SimpleNamespace(final_output="PS-88214 is held.")

    monkeypatch.setattr(copilot, "cache_get", get)
    monkeypatch.setattr(copilot, "cache_put", put)
    monkeypatch.setattr(runtime, "run_agent", data_answer)
    ans = await ask(ORG, "Why is PS-88214 on hold?", refresh=True)
    assert reads == [] and writes == [] and ans.citations[0]["clause_ref"] == "4.2"


def test_cache_key_is_versioned() -> None:
    import hashlib

    legacy = hashlib.sha256(b"why is ps-88214 on hold").hexdigest()
    assert q_hash("Why is PS-88214 on hold?") != legacy  # pre-fix (poisoned) rows can no longer be hit


async def test_precompute_uses_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import admin

    calls: list[dict[str, Any]] = []

    async def fake_ask(org: str, q: str, **kw: Any) -> Any:
        calls.append(kw)
        return SimpleNamespace()

    monkeypatch.setattr(copilot, "ask", fake_ask)
    puts: list[str] = []

    async def put(*a: Any) -> None:
        puts.append("x")

    monkeypatch.setattr(copilot, "cache_put", put)
    await admin._precompute_copilot(ORG)
    assert calls and all(kw == {"refresh": True} for kw in calls) and puts == []


# ------------------------------------------------------------- the panel's suggested questions, real KB
def _corpus() -> list[Chunk]:
    """Every chunk of the real knowledge base (tools/corpus/kb), chunked by the real chunker."""
    from app.ai.rag.chunker import chunk_markdown, parse_front_matter
    from app.ai.rag.index import _DIR_KIND, default_paths, fill_placeholders, kb_dir

    out: list[Chunk] = []
    for path in default_paths():
        doc = parse_front_matter(path.read_text(encoding="utf-8"))
        rel = path.resolve().relative_to(kb_dir().resolve())
        kind = doc.meta.get("kind") or _DIR_KIND.get(rel.parts[0], "policy")
        title = doc.meta.get("title") or path.stem
        for c in chunk_markdown(fill_placeholders(doc.body, None), title):
            out.append(
                Chunk(f"{rel.as_posix()}#{c.ord}", rel.as_posix(), title, kind, c.heading_path, c.clause_ref,
                      c.content, contract_id=CONTRACT_ID if kind == "contract" else None)
            )
    return out


@pytest.fixture
def real_kb(monkeypatch: pytest.MonkeyPatch) -> list[Chunk]:
    """`search_kb` over the real corpus: clause pinning plus the production lexical reranker."""
    from app.ai.rag import retrieve

    corpus = _corpus()

    async def search(org_id: str, query: str, k: int = 6, **kw: Any) -> list[Chunk]:
        pinned = []
        if m := retrieve._CLAUSE_Q.search(query):
            pinned = [c for c in corpus if c.clause_ref == m.group(1) and c.kind == "contract"][:3]
        ranked = [c for c in retrieve.rerank(query, corpus) if c not in pinned]
        return (pinned + ranked)[:k]

    async def exc(org_id: str, ref: str) -> dict[str, Any]:
        return json.loads(json.dumps(PS_88214))

    async def queue(org_id: str, status: str = "open", limit: int = 20) -> dict[str, Any]:
        return {"exceptions": [], "count": 0}

    async def miss(*a: Any, **k: Any) -> None:
        return None

    monkeypatch.setattr(copilot, "search_kb", search)
    monkeypatch.setattr(copilot, "get_exception", exc)
    monkeypatch.setattr(copilot, "list_exceptions", queue)
    monkeypatch.setattr(copilot, "cache_get", miss)
    return corpus


@pytest.mark.parametrize(
    ("question", "kind", "clause"),
    [
        ("Why is PS-88214 on hold?", "contract", "4.2"),
        ("What does clause 4.2 of the Protein Supplier agreement say about shrimp?", "contract", "4.2"),
        ("What is our price-variance tolerance?", "policy", None),
        ("How is the touchless rate calculated?", "policy", None),
    ],
)
async def test_suggested_kb_questions_cite_the_right_source(
    real_kb: list[Chunk], fixture_gateway, question: str, kind: str, clause: str | None
) -> None:
    ans = await ask(ORG, question)
    assert ans.citations, ans.answer_md
    first = ans.citations[0]
    assert first["kind"] == kind and (clause is None or first["clause_ref"] == clause)
    assert "[1]" in ans.answer_md
    ids = {c.chunk_id for c in real_kb}
    assert all(c["chunk_id"] in ids for c in ans.citations)  # every chip is a real KB chunk


async def test_queue_question_cites_only_real_chunks(real_kb: list[Chunk], fixture_gateway) -> None:
    ans = await ask(ORG, "Which exceptions are blocking payments right now?")
    assert "no open exceptions" in ans.answer_md
    ids = {c.chunk_id for c in real_kb}
    assert all(c["chunk_id"] in ids for c in ans.citations)


@pytest.mark.parametrize(
    ("answer", "cited"),
    [
        ("Shrimp is priced under clause 4.2 of the agreement.", True),
        ("See §4.2 for the shrimp price.", True),
        ("Clause 4.25 covers something else.", False),
        ("Subclause 4.2 is unrelated wording.", False),
    ],
)
async def test_clause_anchor_matches_the_exact_clause(ps88214_tools, answer: str, cited: bool) -> None:
    ctx = AgentCtx(org_id=ORG)
    await tools.run_get_exception(ctx, "PS-88214")
    ctx.clause_anchors["K1"] = []  # isolate the clause match from the invoice-number match
    _, cites = finalize_citations(answer, ctx)
    assert bool(cites) is cited


@pytest.mark.parametrize("hostile", ["(9." + "99." * 5000, "(" + "9" * 20000, "(K" + "99K" * 5000])
def test_ref_parsing_is_linear_on_hostile_model_output(hostile: str) -> None:
    import time

    start = time.perf_counter()
    finalize_citations(hostile, _ctx(C42))
    assert time.perf_counter() - start < 0.5  # CodeQL py/redos: no catastrophic backtracking
