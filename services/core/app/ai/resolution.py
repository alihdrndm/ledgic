"""Resolution agent: drafts a vendor notice or an internal explanation for an exception (DECISIONS D9).

"LLM reads, never decides": the agent gets the deterministic recommendation and match facts as input
and may call read-only tools (contract-clause RAG, vendor history, PO/GRN). A money guard then extracts
every money figure from the draft; each must equal a figure in the allowed set (recommendation
pay/hold, invoice/PO amounts, line amounts and unit prices, prior short-pays). Any other figure →
the LLM draft is rejected and the deterministic template draft is stored instead.

Modes stored in `exception_drafts.mode`: `live` (LLM draft that passed the guard) or `recorded`
(recorded hero draft or deterministic template — fixture mode, budget spent, LLM error, guard reject).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from agents import Agent
from pydantic import BaseModel

from app.domain.money import fmt_money, fmt_qty, fmt_unit_price
from app.domain.templates import MONTHS

from .gateway import LlmGateway, get_gateway
from .paths import heroes_dir
from .rag.retrieve import Chunk, search_kb
from .tools import RESOLUTION_TOOLS, AgentCtx, get_exception, get_po_grn, vendor_history

log = logging.getLogger("ledgic.ai.resolution")

PROMPT_VERSION = "r-1"
MAX_OUTPUT_TOKENS = 900
EST_INPUT_TOKENS = 9000
KINDS = ("vendor_notice", "explanation")

# ------------------------------------------------------------------------------------------ money guard
_MONEY = re.compile(
    r"(?:\$|\bUSD\s?)\s?(?P<a>-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    r"|(?P<b>-?\d{1,3}(?:,\d{3})*(?:\.\d{2}))\s?(?:USD|dollars)\b",
    re.IGNORECASE,
)
_Q = Decimal("0.0001")


def _norm(v: Any) -> Decimal | None:
    try:
        return Decimal(str(v).replace(",", "").replace("$", "").strip()).quantize(_Q)
    except (InvalidOperation, ValueError):
        return None


def money_figures(text: str) -> list[str]:
    """Every money figure in `text`, as written (without `$`/`USD`)."""
    return [m.group("a") or m.group("b") for m in _MONEY.finditer(text)]


@dataclass(frozen=True)
class GuardResult:
    passed: bool
    figures: list[str]
    rejected: list[str]


def money_guard(text: str, allowed: set[Decimal]) -> GuardResult:
    figs = money_figures(text)
    bad = [f for f in figs if _norm(f) not in allowed]
    return GuardResult(not bad, [str(_norm(f).normalize()) if _norm(f) is not None else f for f in figs], bad)


# ------------------------------------------------------------------------------------------ facts
@dataclass
class DraftFacts:
    org_id: str
    exception: dict[str, Any]
    invoice: dict[str, Any]
    recommendation: dict[str, Any] | None
    lines: list[dict[str, Any]]
    po: dict[str, Any] | None
    prior_short_pays: list[dict[str, Any]]
    contract_chunks: list[Chunk] = field(default_factory=list)

    @property
    def failing_lines(self) -> list[dict[str, Any]]:
        return [ln for ln in self.lines if ln.get("verdict") not in (None, "matched", "favorable")]

    def allowed_figures(self) -> set[Decimal]:
        vals: list[Any] = []
        rec = self.recommendation or {}
        vals += [rec.get("pay_amount"), rec.get("hold_amount"), self.exception.get("amount_at_risk")]
        inv = self.invoice
        vals += [
            inv.get(k)
            for k in ("subtotal", "tax", "freight", "total", "po_total", "expected_total", "total_delta")
        ]
        for ln in self.lines:
            vals += [
                ln.get(k)
                for k in (
                    "amount",
                    "unit_price",
                    "expected_unit_price",
                    "expected_amount",
                    "delta_amount",
                    "allowed_amount",
                    "po_unit_price",
                    "po_amount",
                )
            ]
        if self.po:
            vals.append(self.po.get("purchase_order", {}).get("total"))
            for pl in self.po.get("lines", []):
                vals += [pl.get("amount"), pl.get("unit_price")]
        for sp in self.prior_short_pays:
            vals += [sp.get("hold_amount"), sp.get("pay_amount")]
        return {n for v in vals if v is not None and (n := _norm(v)) is not None}

    def as_prompt_json(self) -> str:
        rec = dict(self.recommendation or {})
        return json.dumps(
            {
                "exception": self.exception,
                "invoice": {
                    k: self.invoice.get(k)
                    for k in (
                        "invoice_number",
                        "invoice_date",
                        "total",
                        "vendor_name",
                        "location_name",
                        "po_number",
                        "match_verdict",
                        "expected_total",
                        "total_delta",
                    )
                },
                "recommendation": rec or None,
                "lines": [
                    {
                        k: ln.get(k)
                        for k in (
                            "line_no",
                            "description",
                            "qty",
                            "uom",
                            "unit_price",
                            "amount",
                            "grn_qty",
                            "expected_unit_price",
                            "expected_source",
                            "expected_amount",
                            "delta_amount",
                            "verdict",
                            "note",
                            "clause_ref",
                            "contract_title",
                        )
                    }
                    for ln in self.lines
                ],
                "goods_receipts": (self.po or {}).get("goods_receipts"),
                "received_in_full": (self.po or {}).get("received_in_full"),
                "prior_short_pays_90d": self.prior_short_pays,
            },
            default=str,
        )


async def gather_facts(exception_id: str) -> DraftFacts:
    from app.db.pool import connection

    async with connection() as conn:
        cur = await conn.execute("select org_id from public.exceptions where id = %s", (exception_id,))
        row = await cur.fetchone()
        await conn.rollback()
    if row is None:
        raise LookupError(f"exception {exception_id} not found")
    org_id = str(row["org_id"])
    ex = await get_exception(org_id, exception_id)
    if "error" in ex:
        raise LookupError(ex["error"])
    inv = ex["invoice"] or {}
    po = await get_po_grn(org_id, inv["id"]) if inv.get("po_id") else None
    if po is not None and "error" in po:
        po = None
    prior: list[dict[str, Any]] = []
    if inv.get("vendor_id"):
        hist = await vendor_history(org_id, inv["vendor_id"], 90)
        prior = [
            sp for sp in hist.get("short_pays", []) if sp.get("invoice_number") != inv.get("invoice_number")
        ]
    facts = DraftFacts(org_id, ex["exception"], inv, ex.get("recommendation"), ex.get("lines", []), po, prior)
    clauses = sorted({ln["clause_ref"] for ln in facts.failing_lines if ln.get("clause_ref")})
    for c in clauses[:2]:
        desc = next((ln["description"] for ln in facts.failing_lines if ln.get("clause_ref") == c), "")
        hits = await search_kb(org_id, f"clause {c} {desc}", k=2, kinds=["contract"])
        facts.contract_chunks += [
            h for h in hits if h.chunk_id not in {x.chunk_id for x in facts.contract_chunks}
        ]
    return facts


# ------------------------------------------------------------------------------------------ templates
def _d(v: Any) -> Decimal:
    return Decimal(str(v))


def _date_text(v: Any) -> str:
    if not v:
        return ""
    d = v if isinstance(v, date) else date.fromisoformat(str(v)[:10])
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def template_draft(kind: str, f: DraftFacts) -> str:
    inv, e, rec = f.invoice, f.exception, f.recommendation or {}
    number = inv.get("invoice_number") or "this invoice"
    if kind == "explanation":
        out = [f"**Why {number} is held** — {e.get('reason', '')}.", ""]
        out += [f"- {r}" for r in rec.get("reasons") or []]
        if rec.get("pay_amount") is not None and rec.get("hold_amount") is not None:
            out += [
                "",
                f"**Recommendation:** {str(rec['action']).replace('_', ' ')} — pay "
                f"{fmt_money(rec['pay_amount'])}, hold {fmt_money(rec['hold_amount'])}.",
            ]
        elif rec:
            out += ["", f"**Recommendation:** {str(rec['action']).replace('_', ' ')}."]
        else:
            out += ["", "No recommendation — decide manually."]
        if f.contract_chunks:
            out.append(
                f"Contract reference: {f.contract_chunks[0].title} §{f.contract_chunks[0].clause_ref} [1]."
            )
        return "\n".join(out).strip()

    vendor = inv.get("vendor_name") or "Vendor"
    out = [
        f"**Subject:** Invoice {number} — {e.get('reason', '')}",
        "",
        f"Hello {vendor} accounts receivable team,",
        "",
    ]
    if rec.get("action") == "short_pay" and rec.get("pay_amount") is not None:
        billed = f" ({fmt_money(inv['total'])} billed)" if inv.get("total") else ""
        dated = f" dated {_date_text(inv['invoice_date'])}" if inv.get("invoice_date") else ""
        out.append(
            f"We have scheduled payment of **{fmt_money(rec['pay_amount'])}** against invoice {number}{dated}"
            f"{billed} and are holding **{fmt_money(rec['hold_amount'])}**."
        )
        out.append("")
        for ln in f.failing_lines:
            uom = f"/{ln['uom']}" if ln.get("uom") else ""
            if ln.get("expected_source") == "contract" and ln.get("expected_unit_price") is not None:
                ref = " [1]" if f.contract_chunks else ""
                agreement = ln.get("contract_title") or "Our agreement"
                out.append(
                    f"- {ln['description']}: invoiced at {fmt_unit_price(ln['unit_price'])}{uom}. "
                    f"{agreement}, clause {ln.get('clause_ref')}, fixes this item at "
                    f"{fmt_unit_price(ln['expected_unit_price'])}{uom}{ref}. "
                    f"Billed {fmt_money(ln['amount'])}, payable {fmt_money(ln['expected_amount'])}."
                )
            elif ln.get("expected_unit_price") is not None and ln.get("verdict") == "price_variance":
                out.append(
                    f"- {ln['description']}: invoiced at {fmt_unit_price(ln['unit_price'])}{uom}; "
                    f"purchase order {inv.get('po_number') or ''} prices it at "
                    f"{fmt_unit_price(ln['expected_unit_price'])}{uom}."
                )
            elif ln.get("grn_qty") is not None and ln.get("qty") is not None:
                out.append(
                    f"- {ln['description']}: {fmt_qty(_d(ln['grn_qty']))} received against "
                    f"{fmt_qty(_d(ln['qty']))} invoiced."
                )
        grns = [g["grn_number"] for g in (f.po or {}).get("goods_receipts", [])]
        if (f.po or {}).get("received_in_full") and grns:
            out += ["", f"Goods were received in full ({', '.join(grns)}), so the hold covers price only."]
        out += [
            "",
            f"Please send a credit memo for {fmt_money(rec['hold_amount'])} or a corrected invoice. If you "
            "believe the billed price is right, reply with the supporting amendment and we will review it.",
        ]
    else:
        out.append(f"Invoice {number} is on hold while we review it: {e.get('reason', '')}.")
        out.append("We will contact you if we need anything further.")
    out += ["", "Thank you,", "Accounts Payable"]
    return "\n".join(out).strip()


def recorded_draft(kind: str, f: DraftFacts) -> str | None:
    """Recorded LLM draft for hero invoices (`<invoice>.draft.json`), placeholders filled from facts."""
    number = f.invoice.get("invoice_number")
    if not number:
        return None
    try:
        path = heroes_dir() / f"{number}.draft.json"
    except FileNotFoundError:
        return None
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    body = (data.get(kind) or {}).get("body_md")
    if not body:
        return None
    eff_to = next(
        (ln.get("contract_effective_to") for ln in f.lines if ln.get("contract_effective_to")), None
    )
    return (
        body.replace("{{INVOICE_DATE}}", _date_text(f.invoice.get("invoice_date")))
        .replace("{{CONTRACT_EFFECTIVE_TO}}", _date_text(eff_to))
        .replace("{{VENDOR}}", f.invoice.get("vendor_name") or "")
    )


# ------------------------------------------------------------------------------------------ agent
class DraftOut(BaseModel):
    body_md: str


INSTRUCTIONS = """You draft accounts-payable correspondence for Ledgic. The decision has already been made by
deterministic rules (the `recommendation` in the facts); you explain it, you never change it.

Write either:
- kind=vendor_notice: a short, courteous, firm notice to the vendor's accounts-receivable team. Start with a
  bold **Subject:** line. State what is being paid and what is held, why (quote the contract clause or PO
  price), that goods were received if the facts say so, and ask for a credit memo or corrected invoice.
  Sign off as "Accounts Payable". No internal details (confidence scores, prior short-pays, people).
- kind=explanation: an internal note for the AP manager: why the invoice is held, the recommendation,
  the supporting facts (contract clause, receipt, vendor history). 3–6 bullets max.

Rules:
- Use ONLY money figures that appear in the facts or tool results, copied exactly. Never compute a new
  figure (no new totals, differences, percentages of money, or per-unit math). The draft is rejected
  automatically if it contains any other money figure.
- Cite contract passages with their ref in square brackets, e.g. [K1], right after the sentence.
- Plain Markdown, under 180 words. No placeholders, no "[Your name]".
Return JSON {"body_md": "..."}."""


def build_agent() -> Agent[AgentCtx]:
    return Agent[AgentCtx](
        name="Ledgic resolution",
        instructions=INSTRUCTIONS,
        tools=list(RESOLUTION_TOOLS),
        output_type=DraftOut,
    )


# ------------------------------------------------------------------------------------------ public API
@dataclass
class Draft:
    draft_id: str | None
    exception_id: str
    kind: str
    body_md: str
    citations: list[dict[str, Any]]
    mode: str  # live | recorded
    model: str | None
    prompt_version: str | None
    cost_usd: Decimal
    created_at: datetime | None
    guard: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cost_usd"] = str(self.cost_usd)
        d["created_at"] = self.created_at.isoformat() if self.created_at else None
        return d


def _cites(chunks: list[Chunk], query: str | None = None) -> list[dict[str, Any]]:
    from .copilot import citation_payload

    return [citation_payload(n, c, query) for n, c in enumerate(chunks, start=1)]


async def latest_draft(exception_id: str, kind: str) -> Draft | None:
    from app.db.pool import connection

    async with connection() as conn:
        cur = await conn.execute(
            "select * from public.exception_drafts where exception_id = %s and kind = %s"
            " order by created_at desc limit 1",
            (exception_id, kind),
        )
        row = await cur.fetchone()
        await conn.rollback()
    if row is None:
        return None
    figs = money_figures(row["body_md"])
    return Draft(
        str(row["id"]),
        exception_id,
        kind,
        row["body_md"],
        row["citations"] or [],
        row["mode"],
        row["model"],
        row["prompt_version"],
        Decimal(row["cost_usd"]),
        row["created_at"],
        {"passed": True, "figures": [str(_norm(x).normalize()) for x in figs if _norm(x) is not None]},
    )


async def draft_for_exception(
    exception_id: str,
    api_key: str | None = None,
    *,
    kind: str = "vendor_notice",
    regenerate: bool = False,
    persist: bool = True,
    gateway: LlmGateway | None = None,
) -> Draft:
    """Latest stored draft (unless `regenerate`), else run the resolution agent (live) or use the
    recorded/template draft, guard it, persist it to `exception_drafts` and return it."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if not regenerate and persist:
        existing = await latest_draft(exception_id, kind)
        if existing is not None:
            return existing

    facts = await gather_facts(exception_id)
    allowed = facts.allowed_figures()
    gw = gateway or get_gateway()
    body: str | None = None
    citations: list[dict[str, Any]] = []
    mode, model, cost = "recorded", None, Decimal(0)
    rejected: list[str] = []
    fallback_reason: str | None = None

    if gw.can_call(api_key):
        try:
            live_body, live_cites, model_used, cost = await _draft_live(kind, facts, api_key, gw)
            g = money_guard(live_body, allowed)
            if g.passed:
                body, citations, mode, model = live_body, live_cites, "live", model_used
            else:
                rejected, fallback_reason = g.rejected, "money_guard"
                log.warning("resolution draft rejected by money guard: %s", g.rejected)
        except Exception as exc:
            fallback_reason = type(exc).__name__
            log.info("resolution agent unavailable (%s); using template", fallback_reason)
    else:
        fallback_reason = "fixture mode" if gw.mode != "live" else "no API key"

    if body is None:
        rec_body = recorded_draft(kind, facts)
        if rec_body is not None and money_guard(rec_body, allowed).passed:
            body = rec_body
        else:
            body = template_draft(kind, facts)
        citations = _cites(facts.contract_chunks[:1])
        if not facts.contract_chunks:
            body = re.sub(r"\s?\[1\]", "", body)

    final_guard = money_guard(body, allowed)
    guard = {
        "passed": final_guard.passed,
        "figures": final_guard.figures,
        "fallback": mode != "live",
        "rejected": rejected,
        "reason": fallback_reason,
    }

    draft_id, created_at = None, None
    if persist:
        from app.db.pool import connection

        async with connection() as conn:
            cur = await conn.execute(
                "insert into public.exception_drafts (org_id, exception_id, kind, body_md, citations, model,"
                " prompt_version, mode, cost_usd) values (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)"
                " returning id, created_at",
                (
                    facts.org_id,
                    exception_id,
                    kind,
                    body,
                    json.dumps(citations, default=str),
                    model,
                    PROMPT_VERSION,
                    mode,
                    cost,
                ),
            )
            row = await cur.fetchone()
            await conn.commit()
        assert row is not None
        draft_id, created_at = str(row["id"]), row["created_at"]
    return Draft(
        draft_id, exception_id, kind, body, citations, mode, model, PROMPT_VERSION, cost, created_at, guard
    )


async def _draft_live(
    kind: str, f: DraftFacts, api_key: str | None, gw: LlmGateway
) -> tuple[str, list[dict[str, Any]], str, Decimal]:
    from .copilot import finalize_citations
    from .runtime import run_agent

    ctx = AgentCtx(org_id=f.org_id, api_key=api_key, max_tool_calls=4)
    pre = []
    for c in f.contract_chunks:
        ref = ctx.ref_for(c, f"clause {c.clause_ref}")
        pre.append({"ref": ref, "title": c.title, "clause": c.clause_ref, "text": c.content})
    prompt = (
        f"kind={kind}\n\nFacts (authoritative):\n{f.as_prompt_json()}\n\n"
        f"Contract passages already retrieved:\n{json.dumps(pre)}"
    )
    async with gw.metered(
        purpose=f"resolution.{kind}",
        org_id=f.org_id,
        est_input_tokens=EST_INPUT_TOKENS,
        max_output_tokens=MAX_OUTPUT_TOKENS * 2,
        api_key=api_key,
    ) as meter:
        result = await run_agent(
            build_agent(),
            prompt,
            meter,
            max_tokens=MAX_OUTPUT_TOKENS,
            max_turns=6,
            context=ctx,
            workflow="ledgic.resolution",
        )
    out = result.final_output
    body_raw = out.body_md if isinstance(out, DraftOut) else str(out)
    body, cites = finalize_citations(body_raw, ctx)
    return body, cites, meter.model, meter.cost_usd
