"""Ask Ledgic — RAG copilot over contracts, AP policy, vendor notes and live AP data (DECISIONS D10).

Order of service for a question:
1. `copilot_cache` (org, sha256(normalized question)) → mode `cached` ($0). Entries for questions that
   name an invoice are skipped once that invoice's exceptions/decisions changed after caching.
2. LLM agent with read-only tools (≤ 6 tool calls, ≤ 1.5k output tokens) → mode `live`.
3. Budget spent / fixture mode / LLM error → mode `retrieval_only`: a deterministic answer built from
   the top knowledge-base chunks (verbatim quotes) plus the deterministic exception facts. No prose is
   generated, so nothing can be invented.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from agents import Agent

from app.domain.money import fmt_conf, fmt_money

from .gateway import BudgetExceeded, LlmGateway, LlmUnavailable, get_gateway
from .rag.retrieve import Chunk, search_kb
from .tools import (
    COPILOT_TOOLS,
    MAX_TOOL_CALLS,
    AgentCtx,
    get_exception,
    get_invoice_summary,
    list_exceptions,
)

log = logging.getLogger("ledgic.ai.copilot")

MAX_OUTPUT_TOKENS = 1500
MAX_QUESTION_CHARS = 500
EST_INPUT_TOKENS = 14000  # budget reservation upper bound across the agent's turns

# The first five are the web panel's suggestions (apps/web/components/copilot/CopilotPanel.tsx) verbatim.
SUGGESTED_QUESTIONS = (
    "Why is PS-88214 on hold?",
    "What does clause 4.2 of the Protein Supplier agreement say about shrimp?",
    "What is our price-variance tolerance?",
    "Which exceptions are blocking payments right now?",
    "How is the touchless rate calculated?",
    "Who can release a fraud hold?",
    "What is the contract price for shrimp?",
)

# Questions about the current queue are never served from (or written to) the cache.
_LIVE_DATA = re.compile(
    r"\b(right now|currently|today|open exceptions|exceptions (?:are|is)|blocking)\b", re.IGNORECASE
)


def is_live_data_question(q: str) -> bool:
    return bool(_LIVE_DATA.search(q))


INSTRUCTIONS = f"""You are Ask Ledgic, the assistant inside an accounts-payable automation console used by
AP clerks, AP managers and controllers of a multi-location restaurant group.

Answer ONLY accounts-payable questions (invoices, exceptions, vendors, contracts, purchase orders,
receipts, AP policy, approvals, month-end close, Ledgic KPIs). For anything else, say briefly that you
can only help with accounts payable.

Ground every statement in tool results:
- Use `search_kb` for contracts, policy and vendor notes; use `get_exception` / `get_invoice` /
  `vendor_history` / `get_po_grn` / `get_kpis` for live data. Prefer one or two well-aimed calls;
  you have at most {MAX_TOOL_CALLS} tool calls.
- Cite every knowledge-base fact with its ref in square brackets, e.g. "[K1]", right after the sentence.
  Name invoices, POs and clauses explicitly (e.g. "PS-88214", "PO-RS-1873", "clause 4.2").
- Never invent or compute new numbers. Every amount, price, percentage, date or count you state must
  appear verbatim in a tool result. If the tools do not contain the answer, say what is missing.
- Recommendations come from Ledgic's deterministic rules; report them, do not override them, and do
  not approve, reject or decide anything yourself.

Style: concise Markdown, lead with the direct answer in one or two sentences, then at most a few
bullets. Money as $1,234.56. No preamble, no closing offers."""


@dataclass
class CopilotAnswer:
    answer_md: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "retrieval_only"  # live | cached | retrieval_only
    model: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: Decimal = Decimal(0)
    notice: str | None = None  # why the answer is retrieval-only, for the UI banner

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cost_usd"] = str(self.cost_usd)
        return d


def build_agent() -> Agent[AgentCtx]:
    return Agent[AgentCtx](name="Ask Ledgic", instructions=INSTRUCTIONS, tools=list(COPILOT_TOOLS))


# --------------------------------------------------------------------------------------- normalization
def normalize_question(q: str) -> str:
    q = re.sub(r"\s+", " ", q.strip().lower())
    return q.rstrip(" ?!.")


def q_hash(q: str) -> str:
    return hashlib.sha256(normalize_question(q).encode("utf-8")).hexdigest()


_INVOICE_REF = re.compile(r"(?<![\w-])([A-Za-z]{2,4}-\d{3,7})(?![\w-])")


def invoice_ref_in(text: str) -> str | None:
    m = _INVOICE_REF.search(text)
    return m.group(1).upper() if m else None


# --------------------------------------------------------------------------------------- citations
def citation_payload(n: int, c: Chunk, query: str | None) -> dict[str, Any]:
    snippet = c.snippet(query)
    return {
        "n": n,
        "chunk_id": c.chunk_id,
        "document_id": c.document_id,
        "title": c.title,
        "kind": c.kind,
        "clause_ref": c.clause_ref,
        "quote": snippet,
        "snippet": snippet,
    }


_REF = re.compile(r"\[(K\d+(?:\s*,\s*K\d+)*)\]")


def finalize_citations(text: str, ctx: AgentCtx) -> tuple[str, list[dict[str, Any]]]:
    """Renumber `[K3]` refs to `[1]`, `[2]` in order of first use; drop refs the tools never returned."""
    order: dict[str, int] = {}

    def repl(m: re.Match[str]) -> str:
        out = []
        for ref in (r.strip() for r in m.group(1).split(",")):
            if ref not in ctx.chunks:
                continue
            if ref not in order:
                order[ref] = len(order) + 1
            out.append(f"[{order[ref]}]")
        return "".join(out)

    body = _REF.sub(repl, text)
    cites = [citation_payload(n, ctx.chunks[ref], ctx.query_for_ref.get(ref)) for ref, n in order.items()]
    return body, cites


class _StreamRewriter:
    """Rewrites `[K1]` refs on the fly while streaming (holds back an unfinished `[...`)."""

    def __init__(self, ctx: AgentCtx) -> None:
        self.ctx = ctx
        self.order: dict[str, int] = {}
        self.pending = ""

    def feed(self, text: str) -> str:
        buf = self.pending + text
        cut = buf.rfind("[")
        if cut != -1 and "]" not in buf[cut:] and len(buf) - cut < 24:
            self.pending, buf = buf[cut:], buf[:cut]
        else:
            self.pending = ""
        return self._sub(buf)

    def flush(self) -> str:
        out, self.pending = self._sub(self.pending), ""
        return out

    def _sub(self, s: str) -> str:
        def repl(m: re.Match[str]) -> str:
            out = []
            for ref in (r.strip() for r in m.group(1).split(",")):
                if ref in self.ctx.chunks:
                    self.order.setdefault(ref, len(self.order) + 1)
                    out.append(f"[{self.order[ref]}]")
            return "".join(out)

        return _REF.sub(repl, s)


# --------------------------------------------------------------------------------------- cache
async def cache_get(org_id: str, question: str) -> CopilotAnswer | None:
    from app.db.pool import connection

    try:
        async with connection() as conn:
            cur = await conn.execute(
                "select answer, created_at from public.copilot_cache where org_id = %s and q_hash = %s",
                (org_id, q_hash(question)),
            )
            row = await cur.fetchone()
            if row is None or is_live_data_question(question):
                return None
            ref = invoice_ref_in(question)
            if ref:
                cur = await conn.execute(
                    """
                    select exists (
                      select 1 from public.exceptions e
                      join public.invoices i on i.id = e.invoice_id
                      left join public.approvals a on a.exception_id = e.id
                      where i.org_id = %(org)s
                        and i.invoice_number_norm = upper(regexp_replace(%(ref)s, '[^A-Za-z0-9]', '', 'g'))
                        and (e.opened_at > %(at)s or e.resolved_at > %(at)s or a.decided_at > %(at)s)
                    ) as stale
                    """,
                    {"org": org_id, "ref": ref, "at": row["created_at"]},
                )
                stale = await cur.fetchone()
                if stale and stale["stale"]:
                    return None
            await conn.rollback()
    except Exception as exc:
        log.warning("copilot cache read failed: %s", type(exc).__name__)
        return None
    a = row["answer"] if isinstance(row["answer"], dict) else json.loads(row["answer"])
    return CopilotAnswer(
        answer_md=a.get("answer_md", ""),
        citations=a.get("citations", []),
        mode="cached",
        model=a.get("model"),
        tool_calls=a.get("tool_calls", []),
        cost_usd=Decimal(0),
        notice=a.get("notice"),
    )


async def cache_put(org_id: str, question: str, ans: CopilotAnswer) -> None:
    from app.db.pool import connection

    if is_live_data_question(question):
        return
    payload = {
        "answer_md": ans.answer_md,
        "citations": ans.citations,
        "mode": ans.mode,
        "model": ans.model,
        "tool_calls": ans.tool_calls,
        "notice": ans.notice,
    }
    try:
        async with connection() as conn:
            await conn.execute(
                "insert into public.copilot_cache (org_id, q_hash, question, answer)"
                " values (%s, %s, %s, %s::jsonb)"
                " on conflict (org_id, q_hash) do update set question = excluded.question,"
                " answer = excluded.answer, created_at = now()",
                (org_id, q_hash(question), question.strip(), json.dumps(payload)),
            )
            await conn.commit()
    except Exception as exc:
        log.warning("copilot cache write failed: %s", type(exc).__name__)


# --------------------------------------------------------------------------------------- retrieval-only
_NOTICES = {
    "budget": "Today's AI budget is spent, so this answer quotes the knowledge base directly.",
    "fixture": "AI answers are off in this environment, so this answer quotes the knowledge base directly.",
    "no_key": "No AI key is configured, so this answer quotes the knowledge base directly.",
    "error": "The AI service did not respond, so this answer quotes the knowledge base directly.",
}


def _facts_md(ex: dict[str, Any]) -> list[str]:
    e, inv, rec = ex.get("exception") or {}, ex.get("invoice") or {}, ex.get("recommendation")
    out: list[str] = []
    head = f"**{inv.get('invoice_number') or 'Invoice'}**"
    if inv.get("vendor_name"):
        head += f" from {inv['vendor_name']}"
    if inv.get("total"):
        head += f" ({fmt_money(inv['total'])})"
    label = str(e.get("type", "")).replace("_", " ")
    status = "resolved" if e.get("status") == "resolved" else f"{e.get('status', 'open')}"
    out.append(f"{head} has a **{label}** exception ({status}): {e.get('reason', '')}.")
    if e.get("amount_at_risk") and Decimal(str(e["amount_at_risk"])) > 0:
        out.append(f"Amount at risk: {fmt_money(e['amount_at_risk'])}.")
    if rec:
        line = f"Ledgic's deterministic recommendation is **{str(rec['action']).replace('_', ' ')}**"
        if rec.get("pay_amount") is not None and rec.get("hold_amount") is not None:
            line += f": pay {fmt_money(rec['pay_amount'])}, hold {fmt_money(rec['hold_amount'])}"
        line += f" (confidence {fmt_conf(rec['confidence'])})."
        out.append(line)
        out += [f"- {r}" for r in rec.get("reasons") or []]
    d = ex.get("latest_decision")
    if d:
        who = d.get("actor") or "a reviewer"
        out.append(f"Decision: {str(d['action']).replace('_', ' ')} by {who}.")
    return out


_BLOCKING = {"duplicate", "new_vendor_screen"}


def _queue_md(rows: list[dict[str, Any]]) -> list[str]:
    """Open exceptions; duplicate and new-vendor (fraud) holds block payment entirely."""
    if not rows:
        return ["There are no open exceptions right now."]
    blocking = [r for r in rows if r["type"] in _BLOCKING]
    out = [
        f"**{len(blocking)} of {len(rows)} open exceptions block payment** (suspected duplicates and "
        "new-vendor fraud screens hold the whole invoice)."
    ]
    for r in blocking[:8]:
        out.append(
            f"- {r.get('invoice_number') or 'Invoice'} · {r.get('vendor_name') or ''} · "
            f"{str(r['type']).replace('_', ' ')} · {fmt_money(r['amount_at_risk'])} at risk — {r['reason']}"
        )
    others = len(rows) - len(blocking)
    if others:
        out.append(f"The other {others} open exceptions (price, quantity, PO) hold only the disputed amount.")
    return out


async def answer_retrieval_only(
    org_id: str, question: str, context: dict[str, Any] | None = None, reason: str = "fixture"
) -> CopilotAnswer:
    tool_calls: list[dict[str, Any]] = []
    facts: list[str] = []
    query = question
    ref = (context or {}).get("exception_id") or (context or {}).get("invoice_id") or invoice_ref_in(question)
    if ref:
        tool_calls.append({"name": "get_exception", "args": {"ref": ref}})
        ex = await get_exception(org_id, str(ref))
        if "error" not in ex:
            facts = _facts_md(ex)
            clauses = {ln.get("clause_ref") for ln in ex.get("lines", []) if ln.get("clause_ref")}
            query = " ".join(
                [question, ex["exception"].get("reason") or ""] + [f"clause {c}" for c in clauses]
            )
        elif ex.get("invoice"):
            inv = ex["invoice"]
            facts = [
                f"**{inv.get('invoice_number')}** from {inv.get('vendor_name')} has no exceptions "
                f"(status {inv.get('status')})."
            ]
        else:
            summary = await get_invoice_summary(org_id, str(ref))
            if "error" in summary:
                facts = [f"I couldn't find {ref} in this organization."]
    if not ref and is_live_data_question(question) and "exception" in question.lower():
        tool_calls.append({"name": "list_exceptions", "args": {"status": "open"}})
        facts = _queue_md((await list_exceptions(org_id, "open", 50))["exceptions"])
    tool_calls.append({"name": "search_kb", "args": {"query": query}})
    chunks = await search_kb(org_id, query, k=4)

    lines = list(facts)
    cites: list[dict[str, Any]] = []
    top = chunks[:3]
    if top:
        if facts:
            lines.append("")
        lines.append("**From the knowledge base**" if facts else "Here is what the knowledge base says:")
        for n, c in enumerate(top, start=1):
            cite = citation_payload(n, c, question)
            cites.append(cite)
            where = c.title + (f" §{c.clause_ref}" if c.clause_ref else "")
            lines.append(f"- **{where}** — “{cite['quote']}” [{n}]")
    elif not facts:
        lines.append("I couldn't find anything in the knowledge base about that.")
    notice = _NOTICES.get(reason, _NOTICES["fixture"])
    return CopilotAnswer(
        "\n".join(lines).strip(), cites, "retrieval_only", None, tool_calls, Decimal(0), notice
    )


# --------------------------------------------------------------------------------------- live
def _input(question: str, context: dict[str, Any] | None) -> str:
    ctx_lines = []
    if context and context.get("exception_id"):
        ctx_lines.append(f"The user is looking at exception {context['exception_id']}.")
    if context and context.get("invoice_id"):
        ctx_lines.append(f"The user is looking at invoice {context['invoice_id']}.")
    return "\n".join([*ctx_lines, f"Question: {question}"])


def _reason_for(exc: BaseException, gw: LlmGateway) -> str:
    if isinstance(exc, BudgetExceeded):
        return "budget"
    if isinstance(exc, LlmUnavailable):
        return "fixture" if gw.mode != "live" else "no_key"
    return "error"


async def ask(
    org_id: str,
    question: str,
    context: dict[str, Any] | None = None,
    api_key: str | None = None,
    *,
    use_cache: bool = True,
    gateway: LlmGateway | None = None,
) -> CopilotAnswer:
    question = question.strip()[:MAX_QUESTION_CHARS]
    if use_cache and not context:
        hit = await cache_get(org_id, question)
        if hit is not None:
            return hit
    gw = gateway or get_gateway()
    if not gw.can_call(api_key):
        return await answer_retrieval_only(
            org_id, question, context, "fixture" if gw.mode != "live" else "no_key"
        )
    try:
        ans, ctx = await _ask_live(org_id, question, context, api_key, gw)
    except Exception as exc:
        if not isinstance(exc, BudgetExceeded | LlmUnavailable):
            log.warning("copilot live answer failed: %s", type(exc).__name__)
        return await answer_retrieval_only(org_id, question, context, _reason_for(exc, gw))
    if use_cache and not context and not ctx.data_tools_used:
        await cache_put(org_id, question, ans)  # KB-only answers are stable until the KB changes
    return ans


async def _ask_live(
    org_id: str, question: str, context: dict[str, Any] | None, api_key: str | None, gw: LlmGateway
) -> tuple[CopilotAnswer, AgentCtx]:
    from .runtime import run_agent

    ctx = AgentCtx(org_id=org_id, api_key=api_key)
    async with gw.metered(
        purpose="copilot",
        org_id=org_id,
        est_input_tokens=EST_INPUT_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS * 2,
        api_key=api_key,
    ) as meter:
        result = await run_agent(
            build_agent(),
            _input(question, context),
            meter,
            max_tokens=MAX_OUTPUT_TOKENS,
            max_turns=MAX_TOOL_CALLS + 2,
            context=ctx,
            workflow="ledgic.copilot",
        )
    body, cites = finalize_citations(str(result.final_output), ctx)
    return CopilotAnswer(body, cites, "live", meter.model, ctx.tool_calls, meter.cost_usd), ctx


# --------------------------------------------------------------------------------------- streaming
def sse(event: dict[str, Any]) -> str:
    """Format one `{"event", "data"}` dict as a Server-Sent Events frame."""
    return f"event: {event['event']}\ndata: {json.dumps(event['data'], default=str)}\n\n"


async def _emit_answer(ans: CopilotAnswer) -> AsyncIterator[dict[str, Any]]:
    yield {"event": "status", "data": {"step": "answering"}}
    for piece in re.findall(r"\S+\s*|\s+", ans.answer_md):
        yield {"event": "token", "data": {"text": piece}}
    for c in ans.citations:
        yield {"event": "citation", "data": c}
    yield {"event": "done", "data": ans.to_dict()}


async def stream_ask(
    org_id: str,
    question: str,
    context: dict[str, Any] | None = None,
    api_key: str | None = None,
    *,
    gateway: LlmGateway | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-ready events per contracts/core-api.md: status, token, citation, done (or error).
    Format each with `sse(event)`."""
    from agents import RawResponsesStreamEvent, RunItemStreamEvent, Runner

    from .runtime import run_config

    question = question.strip()[:MAX_QUESTION_CHARS]
    yield {"event": "status", "data": {"step": "retrieving"}}
    if not context:
        hit = await cache_get(org_id, question)
        if hit is not None:
            async for ev in _emit_answer(hit):
                yield ev
            return
    gw = gateway or get_gateway()
    if not gw.can_call(api_key):
        ans = await answer_retrieval_only(
            org_id, question, context, "fixture" if gw.mode != "live" else "no_key"
        )
        async for ev in _emit_answer(ans):
            yield ev
        return

    ctx = AgentCtx(org_id=org_id, api_key=api_key)
    rewriter = _StreamRewriter(ctx)
    streamed_any = False
    parts: list[str] = []
    try:
        async with gw.metered(
            purpose="copilot",
            org_id=org_id,
            est_input_tokens=EST_INPUT_TOKENS,
            max_output_tokens=MAX_OUTPUT_TOKENS * 2,
            api_key=api_key,
        ) as meter:
            result = Runner.run_streamed(
                build_agent(),
                _input(question, context),
                context=ctx,
                max_turns=MAX_TOOL_CALLS + 2,
                run_config=run_config(meter, max_tokens=MAX_OUTPUT_TOKENS, workflow="ledgic.copilot"),
            )
            try:
                async for ev in result.stream_events():
                    if isinstance(ev, RunItemStreamEvent) and ev.name == "tool_called":
                        name = getattr(ev.item.raw_item, "name", None)
                        yield {"event": "status", "data": {"step": "calling_tool", "tool": name}}
                    elif (
                        isinstance(ev, RawResponsesStreamEvent)
                        and ev.data.type == "response.output_text.delta"
                    ):
                        text = rewriter.feed(ev.data.delta)
                        if text:
                            if not streamed_any:
                                yield {"event": "status", "data": {"step": "answering"}}
                            streamed_any = True
                            parts.append(text)
                            yield {"event": "token", "data": {"text": text}}
            finally:
                meter.add_agents_usage(result.context_wrapper.usage)
        tail = rewriter.flush()
        if tail:
            yield {"event": "token", "data": {"text": tail}}
        body, cites = finalize_citations(str(result.final_output), ctx)
        ans = CopilotAnswer(body, cites, "live", meter.model, ctx.tool_calls, meter.cost_usd)
        for c in cites:
            yield {"event": "citation", "data": c}
        yield {"event": "done", "data": ans.to_dict()}
    except Exception as exc:
        log.warning("copilot stream failed: %s", type(exc).__name__)
        if streamed_any:
            yield {
                "event": "error",
                "data": {
                    "code": "LLM_BAD_OUTPUT",
                    "message": "The answer was interrupted.",
                    "retryable": True,
                },
            }
            return
        ans = await answer_retrieval_only(org_id, question, context, _reason_for(exc, gw))
        async for ev in _emit_answer(ans):
            yield ev
