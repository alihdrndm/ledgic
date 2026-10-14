"""Data access behind the MCP tools. Plain async functions taking a `TokenContext`, so they are testable
without an MCP session. Every query runs inside a transaction *as the token's user* (`as_user`), so RLS
(`security_invoker` views), role limits and segregation of duties are enforced by Postgres; each query
also filters `org_id` explicitly (views contract)."""

from __future__ import annotations

import dataclasses
import inspect
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from mcp.server.mcpserver.exceptions import ToolError
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.db.pool import as_user, connection
from app.domain.money import fmt_money, fmt_money_short, fmt_pct_limit, fmt_qty
from app.domain.tolerance import line_tolerance, tolerance_sentence

from .auth import TokenContext

log = logging.getLogger(__name__)

EXCEPTION_TYPES = (
    "extraction_review",
    "price_variance",
    "qty_mismatch",
    "no_po",
    "unmatched_line",
    "duplicate",
    "new_vendor_screen",
    "posting_failed",
)
EXCEPTION_STATUS_FILTERS = ("open", "all", "resolved", "awaiting_vendor", "disputed", "escalated")
DECISION_ACTIONS = (
    "short_pay",
    "approve_as_is",
    "dispute",
    "reject_invoice",
    "link_po",
    "approve_without_po",
    "merge",
    "reject_copy",
    "not_duplicate",
    "request_w9",
    "release_hold",
    "retry_posting",
)
KPI_PERIODS = ("mtd", "qtd", "l30")
RATE_LIMIT_PER_MINUTE = 60
QUOTE_CHARS = 600


class LedgicError(ToolError):
    """Anticipated failure; the message is shown to the model/user verbatim."""


# ---- plumbing ---------------------------------------------------------------------------------


def jsonable(value: Any) -> Any:
    """Decimal → decimal string (money is never a float), dates → ISO-8601, UUID → str."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [jsonable(v) for v in value]
    return value


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return dataclasses.asdict(item)
    return dict(vars(item)) if hasattr(item, "__dict__") else {"value": item}


async def call_flex(fn: Callable[..., Any], **candidates: Any) -> Any:
    """Call a sibling-module function passing only the keyword arguments its signature accepts
    (the RAG/copilot modules are built in parallel; this keeps the MCP layer decoupled)."""
    params = inspect.signature(fn).parameters
    var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    kwargs = {k: v for k, v in candidates.items() if var_kw or k in params}
    result = fn(**kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


def _ledgic_message(exc: BaseException) -> str | None:
    diag = getattr(exc, "diag", None)
    msg = (getattr(diag, "message_primary", None) or str(exc) or "").strip()
    return msg if msg.startswith("LEDGIC_") else None


def translate_db_error(exc: psycopg.Error) -> LedgicError:
    msg = _ledgic_message(exc)
    if msg:
        code, _, text = msg.partition(":")
        text = text.strip() or code
        label = {
            "LEDGIC_FORBIDDEN": "Forbidden",
            "LEDGIC_NOT_FOUND": "Not found",
            "LEDGIC_CONFLICT": "Conflict",
            "LEDGIC_INVALID": "Invalid",
        }.get(code, code)
        return LedgicError(f"{label}: {text}")
    if isinstance(exc, psycopg.errors.UndefinedTable | psycopg.errors.UndefinedFunction):
        what = (getattr(exc.diag, "message_primary", None) or str(exc)).strip()
        return LedgicError(
            f"Not available yet: this Ledgic database is missing a required view or function ({what})."
        )
    if isinstance(exc, psycopg.errors.InsufficientPrivilege):
        return LedgicError("Forbidden: the database refused this request for your role.")
    if isinstance(exc, psycopg.OperationalError):
        return LedgicError("Database unavailable — try again shortly.")
    if isinstance(exc, psycopg.errors.InvalidTextRepresentation | psycopg.errors.DataException):
        return LedgicError(f"Invalid: {(exc.diag.message_primary or str(exc)).strip()}")
    log.exception("unexpected database error in MCP tool")
    return LedgicError("Internal database error.")


@asynccontextmanager
async def user_tx(ctx: TokenContext) -> AsyncIterator[AsyncConnection]:
    """A transaction acting as the token's user (RLS + RPC role checks apply)."""
    try:
        async with connection() as conn, conn.transaction():
            await as_user(conn, ctx.user_id)
            yield conn
    except psycopg.Error as exc:
        raise translate_db_error(exc) from exc


async def _fetchall(conn: AsyncConnection, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
    cur = await conn.execute(sql, params)  # type: ignore[arg-type]
    return list(await cur.fetchall())  # type: ignore[arg-type]


async def _fetchone(conn: AsyncConnection, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
    cur = await conn.execute(sql, params)  # type: ignore[arg-type]
    return await cur.fetchone()  # type: ignore[return-value]


async def rate_limit(ctx: TokenContext) -> None:
    """Fixed-window limit per token (rpc.md `rate_limit_hit`, key `mcp:token:<id>`). No-op until the
    RPC exists."""
    try:
        async with connection() as conn:
            row = await _fetchone(
                conn,
                "select public.rate_limit_hit(%s, %s, %s) as over",
                (f"mcp:token:{ctx.token_id}", RATE_LIMIT_PER_MINUTE, 60),
            )
    except psycopg.errors.UndefinedFunction:
        return
    except psycopg.Error:
        log.warning("rate_limit_hit failed; allowing MCP call", exc_info=True)
        return
    if row and row["over"]:
        raise LedgicError(f"Rate limited: more than {RATE_LIMIT_PER_MINUTE} Ledgic tool calls a minute.")


def _uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(str(value).strip()))
    except ValueError as exc:
        raise LedgicError(f"Invalid: {what} must be a UUID, got {value!r}.") from exc


def _compact_rec(rec: Any) -> dict[str, Any] | None:
    if not isinstance(rec, dict):
        return None
    keep = ("action", "pay_amount", "hold_amount", "confidence", "reasons")
    return {k: rec.get(k) for k in keep if rec.get(k) is not None}


def _norm_number(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


# ---- exceptions -------------------------------------------------------------------------------


async def list_exceptions(
    ctx: TokenContext, status: str = "open", type: str | None = None, limit: int = 20
) -> dict[str, Any]:
    if status not in EXCEPTION_STATUS_FILTERS:
        raise LedgicError(f"Invalid: status must be one of {', '.join(EXCEPTION_STATUS_FILTERS)}.")
    if type is not None and type not in EXCEPTION_TYPES:
        raise LedgicError(f"Invalid: type must be one of {', '.join(EXCEPTION_TYPES)}.")
    limit = max(1, min(int(limit), 100))
    where = ["org_id = %(org)s"]
    if status == "open":
        where.append("status <> 'resolved'")
    elif status != "all":
        where.append("status = %(status)s::public.exception_status")
    if type:
        where.append("type = %(type)s::public.exception_type")
    params = {"org": ctx.org_id, "status": status, "type": type, "limit": limit}
    cond = " and ".join(where)
    async with user_tx(ctx) as conn:
        total = await _fetchone(
            conn, f"select count(*)::int as n from public.v_exception_queue where {cond}", params
        )
        rows = await _fetchall(
            conn,
            f"""
            select exception_id, type, group_label, status, invoice_number, vendor_name, location_name,
                   amount_at_risk, invoice_total, reason, assigned_role, escalated, opened_at, sla_due_at,
                   age_seconds, payment_blocked, similarity, signal_score, recommendation, has_draft
              from public.v_exception_queue
             where {cond}
             order by (status = 'resolved'), is_risk_group desc, opened_at asc
             limit %(limit)s
            """,
            params,
        )
    items = []
    for r in rows:
        item = {
            "exception_id": r["exception_id"],
            "type": r["type"],
            "label": r["group_label"],
            "status": r["status"],
            "invoice_number": r["invoice_number"],
            "vendor": r["vendor_name"],
            "location": r["location_name"],
            "amount_at_risk": r["amount_at_risk"],
            "invoice_total": r["invoice_total"],
            "reason": r["reason"],
            "assigned_role": r["assigned_role"],
            "age_hours": round((r["age_seconds"] or 0) / 3600, 1),
            "sla_due_at": r["sla_due_at"],
            "payment_blocked": r["payment_blocked"],
            "recommendation": _compact_rec(r["recommendation"]),
        }
        if r["escalated"]:
            item["escalated"] = True
        if r["similarity"] is not None:
            item["duplicate_similarity"] = r["similarity"]
        if r["signal_score"] is not None:
            item["fraud_signal_score"] = r["signal_score"]
        items.append(item)
    return jsonable(
        {
            "status_filter": status,
            "type_filter": type,
            "total": total["n"] if total else len(items),
            "returned": len(items),
            "exceptions": items,
        }
    )


# ---- invoices ---------------------------------------------------------------------------------

_FIND_INVOICE_SQL = """
select * from public.v_invoice_detail
 where org_id = %(org)s
   and (invoice_id::text = %(raw)s
        or upper(regexp_replace(coalesce(invoice_number, ''), '[^A-Za-z0-9]', '', 'g')) = %(norm)s)
 order by received_at desc
 limit 10
"""


async def _find_invoices(
    conn: AsyncConnection, ctx: TokenContext, invoice_number: str
) -> list[dict[str, Any]]:
    raw = (invoice_number or "").strip()
    if not raw:
        raise LedgicError("Invalid: give an invoice number like PS-88214 (or an invoice UUID).")
    rows = await _fetchall(
        conn, _FIND_INVOICE_SQL, {"org": ctx.org_id, "raw": raw.lower(), "norm": _norm_number(raw)}
    )
    if not rows:
        raise LedgicError(f"Not found: no invoice {raw!r} in this organization.")
    return rows


async def get_invoice(ctx: TokenContext, invoice_number: str) -> dict[str, Any]:
    async with user_tx(ctx) as conn:
        rows = await _find_invoices(conn, ctx, invoice_number)
        inv = rows[0]
        match = await _fetchone(
            conn,
            """
            select verdict, tolerance_pct, tolerance_abs, expected_total, total_delta, lines_verified,
                   lines_total, computed_at
              from public.v_match_detail where org_id = %s and invoice_id = %s limit 1
            """,
            (ctx.org_id, inv["invoice_id"]),
        )
        excs = await _fetchall(
            conn,
            """
            select exception_id, type, group_label, status, amount_at_risk, reason, opened_at, resolved_at,
                   payment_blocked, recommendation, latest_decision
              from public.v_exception_queue where org_id = %s and invoice_id = %s order by opened_at
            """,
            (ctx.org_id, inv["invoice_id"]),
        )
    lines = [
        {
            k: ln.get(k)
            for k in ("line_no", "description", "qty", "uom", "unit_price", "amount", "gl_number", "gl_name")
        }
        for ln in (inv.get("lines") or [])
    ]
    out: dict[str, Any] = {
        "invoice_id": inv["invoice_id"],
        "invoice_number": inv["invoice_number"],
        "status": inv["status"],
        "vendor": inv["vendor_name"],
        "entity": inv["entity_short_code"] or inv["entity_name"],
        "location": inv["location_name"],
        "channel": inv["channel"],
        "invoice_date": inv["invoice_date"],
        "due_date": inv["due_date"],
        "terms": inv["terms"],
        "currency": inv["currency"],
        "subtotal": inv["subtotal"],
        "tax": inv["tax"],
        "freight": inv["freight"],
        "total": inv["total"],
        "received_at": inv["received_at"],
        "doc_confidence": inv["doc_confidence"],
        "touchless": inv["touchless"],
        "human_touches": inv["human_touches"],
        "extraction_mode": inv["extraction_mode"],
        "po_number": inv["po_number"],
        "po_total": inv["po_total"],
        "grn_numbers": inv["grn_numbers"],
        "grn_in_full": inv["grn_in_full"],
        "duplicate_of": inv["duplicate_of"],
        "run_number": inv["run_number"],
        "lines": lines,
        "match": dict(match) if match else None,
        "exceptions": [
            {
                "exception_id": e["exception_id"],
                "type": e["type"],
                "label": e["group_label"],
                "status": e["status"],
                "amount_at_risk": e["amount_at_risk"],
                "reason": e["reason"],
                "payment_blocked": e["payment_blocked"],
                "recommendation": _compact_rec(e["recommendation"]),
                "latest_decision": e["latest_decision"],
            }
            for e in excs
        ],
        "posting": {
            "erp_system": inv["erp_system"],
            "erp_external_id": inv["erp_external_id"],
            "erp_status": inv["erp_status"],
            "posted_at": inv["posted_at"],
        }
        if inv["erp_system"] or inv["posted_at"]
        else None,
    }
    if len(rows) > 1:
        out["other_invoices_with_same_number"] = [
            {
                "invoice_id": r["invoice_id"],
                "status": r["status"],
                "vendor": r["vendor_name"],
                "total": r["total"],
            }
            for r in rows[1:]
        ]
    return jsonable(out)


def _line_sentence(r: dict[str, Any], pct: Decimal, abs_amount: Decimal) -> str | None:
    n = r["line_no"]
    verdict = r["line_verdict"]
    if verdict == "unmatched_line" or (r["po_line_id"] is None and r["expected_unit_price"] is None):
        return f"Line {n} has no matching PO line, so there is nothing to compare its price against."
    if verdict in ("qty_over_receipt", "qty_over_order"):
        ref, ref_name = (
            (r["grn_qty"], "received") if verdict == "qty_over_receipt" else (r["po_qty"], "ordered")
        )
        if r["inv_qty"] is not None and ref is not None:
            return (
                f"Line {n} invoices {fmt_qty(r['inv_qty'])} {r['uom'] or ''}".rstrip()
                + f" but only {fmt_qty(ref)} {ref_name} — quantity mismatch, "
                + "so the invoice holds for approval."
            )
    if r["expected_unit_price"] is not None and r["inv_qty"] is not None and r["inv_amount"] is not None:
        return tolerance_sentence(
            n, line_tolerance(r["expected_unit_price"], r["inv_qty"], r["inv_amount"], pct, abs_amount)
        )
    return None


async def explain_match(ctx: TokenContext, invoice_number: str) -> dict[str, Any]:
    async with user_tx(ctx) as conn:
        inv = (await _find_invoices(conn, ctx, invoice_number))[0]
        rows = await _fetchall(
            conn,
            "select * from public.v_match_detail where org_id = %s and invoice_id = %s order by line_no",
            (ctx.org_id, inv["invoice_id"]),
        )
    if not rows:
        return jsonable(
            {
                "invoice_id": inv["invoice_id"],
                "invoice_number": inv["invoice_number"],
                "status": inv["status"],
                "verdict": None,
                "message": "This invoice has not been through three-way match yet "
                + ("(no purchase order linked)." if inv["po_id"] is None else "(match still pending)."),
            }
        )
    head = rows[0]
    pct = Decimal(head["tolerance_pct"])
    abs_amount = Decimal(head["tolerance_abs"])
    lines = []
    sentences = []
    for r in rows:
        sentence = _line_sentence(r, pct, abs_amount)
        if sentence and r["line_verdict"] not in ("matched",):
            sentences.append(sentence)
        lines.append(
            {
                "line_no": r["line_no"],
                "description": r["description"],
                "uom": r["uom"],
                "invoiced": {
                    "qty": r["inv_qty"],
                    "unit_price": r["inv_unit_price"],
                    "amount": r["inv_amount"],
                },
                "po": {"qty": r["po_qty"], "unit_price": r["po_unit_price"], "amount": r["po_amount"]}
                if r["po_line_id"]
                else None,
                "received_qty": r["grn_qty"],
                "expected": {
                    "unit_price": r["expected_unit_price"],
                    "source": r["expected_source"],
                    "amount": r["expected_amount"],
                    "contract": {
                        "title": r["contract_title"],
                        "clause_ref": r["clause_ref"],
                        "effective_to": r["contract_effective_to"],
                    }
                    if r["contract_id"]
                    else None,
                },
                "delta_amount": r["delta_amount"],
                "delta_pct": r["delta_pct"],
                "allowed_amount": r["allowed_amount"],
                "verdict": r["line_verdict"],
                "note": r["note"],
                "explanation": sentence,
            }
        )
    rule = (
        f"A line passes when it is under the expected amount, or over it by no more than the lower of "
        f"±{fmt_pct_limit(pct)} of the expected extension and {fmt_money_short(abs_amount)}."
    )
    summary = (
        f"Verdict {head['verdict']}: {head['lines_verified']} of {head['lines_total']} lines verified; "
        f"invoice is {fmt_money(head['total_delta'] or 0, sign=True)} against the expected "
        f"{fmt_money(head['expected_total'] or 0)}."
    )
    return jsonable(
        {
            "invoice_id": inv["invoice_id"],
            "invoice_number": inv["invoice_number"],
            "vendor": inv["vendor_name"],
            "po_number": inv["po_number"],
            "grn_numbers": inv["grn_numbers"],
            "verdict": head["verdict"],
            "summary": summary,
            "tolerance": {"pct": pct, "abs": abs_amount, "rule": rule},
            "expected_total": head["expected_total"],
            "total_delta": head["total_delta"],
            "lines_verified": head["lines_verified"],
            "lines_total": head["lines_total"],
            "explanations": sentences or ["Every line is within tolerance."],
            "lines": lines,
            "exception_id": head["exception_id"],
            "recommendation": head["recommendation"],
            "decision": head["decision"],
        }
    )


# ---- knowledge base / copilot -----------------------------------------------------------------


def _citation(n: int, hit: dict[str, Any]) -> dict[str, Any]:
    content = hit.get("content") or hit.get("quote") or hit.get("text") or ""
    quote = content if len(content) <= QUOTE_CHARS else content[: QUOTE_CHARS - 1].rstrip() + "…"
    score = hit.get("rrf_score", hit.get("score"))
    out = {
        "n": n,
        "title": hit.get("title"),
        "kind": hit.get("kind"),
        "clause_ref": hit.get("clause_ref"),
        "heading_path": hit.get("heading_path"),
        "quote": quote,
        "document_id": hit.get("document_id"),
        "chunk_id": hit.get("chunk_id") or hit.get("id"),
    }
    if score is not None:
        out["score"] = round(float(score), 5)
    return {k: v for k, v in out.items() if v is not None}


_FTS_SQL = """
select c.id as chunk_id, c.document_id, d.title, d.kind, c.heading_path, c.clause_ref, c.content,
       ts_rank_cd(c.tsv, q) as score
  from public.kb_chunks c
  join public.kb_documents d on d.id = c.document_id,
       websearch_to_tsquery('english', %(q)s) q
 where c.org_id = %(org)s and c.tsv @@ q and (%(kind)s::text is null or d.kind = %(kind)s)
 order by score desc
 limit %(k)s
"""


async def _fts_search(ctx: TokenContext, query: str, k: int, kind: str | None) -> list[dict[str, Any]]:
    try:
        async with connection() as conn:  # kb_search contract: core reads kb as service role, org-filtered
            return await _fetchall(conn, _FTS_SQL, {"q": query, "org": ctx.org_id, "kind": kind, "k": k})
    except psycopg.Error as exc:
        raise translate_db_error(exc) from exc


def _load_search_kb() -> Callable[..., Any] | None:
    """The RAG workstream's hybrid retriever, wherever it lives; None when not installed."""
    import importlib

    for mod in ("app.ai.rag.retrieve", "app.ai.retrieve"):
        try:
            return getattr(importlib.import_module(mod), "search_kb")  # noqa: B009
        except (ImportError, AttributeError):
            continue
    return None


async def search_contracts(
    ctx: TokenContext, query: str, k: int = 5, kind: str | None = None
) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        raise LedgicError("Invalid: query is empty.")
    k = max(1, min(int(k), 20))
    kinds = [kind] if kind else None
    mode = "hybrid"
    note = None
    hits: list[dict[str, Any]] = []
    search_kb = _load_search_kb()
    if search_kb is not None:
        try:
            raw = await call_flex(
                search_kb, org_id=ctx.org_id, org=ctx.org_id, query=query, k=k, top_k=k, limit=k, kinds=kinds
            )
            hits = [_as_dict(h) for h in (raw or [])][:k]
        except Exception:
            log.warning("search_kb failed; falling back to full-text search", exc_info=True)
            note = "Semantic search was unavailable; results are keyword (full-text) matches only."
            search_kb = None
    if search_kb is None:
        mode = "text_only"
        hits = await _fts_search(ctx, query, k, kind)
    out: dict[str, Any] = {
        "query": query,
        "mode": mode,
        "results": [_citation(i + 1, h) for i, h in enumerate(hits)],
    }
    if note:
        out["note"] = note
    if not hits:
        out["note"] = "No matching contract, policy or vendor-note passages."
    return jsonable(out)


async def ask_ledgic(ctx: TokenContext, question: str) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        raise LedgicError("Invalid: question is empty.")
    if len(question) > 500:
        raise LedgicError("Invalid: keep the question under 500 characters.")
    try:
        from app.ai.copilot import ask
    except ImportError as exc:
        raise LedgicError(
            "The Ask Ledgic copilot is not available in this deployment yet. Use search_contracts, "
            "get_invoice and explain_match directly."
        ) from exc
    ask_fn: Callable[..., Awaitable[Any] | Any] = ask
    try:
        result = await call_flex(ask_fn, org_id=ctx.org_id, question=question, user_id=ctx.user_id)
    except ToolError:
        raise
    except Exception as exc:
        log.exception("copilot ask failed")
        raise LedgicError("The copilot failed to answer; try search_contracts instead.") from exc
    data = _as_dict(result)
    if isinstance(data.get("data"), dict):  # tolerate an envelope
        data = data["data"]
    citations = [
        _citation(int(c.get("n") or i + 1), c)
        for i, c in enumerate(_as_dict(c) for c in data.get("citations") or [])
    ]
    return jsonable(
        {
            "answer_md": data.get("answer_md") or data.get("answer"),
            "citations": citations,
            "mode": data.get("mode"),
            "model": data.get("model"),
            "cost_usd": data.get("cost_usd"),
            "tool_calls": data.get("tool_calls"),
            "notice": data.get("notice"),
        }
    )


# ---- KPIs / audit -----------------------------------------------------------------------------

_KPI_COLUMNS = (
    "period_key, period_start, period_end, invoices, locations, entities, cost_total, cost_per_invoice, "
    "cost_llm, cost_ocr, cost_infra, cost_human, touchless_rate, touchless_rate_first_week, "
    "median_cycle_seconds, held_variances, held_duplicates, held_fraud, held_total, short_pays_accepted, "
    "avg_decision_seconds, decisions_logged_pct, top_catches, erp_sync, refreshed_at"
)


async def get_kpis(ctx: TokenContext, period: str = "mtd") -> dict[str, Any]:
    if period not in KPI_PERIODS:
        raise LedgicError(f"Invalid: period must be one of {', '.join(KPI_PERIODS)}.")
    async with user_tx(ctx) as conn:
        ops = await _fetchone(
            conn,
            f"select {_KPI_COLUMNS} from public.v_ops_period where org_id = %s and period_key = %s",
            (ctx.org_id, period),
        )
        status = await _fetchone(
            conn,
            """
            select runs_today, review_queue_size, exceptions_open, exceptions_raised_today,
                   exceptions_cleared_today, payments_blocked, dead_letters_open, erp_failing, last_run_at
              from public.v_status_bar where org_id = %s
            """,
            (ctx.org_id,),
        )
    out: dict[str, Any] = {
        "period": period,
        "kpis": dict(ops) if ops else None,
        "today": dict(status) if status else None,
    }
    if ops is None:
        out["note"] = "No KPI snapshot yet for this period (the operations view refreshes every minute)."
    else:
        out["definitions"] = {
            "touchless_rate": "share of invoices posted with no human touch (fraction, 0.62 = 62%)",
            "held_total": "money held back by short-pays, duplicate and fraud holds in the period",
            "cost_per_invoice": "LLM + OCR + infra + loaded human time, per invoice (USD)",
        }
    return jsonable(out)


async def verify_audit_chain(ctx: TokenContext) -> dict[str, Any]:
    async with user_tx(ctx) as conn:
        row = await _fetchone(conn, "select public.audit_verify_org(%s::uuid) as r", (ctx.org_id,))
    r = dict((row or {}).get("r") or {})
    if r.get("ok"):
        r["message"] = f"Audit chain intact: {r.get('entries')} entries, each hash links to the previous one."
    else:
        r["message"] = (
            f"Audit chain BROKEN at entry {r.get('first_broken_id')} — "
            "a row was altered or removed after it was written."
        )
    return jsonable(r)


# ---- decisions --------------------------------------------------------------------------------


async def decide_exception(
    ctx: TokenContext,
    exception_id: str,
    action: str,
    comment: str | None = None,
    pay_amount: Decimal | None = None,
    hold_amount: Decimal | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exc_id = _uuid(exception_id, "exception_id")
    if action not in DECISION_ACTIONS:
        raise LedgicError(f"Invalid: action must be one of {', '.join(DECISION_ACTIONS)}.")
    async with user_tx(ctx) as conn:
        row = await _fetchone(
            conn,
            """
            select public.rpc_decide_exception(
                     p_exception_id => %s::uuid,
                     p_action       => %s::public.decision_action,
                     p_pay_amount   => %s::numeric,
                     p_hold_amount  => %s::numeric,
                     p_comment      => %s::text,
                     p_time_spent   => null::int,
                     p_extra        => %s::jsonb) as r
            """,
            (exc_id, action, pay_amount, hold_amount, (comment or None), Jsonb(extra or {})),
        )
    result = dict((row or {}).get("r") or {})
    return jsonable(
        {
            "ok": True,
            "exception_id": exc_id,
            "action": action,
            "exception_status": result.get("exception_status"),
            "approval_id": result.get("approval_id"),
            "run_id": result.get("run_id"),
            "message": f"Recorded '{action}' on exception {exc_id}; "
            f"it is now {result.get('exception_status')}."
            + (" The paused pipeline run will resume." if result.get("run_id") else ""),
        }
    )


# ---- resources --------------------------------------------------------------------------------

_FALLBACK_POLICY = """# Northside Group — AP policy (summary)

- **Price tolerance:** a line passes when it is under the expected price, or over it by no more than the
  lower of ±2% of the expected extension and $25.00. Expected price = active contract price, else PO price.
- **Three-way match:** invoice ↔ purchase order ↔ goods receipt (GRN). Quantities above what was received
  hold for approval.
- **Approval authority:** AP managers decide exceptions up to $5,000.00 at risk; above that, a controller.
  Duplicate "not a duplicate" calls and new-vendor holds need a controller.
- **Segregation of duties:** whoever edited an invoice's amounts cannot approve it; whoever created a vendor
  cannot release its new-vendor hold.
- **Comments** are required for approve-as-is, approve-without-PO, not-duplicate, dispute and release-hold.
- Every decision is written to a tamper-evident, hash-chained audit log.
"""


def ap_policy_path() -> Path | None:
    rel = Path("tools/corpus/kb/policies/ap-policy.md")
    try:
        from app.ai.paths import kb_dir  # RAG workstream helper, if present

        p = Path(kb_dir()) / "policies" / "ap-policy.md"
        if p.is_file():
            return p
    except Exception:  # noqa: S110 - optional helper
        pass
    for parent in Path(__file__).resolve().parents:
        p = parent / rel
        if p.is_file():
            return p
    return None


def read_ap_policy() -> str:
    p = ap_policy_path()
    if p is not None:
        return p.read_text(encoding="utf-8")
    return _FALLBACK_POLICY
