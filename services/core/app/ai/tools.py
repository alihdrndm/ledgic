"""Read-only data tools shared by the copilot, the resolution agent and the MCP server.

Each tool is a plain `async def ...(org_id, ...) -> dict` (JSON-able: money as decimal strings) that
runs in a READ ONLY transaction scoped to `org_id`, plus an Agents-SDK `function_tool` wrapper that
takes the org from the run context (`AgentCtx`) — the model can never choose another org.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from agents import RunContextWrapper, function_tool

from .rag.retrieve import Chunk, clause_chunk, search_kb

MAX_TOOL_CALLS = 6


# ------------------------------------------------------------------------------------------ helpers
def jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [jsonable(x) for x in v]
    return v


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except ValueError:
        return False


def norm_invoice_number(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


@asynccontextmanager
async def read_only() -> AsyncIterator[Any]:
    from app.db.pool import connection

    async with connection() as conn:
        await conn.execute("set transaction read only")
        try:
            yield conn
        finally:
            await conn.rollback()


async def _all(conn: Any, sql: str, params: Any) -> list[dict[str, Any]]:
    cur = await conn.execute(sql, params)
    return [dict(r) for r in await cur.fetchall()]


async def _one(conn: Any, sql: str, params: Any) -> dict[str, Any] | None:
    cur = await conn.execute(sql, params)
    r = await cur.fetchone()
    return dict(r) if r else None


async def _resolve_invoice(conn: Any, org_id: str, ref: str) -> dict[str, Any] | None:
    return await _one(
        conn,
        """
        select i.id, i.invoice_number, i.invoice_date, i.due_date, i.terms, i.currency, i.subtotal, i.tax,
               i.freight, i.total, i.status, i.doc_confidence, i.gate_passed, i.touchless, i.human_touches,
               i.extraction_mode, i.received_at, i.posted_at, i.vendor_id, v.display_name as vendor_name,
               l.name as location_name, e.short_code as entity, i.po_id, po.po_number, po.total as po_total,
               d.channel, mr.verdict as match_verdict, mr.expected_total, mr.total_delta
        from public.invoices i
        left join public.vendors v on v.id = i.vendor_id
        left join public.locations l on l.id = i.location_id
        left join public.entities e on e.id = i.entity_id
        left join public.purchase_orders po on po.id = i.po_id
        left join public.documents d on d.id = i.document_id
        left join public.match_results mr on mr.invoice_id = i.id
        where i.org_id = %(org)s
          and (i.id::text = %(ref)s or i.invoice_number_norm = %(norm)s)
        order by (i.id::text = %(ref)s) desc, i.duplicate_of is not null, i.received_at desc
        limit 1
        """,
        {"org": org_id, "ref": ref, "norm": norm_invoice_number(ref)},
    )


async def _match_lines(conn: Any, invoice_id: Any) -> list[dict[str, Any]]:
    return await _all(
        conn,
        """
        select il.line_no, il.description, il.qty, il.uom, il.unit_price, il.amount,
               mlr.grn_qty, mlr.expected_unit_price, mlr.expected_source, mlr.expected_amount,
               mlr.delta_amount, mlr.delta_pct, mlr.allowed_amount, mlr.verdict, mlr.note,
               cp.clause_ref, cp.contract_id, c.title as contract_title, c.effective_to as contract_effective_to,
               pl.qty as po_qty, pl.unit_price as po_unit_price, pl.amount as po_amount
        from public.invoice_lines il
        left join public.match_results mr on mr.invoice_id = il.invoice_id
        left join public.match_line_results mlr
               on mlr.match_result_id = mr.id and mlr.invoice_line_id = il.id
        left join public.contract_prices cp on cp.id = mlr.contract_price_id
        left join public.contracts c on c.id = cp.contract_id
        left join public.po_lines pl on pl.id = coalesce(mlr.po_line_id, il.po_line_id)
        where il.invoice_id = %s
        order by il.line_no
        """,
        (invoice_id,),
    )


def _not_found(what: str, ref: str) -> dict[str, Any]:
    return {"error": f"{what} {ref!r} not found in this organization"}


# ------------------------------------------------------------------------------------------ plain tools
async def kb_search_tool(
    org_id: str, query: str, k: int = 5, kind: str | None = None, api_key: str | None = None
) -> dict[str, Any]:
    chunks = await search_kb(org_id, query, k, kinds=[kind] if kind else None, api_key=api_key)
    return {"chunks": [chunk_payload(c, query) for c in chunks]}


def chunk_payload(c: Chunk, query: str | None = None) -> dict[str, Any]:
    return {
        "chunk_id": c.chunk_id,
        "document_id": c.document_id,
        "title": c.title,
        "kind": c.kind,
        "clause_ref": c.clause_ref,
        "section": c.heading_path,
        "content": c.content,
        "snippet": c.snippet(query),
    }


async def get_invoice_summary(org_id: str, invoice: str) -> dict[str, Any]:
    """Invoice header, lines with match results, and open exceptions. `invoice`: id or number."""
    async with read_only() as conn:
        inv = await _resolve_invoice(conn, org_id, invoice)
        if inv is None:
            return _not_found("invoice", invoice)
        lines = await _match_lines(conn, inv["id"])
        exc = await _all(
            conn,
            "select id as exception_id, type, status, amount_at_risk, reason, assigned_role, opened_at,"
            " sla_due_at, resolved_at from public.exceptions where invoice_id = %s order by opened_at",
            (inv["id"],),
        )
    return jsonable({"invoice": inv, "lines": lines, "exceptions": exc})


async def get_exception(org_id: str, exception: str) -> dict[str, Any]:
    """Exception with recommendation, latest decision and match lines. `exception`: exception id, or an
    invoice id/number (→ its most recent exception)."""
    async with read_only() as conn:
        row = None
        if _is_uuid(exception):
            row = await _one(
                conn, "select * from public.exceptions where org_id = %s and id = %s", (org_id, exception)
            )
        if row is None:
            inv = await _resolve_invoice(conn, org_id, exception)
            if inv is None:
                return _not_found("exception", exception)
            row = await _one(
                conn,
                "select * from public.exceptions where invoice_id = %s"
                " order by (status <> 'resolved') desc, opened_at desc limit 1",
                (inv["id"],),
            )
            if row is None:
                return {"error": f"invoice {exception!r} has no exceptions", "invoice": jsonable(inv)}
        inv = await _resolve_invoice(conn, org_id, str(row["invoice_id"]))
        rec = await _one(
            conn,
            "select action, pay_amount, hold_amount, confidence, reasons from public.recommendations"
            " where exception_id = %s",
            (row["id"],),
        )
        decision = await _one(
            conn,
            "select a.action, a.pay_amount, a.hold_amount, a.comment, a.decided_at, p.full_name as actor"
            " from public.approvals a left join public.profiles p on p.user_id = a.actor_id"
            " where a.exception_id = %s order by a.decided_at desc limit 1",
            (row["id"],),
        )
        lines = await _match_lines(conn, row["invoice_id"]) if inv else []
    if rec and isinstance(rec.get("reasons"), list):
        rec["reasons"] = [r.get("text", r) if isinstance(r, dict) else r for r in rec["reasons"]]
    return jsonable(
        {
            "exception": {
                "exception_id": row["id"],
                "type": row["type"],
                "status": row["status"],
                "amount_at_risk": row["amount_at_risk"],
                "reason": row["reason"],
                "assigned_role": row["assigned_role"],
                "escalated": row["escalated"],
                "opened_at": row["opened_at"],
                "sla_due_at": row["sla_due_at"],
                "resolved_at": row["resolved_at"],
            },
            "invoice": inv,
            "recommendation": rec,
            "latest_decision": decision,
            "lines": lines,
        }
    )


async def list_exceptions(org_id: str, status: str = "open", limit: int = 20) -> dict[str, Any]:
    """Exceptions queue (status: open = anything not resolved, resolved, or all)."""
    limit = max(1, min(int(limit), 100))
    cond = {"open": "e.status <> 'resolved'", "resolved": "e.status = 'resolved'"}.get(status, "true")
    async with read_only() as conn:
        rows = await _all(
            conn,
            f"""
            select e.id as exception_id, e.type, e.status, e.amount_at_risk, e.reason, e.assigned_role,
                   e.opened_at, e.sla_due_at, i.invoice_number, i.total as invoice_total,
                   v.display_name as vendor_name
            from public.exceptions e
            join public.invoices i on i.id = e.invoice_id
            left join public.vendors v on v.id = i.vendor_id
            where e.org_id = %s and {cond}
            order by e.opened_at desc
            limit %s
            """,
            (org_id, limit),
        )
    return jsonable({"exceptions": rows, "count": len(rows)})


async def _resolve_vendor(conn: Any, org_id: str, vendor: str) -> dict[str, Any] | None:
    return await _one(
        conn,
        """
        select v.id, v.display_name, v.legal_name, v.category, v.w9_on_file, v.created_at,
               v.remit_address_changed_at, v.contact_email::text as contact_email
        from public.vendors v
        where v.org_id = %(org)s and (
            v.id::text = %(ref)s or v.display_name ilike %(ref)s
            or v.display_name ilike '%%' || %(ref)s || '%%'
            or exists (select 1 from public.vendor_aliases a
                       where a.vendor_id = v.id and a.alias ilike %(ref)s))
        order by (v.id::text = %(ref)s or v.display_name ilike %(ref)s) desc, length(v.display_name)
        limit 1
        """,
        {"org": org_id, "ref": vendor},
    )


async def vendor_history(org_id: str, vendor: str, days: int = 90) -> dict[str, Any]:
    """Vendor activity over the last `days`: invoice count/total, recent invoices, accepted short-pays,
    exceptions by type, contracts on file. `vendor`: id, display name or alias."""
    days = max(1, min(int(days), 365))
    async with read_only() as conn:
        v = await _resolve_vendor(conn, org_id, vendor)
        if v is None:
            return _not_found("vendor", vendor)
        p = {"org": org_id, "vid": v["id"], "days": days}
        agg = await _one(
            conn,
            "select count(*) as invoices, coalesce(sum(total),0) as total, avg(total) as avg_total"
            " from public.invoices where org_id = %(org)s and vendor_id = %(vid)s and duplicate_of is null"
            " and received_at >= now() - make_interval(days => %(days)s)",
            p,
        )
        recent = await _all(
            conn,
            "select invoice_number, invoice_date, total, status, touchless from public.invoices"
            " where org_id = %(org)s and vendor_id = %(vid)s"
            " and received_at >= now() - make_interval(days => %(days)s)"
            " order by received_at desc limit 10",
            p,
        )
        short_pays = await _all(
            conn,
            """
            select i.invoice_number, a.pay_amount, a.hold_amount, a.decided_at, e.reason, e.status
            from public.approvals a
            join public.exceptions e on e.id = a.exception_id
            join public.invoices i on i.id = e.invoice_id
            where a.org_id = %(org)s and i.vendor_id = %(vid)s and a.action = 'short_pay'
              and a.decided_at >= now() - make_interval(days => %(days)s)
            order by a.decided_at desc
            """,
            p,
        )
        by_type = await _all(
            conn,
            "select e.type, count(*) as n from public.exceptions e"
            " join public.invoices i on i.id = e.invoice_id"
            " where e.org_id = %(org)s and i.vendor_id = %(vid)s"
            " and e.opened_at >= now() - make_interval(days => %(days)s) group by e.type order by n desc",
            p,
        )
        contracts = await _all(
            conn,
            "select title, effective_from, effective_to, countersigned_at from public.contracts"
            " where org_id = %(org)s and vendor_id = %(vid)s order by effective_to desc",
            p,
        )
    return jsonable(
        {
            "vendor": v,
            "window_days": days,
            "invoices": agg,
            "recent_invoices": recent,
            "short_pays": short_pays,
            "exceptions_by_type": by_type,
            "contracts": contracts,
        }
    )


async def get_po_grn(org_id: str, ref: str) -> dict[str, Any]:
    """Purchase order with lines, received quantities and goods receipts. `ref`: PO number, PO id, or an
    invoice id/number (→ its linked PO)."""
    async with read_only() as conn:
        po = await _one(
            conn,
            "select po.id, po.po_number, po.status, po.ordered_at, po.total, po.source,"
            " v.display_name as vendor_name,"
            " l.name as location_name from public.purchase_orders po"
            " join public.vendors v on v.id = po.vendor_id join public.locations l on l.id = po.location_id"
            " where po.org_id = %(org)s and (po.id::text = %(ref)s or upper(po.po_number) = upper(%(ref)s))",
            {"org": org_id, "ref": ref},
        )
        if po is None:
            inv = await _resolve_invoice(conn, org_id, ref)
            if inv is None or inv.get("po_id") is None:
                return _not_found("purchase order", ref)
            return await get_po_grn(org_id, str(inv["po_id"]))
        lines = await _all(
            conn,
            "select pl.line_no, pl.description, pl.qty, pl.uom, pl.unit_price, pl.amount,"
            " coalesce((select sum(g.qty_received) from public.grn_lines g where g.po_line_id = pl.id), 0)"
            " as qty_received from public.po_lines pl where pl.po_id = %s order by pl.line_no",
            (po["id"],),
        )
        grns = await _all(
            conn,
            "select grn_number, received_at, received_by, source from public.goods_receipts"
            " where po_id = %s order by received_at",
            (po["id"],),
        )
    in_full = all(Decimal(ln["qty_received"]) >= Decimal(ln["qty"]) for ln in lines) if lines else None
    return jsonable(
        {"purchase_order": po, "lines": lines, "goods_receipts": grns, "received_in_full": in_full}
    )


_KPI_FALLBACK_SQL = """
with p as (
  select case %(period)s
           when 'qtd' then date_trunc('quarter', now())
           when 'l30' then now() - interval '30 days'
           else date_trunc('month', now()) end as start
)
select %(period)s as period_key, (select start from p)::date as period_start,
  (select count(*) from public.invoices i where i.org_id = %(org)s and i.received_at >= (select start from p)
     and i.duplicate_of is null) as invoices,
  (select avg(case when i.touchless then 1.0 else 0.0 end) from public.invoices i
     where i.org_id = %(org)s and i.received_at >= (select start from p) and i.posted_at is not null)
     as touchless_rate,
  (select count(*) from public.exceptions e where e.org_id = %(org)s and e.status <> 'resolved')
     as exceptions_open,
  (select coalesce(sum(a.hold_amount), 0) from public.approvals a where a.org_id = %(org)s
     and a.action = 'short_pay' and a.decided_at >= (select start from p)) as held_variances,
  (select count(*) from public.approvals a where a.org_id = %(org)s and a.action = 'short_pay'
     and a.decided_at >= (select start from p)) as short_pays,
  (select coalesce(sum(c.amount_usd), 0) from public.cost_ledger c where c.org_id = %(org)s
     and c.kind = 'llm' and c.at >= (select start from p)) as cost_llm
"""


async def get_kpis(org_id: str, period: str = "mtd") -> dict[str, Any]:
    """Operations KPIs for period mtd | qtd | l30 (from mv_ops_period; base-table fallback)."""
    from psycopg import errors

    period = period if period in ("mtd", "qtd", "l30") else "mtd"
    async with read_only() as conn:
        try:
            row = await _one(
                conn,
                "select * from public.mv_ops_period where org_id = %s and period_key = %s",
                (org_id, period),
            )
            source = "mv_ops_period"
        except (errors.UndefinedTable, errors.InsufficientPrivilege):
            await conn.rollback()
            await conn.execute("set transaction read only")
            row = None
        if row is None:
            row = await _one(conn, _KPI_FALLBACK_SQL, {"org": org_id, "period": period})
            source = "base_tables"
    return jsonable({"period": period, "source": source, "kpis": row})


# ------------------------------------------------------------------------------------------ agent tools
@dataclass
class AgentCtx:
    """Run context for agents: org scope, BYOK key (never shown to the model), tool budget, citations."""

    org_id: str
    api_key: str | None = None
    max_tool_calls: int = MAX_TOOL_CALLS
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    chunks: dict[str, Chunk] = field(default_factory=dict)  # ref "K1" → chunk
    query_for_ref: dict[str, str] = field(default_factory=dict)
    data_tools_used: bool = False
    # ref → names that tie an answer to that clause (invoice number, exception id): a contract clause a
    # data tool returned is cited when the answer talks about its exception, even without a [K] ref.
    clause_anchors: dict[str, list[str]] = field(default_factory=dict)

    def ref_for(self, chunk: Chunk, query: str) -> str:
        for ref, c in self.chunks.items():
            if c.chunk_id == chunk.chunk_id:
                return ref
        ref = f"K{len(self.chunks) + 1}"
        self.chunks[ref] = chunk
        self.query_for_ref[ref] = query
        return ref


def _budget(ctx: RunContextWrapper[AgentCtx], name: str, args: dict[str, Any]) -> str | None:
    c = ctx.context
    if len(c.tool_calls) >= c.max_tool_calls:
        return json.dumps(
            {"error": "Tool-call limit reached. Answer now using the results you already have."}
        )
    c.tool_calls.append({"name": name, "args": args})
    return None


@function_tool(name_override="search_kb")
async def tool_search_kb(ctx: RunContextWrapper[AgentCtx], query: str, kind: str | None) -> str:
    """Search the knowledge base (supplier contracts, AP policy, month-end close, vendor notes).
    Each result has a ref like K1 — cite it as [K1] when you use it.

    Args:
        query: what to look for, e.g. "shrimp contract price" or "who can release a fraud hold".
        kind: optional filter: "contract", "policy" or "vendor_note"; null for all.
    """
    if (err := _budget(ctx, "search_kb", {"query": query, "kind": kind})) is not None:
        return err
    if kind not in (None, "contract", "policy", "vendor_note"):
        kind = None
    chunks = await search_kb(
        ctx.context.org_id, query, 5, kinds=[kind] if kind else None, api_key=ctx.context.api_key
    )
    out = []
    for c in chunks:
        ref = ctx.context.ref_for(c, query)
        out.append(
            {
                "ref": ref,
                "title": c.title,
                "clause": c.clause_ref,
                "section": c.heading_path,
                "text": c.content,
            }
        )
    return json.dumps({"results": out} if out else {"results": [], "note": "no matching passages"})


@function_tool(name_override="get_invoice")
async def tool_get_invoice(ctx: RunContextWrapper[AgentCtx], invoice: str) -> str:
    """Invoice header, lines with three-way-match results, and exceptions.

    Args:
        invoice: invoice number as printed (e.g. "PS-88214") or invoice id.
    """
    if (err := _budget(ctx, "get_invoice", {"invoice": invoice})) is not None:
        return err
    ctx.context.data_tools_used = True
    return json.dumps(await get_invoice_summary(ctx.context.org_id, invoice))


PASSING_VERDICTS = frozenset({None, "matched", "favorable"})  # lines that are not why an invoice is held


async def run_get_exception(ctx: AgentCtx, ref: str) -> str:
    """`get_exception` plus the contract clauses behind its held lines, registered as citable refs."""
    ctx.data_tools_used = True
    ex = await get_exception(ctx.org_id, ref)
    clauses: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for ln in ex.get("lines") or []:
        key = (ln.get("clause_ref"), ln.get("contract_id"))
        if not key[0] or ln.get("verdict") in PASSING_VERDICTS or key in seen:
            continue
        seen.add(key)
        chunk = await clause_chunk(ctx.org_id, key[0], key[1])
        if chunk is None:
            continue
        kref = ctx.ref_for(chunk, f"clause {key[0]}")
        e, inv = ex.get("exception") or {}, ex.get("invoice") or {}
        ctx.clause_anchors[kref] = [
            n for n in (inv.get("invoice_number"), str(e.get("exception_id") or "")) if n
        ]
        clauses.append({"ref": kref, "clause": chunk.clause_ref, "title": chunk.title, "text": chunk.content})
    if clauses:
        ex["contract_clauses"] = clauses
    return json.dumps(ex)


@function_tool(name_override="get_exception")
async def tool_get_exception(ctx: RunContextWrapper[AgentCtx], ref: str) -> str:
    """An exception (why an invoice is held) with the deterministic recommendation and latest decision.
    `contract_clauses` holds the contract clauses behind the held lines; cite them by ref like [K1].

    Args:
        ref: exception id, or an invoice number/id (returns its most recent exception).
    """
    if (err := _budget(ctx, "get_exception", {"ref": ref})) is not None:
        return err
    return await run_get_exception(ctx.context, ref)


@function_tool(name_override="vendor_history")
async def tool_vendor_history(ctx: RunContextWrapper[AgentCtx], vendor: str, days: int) -> str:
    """A vendor's recent activity: invoices, accepted short-pays, exceptions by type, contracts on file.

    Args:
        vendor: vendor name (e.g. "Protein Supplier") or id.
        days: look-back window in days (use 90 unless asked otherwise).
    """
    if (err := _budget(ctx, "vendor_history", {"vendor": vendor, "days": days})) is not None:
        return err
    ctx.context.data_tools_used = True
    return json.dumps(await vendor_history(ctx.context.org_id, vendor, days or 90))


@function_tool(name_override="get_po_grn")
async def tool_get_po_grn(ctx: RunContextWrapper[AgentCtx], ref: str) -> str:
    """Purchase order lines with received quantities and goods receipts.

    Args:
        ref: PO number (e.g. "PO-RS-1873"), or an invoice number to use its linked PO.
    """
    if (err := _budget(ctx, "get_po_grn", {"ref": ref})) is not None:
        return err
    ctx.context.data_tools_used = True
    return json.dumps(await get_po_grn(ctx.context.org_id, ref))


@function_tool(name_override="get_kpis")
async def tool_get_kpis(ctx: RunContextWrapper[AgentCtx], period: str) -> str:
    """Operations KPIs (invoices, touchless rate, held amounts, cost) computed in SQL.

    Args:
        period: "mtd" (month to date), "qtd" (quarter to date) or "l30" (last 30 days).
    """
    if (err := _budget(ctx, "get_kpis", {"period": period})) is not None:
        return err
    ctx.context.data_tools_used = True
    return json.dumps(await get_kpis(ctx.context.org_id, period))


COPILOT_TOOLS = [
    tool_search_kb,
    tool_get_invoice,
    tool_get_exception,
    tool_vendor_history,
    tool_get_po_grn,
    tool_get_kpis,
]
RESOLUTION_TOOLS = [tool_search_kb, tool_vendor_history, tool_get_po_grn]
