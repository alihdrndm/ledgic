"""DB-backed checks of the AI tools, resolution drafts, copilot facts and budget RPCs.

Seeds a throwaway org with the PS-88214 hero (contract clause 4.2, PO/GRN, match results, exception,
recommendation, two prior accepted short-pays) and deletes it afterwards. Skips without a local DB.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import psycopg
import pytest

from app.ai.gateway import LlmGateway, PgBudgetStore, set_gateway
from app.config import get_settings

from .conftest import MemoryBudgetStore, make_settings, needs_db

pytestmark = needs_db


def _seed(c: psycopg.Connection, org: str) -> dict[str, str]:
    def one(sql: str, *p: object) -> str:
        row = c.execute(sql + " returning id", p).fetchone()
        assert row is not None
        return str(row[0])

    c.execute(
        "insert into public.orgs (id, slug, name, is_demo) values (%s, %s, 'AI db test', true)",
        (org, f"ai-db-{org[:8]}"),
    )
    actor = str(uuid.uuid4())
    c.execute(
        "insert into auth.users (id, email, aud, role) values (%s, %s, 'authenticated', 'authenticated')",
        (actor, f"ai-{actor[:8]}@test.local"),
    )
    ent = one(
        "insert into public.entities (org_id, name, short_code, erp)"
        " values (%s, 'Entity 1', 'E1', 'quickbooks')",
        org,
    )
    loc = one(
        "insert into public.locations (org_id, entity_id, code, name) values (%s, %s, 'RS', 'Riverside')",
        org,
        ent,
    )
    ven = one("insert into public.vendors (org_id, display_name) values (%s, 'Protein Supplier')", org)
    item = one(
        "insert into public.items (org_id, item_key, description, uom) values (%s, 'PS-0001',"
        " 'Shrimp 16/20 IQF 2lb × 10', 'lb')",
        org,
    )
    con = one(
        "insert into public.contracts (org_id, vendor_id, title, effective_from, effective_to,"
        " countersigned_at)"
        " values (%s, %s, 'Vendor agreement 2026', '2026-03-01', '2027-03-31', '2026-03-03')",
        org,
        ven,
    )
    cp = one(
        "insert into public.contract_prices (contract_id, item_id, uom, unit_price, clause_ref)"
        " values (%s, %s, 'lb', 3.68, '4.2')",
        con,
        item,
    )
    po = one(
        "insert into public.purchase_orders (org_id, entity_id, location_id, vendor_id, po_number,"
        " ordered_at, total) values (%s, %s, %s, %s, 'PO-RS-1873', now() - interval '3 days', 2759.60)",
        org,
        ent,
        loc,
        ven,
    )
    pol = one(
        "insert into public.po_lines (po_id, line_no, item_id, description, qty, uom, unit_price, amount)"
        " values (%s, 1, %s, 'Shrimp 16/20 IQF 2lb × 10', 200, 'lb', 3.68, 736.00)",
        po,
        item,
    )
    grn = one(
        "insert into public.goods_receipts (org_id, po_id, grn_number, received_at) values (%s, %s,"
        " 'GRN-RS-4410', now() - interval '1 day')",
        org,
        po,
    )
    c.execute(
        "insert into public.grn_lines (grn_id, po_line_id, qty_received, uom) values (%s, %s, 200, 'lb')",
        (grn, pol),
    )

    def invoice(number: str, total: str, days_ago: int) -> str:
        doc = one(
            "insert into public.documents (org_id, channel, storage_path, sha256, mime) values"
            " (%s, 'email', 'x', %s, 'application/pdf')",
            org,
            uuid.uuid4().hex,
        )
        return one(
            "insert into public.invoices (org_id, document_id, vendor_id, entity_id, location_id, po_id,"
            " invoice_number, invoice_date, total, subtotal, status, received_at) values (%s, %s, %s, %s,"
            " %s, %s, %s, current_date, %s, %s, 'matched', now() - make_interval(days => %s))",
            org,
            doc,
            ven,
            ent,
            loc,
            po,
            number,
            total,
            total,
            days_ago,
        )

    inv = invoice("PS-88214", "2847.60", 0)
    line = one(
        "insert into public.invoice_lines (invoice_id, line_no, description, item_id, qty, uom, unit_price,"
        " amount, confidences, po_line_id) values (%s, 1, 'Shrimp 16/20 IQF 2lb × 10', %s, 200, 'lb', 4.12,"
        " 824.00, '{}', %s)",
        inv,
        item,
        pol,
    )
    mr = one(
        "insert into public.match_results (invoice_id, verdict, tolerance_pct, tolerance_abs, expected_total,"
        " total_delta, lines_verified, lines_total, duration_ms) values (%s, 'price_variance', 0.02, 25,"
        " 2759.60, 88.00, 4, 5, 12)",
        inv,
    )
    c.execute(
        "insert into public.match_line_results (match_result_id, invoice_line_id, po_line_id, grn_qty,"
        " expected_unit_price, expected_source, contract_price_id, expected_amount, delta_amount, delta_pct,"
        " allowed_amount, verdict, note) values (%s, %s, %s, 200, 3.68, 'contract', %s, 736.00, 88.00,"
        " 0.11957, 14.72, 'price_variance', 'ordered 200 · received 200 · invoiced 200')",
        (mr, line, pol, cp),
    )
    exc = one(
        "insert into public.exceptions (org_id, invoice_id, type, amount_at_risk, reason, sla_due_at)"
        " values (%s, %s, 'price_variance', 88.00, 'shrimp 12%% over contract', now() + interval '24 hours')",
        org,
        inv,
    )
    reasons = [
        {
            "template_id": "grn_full",
            "text": "Goods were received in full, so there is no quantity basis to dispute — only price.",
            "facts": {},
        }
    ]
    c.execute(
        "insert into public.recommendations (exception_id, action, pay_amount, hold_amount, confidence,"
        " reasons) values (%s, 'short_pay', 2759.60, 88.00, 0.94, %s::jsonb)",
        (exc, json.dumps(reasons)),
    )
    for number, total, hold, days in (
        ("PS-87710", "1961.60", "61.60", 20),
        ("PS-87102", "2057.35", "47.20", 50),
    ):
        pinv = invoice(number, total, days)
        pexc = one(
            "insert into public.exceptions (org_id, invoice_id, type, status, amount_at_risk, reason,"
            " sla_due_at, resolved_at) values (%s, %s, 'price_variance', 'resolved', %s,"
            " 'shrimp over contract', now(), now())",
            org,
            pinv,
            hold,
        )
        c.execute(
            "insert into public.approvals (org_id, exception_id, actor_id, action, pay_amount, hold_amount,"
            " decided_at) values (%s, %s, %s, 'short_pay', %s, %s, now() - make_interval(days => %s))",
            (org, pexc, actor, Decimal(total) - Decimal(hold), hold, days),
        )
    return {"exception_id": exc, "invoice_id": inv, "actor": actor}


@pytest.fixture
async def ps_org() -> AsyncIterator[tuple[str, dict[str, str]]]:
    from app.ai.rag.index import index_kb
    from app.db import pool as db_pool

    org = str(uuid.uuid4())
    url = get_settings().database_url
    with psycopg.connect(url) as c:
        ids = _seed(c, org)
    set_gateway(LlmGateway(make_settings(llm_mode="fixture"), MemoryBudgetStore()))
    await db_pool.open_pool()
    try:
        await index_kb(org)
        yield org, ids
    finally:
        await db_pool.close_pool()
        set_gateway(None)
        with psycopg.connect(url) as c:
            c.execute("delete from public.orgs where id = %s", (org,))
            c.execute("delete from auth.users where id = %s", (ids["actor"],))


async def test_data_tools(ps_org) -> None:
    from app.ai import tools

    org, ids = ps_org
    ex = await tools.get_exception(org, "PS-88214")
    assert ex["exception"]["exception_id"] == ids["exception_id"]
    assert ex["recommendation"]["pay_amount"] == "2759.60" and ex["recommendation"]["hold_amount"] == "88.00"
    assert ex["recommendation"]["reasons"][0].startswith("Goods were received in full")
    [ln] = ex["lines"]
    assert (
        ln["clause_ref"] == "4.2"
        and ln["expected_unit_price"] == "3.6800"
        and ln["po_unit_price"] == "3.6800"
    )
    assert (await tools.get_exception(org, ids["exception_id"]))["invoice"]["invoice_number"] == "PS-88214"

    hist = await tools.vendor_history(org, "protein supplier", 90)
    assert sorted(sp["hold_amount"] for sp in hist["short_pays"]) == ["47.20", "61.60"]
    assert hist["contracts"][0]["title"] == "Vendor agreement 2026"
    assert hist["invoices"]["invoices"] == 3

    po = await tools.get_po_grn(org, "PS-88214")
    assert po["purchase_order"]["po_number"] == "PO-RS-1873" and po["received_in_full"] is True
    assert po["goods_receipts"][0]["grn_number"] == "GRN-RS-4410"

    inv = await tools.get_invoice_summary(org, "ps88214")
    assert inv["invoice"]["match_verdict"] == "price_variance" and len(inv["exceptions"]) == 1

    q = await tools.list_exceptions(org)
    assert q["count"] == 1 and q["exceptions"][0]["invoice_number"] == "PS-88214"

    kpis = await tools.get_kpis(org, "mtd")
    assert kpis["source"] in ("mv_ops_period", "base_tables")

    assert "error" in await tools.get_exception(org, "XX-0000")
    assert "error" in await tools.vendor_history(org, "Nobody Inc")


async def test_resolution_draft_recorded_and_persisted(ps_org) -> None:
    from app.ai.resolution import draft_for_exception, latest_draft

    org, ids = ps_org
    d = await draft_for_exception(ids["exception_id"], kind="explanation")
    assert d.mode == "recorded" and d.guard["passed"] and d.draft_id
    assert "$61.60 and $47.20" in d.body_md and "March 31, 2027" in d.body_md
    assert d.citations and d.citations[0]["clause_ref"] == "4.2"
    again = await draft_for_exception(ids["exception_id"], kind="explanation")
    assert again.draft_id == d.draft_id  # latest stored draft is returned unless regenerate
    notice = await draft_for_exception(ids["exception_id"], kind="vendor_notice", regenerate=True)
    assert notice.body_md.startswith("**Subject:**") and "$2,759.60" in notice.body_md
    stored = await latest_draft(ids["exception_id"], "vendor_notice")
    assert stored is not None and stored.draft_id == notice.draft_id and stored.mode == "recorded"


async def test_copilot_on_hold_question(ps_org) -> None:
    from app.ai.copilot import ask

    org, _ = ps_org
    ans = await ask(org, "Why is PS-88214 on hold?", use_cache=False)
    assert ans.mode == "retrieval_only"
    assert "pay $2,759.60, hold $88.00" in ans.answer_md
    assert any(c["clause_ref"] == "4.2" for c in ans.citations)


async def test_budget_rpcs_reserve_settle() -> None:
    from app.db import pool as db_pool

    url = get_settings().database_url
    with psycopg.connect(url) as c:
        if not c.execute(
            "select to_regprocedure('public.llm_budget_reserve(numeric, numeric)') is not null"
        ).fetchone()[0]:
            pytest.skip("llm_budget RPCs not migrated")
    store = PgBudgetStore()
    cap = get_settings().llm_daily_cap_usd
    await db_pool.open_pool()
    try:
        rid = await store.reserve(Decimal("0.000001"), cap)
        assert rid is not None
        await store.settle(rid, Decimal("0.000001"))
        await store.settle(rid, Decimal("0.000001"))  # idempotent
        assert await store.reserve(Decimal("1000"), cap) is None  # over the cap → refused
    finally:
        await db_pool.close_pool()
    with psycopg.connect(url) as c:
        status = c.execute(
            "select status, actual_usd from public.llm_budget_reservations where id = %s", (rid,)
        ).fetchone()
    assert status == ("settled", Decimal("0.000001"))


async def test_web_suggested_questions_precompute(ps_org) -> None:
    from app.ai.copilot import SUGGESTED_QUESTIONS, ask, cache_get, cache_put

    org, _ = ps_org
    web = SUGGESTED_QUESTIONS[:5]
    answers = {}
    for q in web:
        ans = await ask(org, q, use_cache=False)
        await cache_put(org, q, ans)
        answers[q] = ans
    assert answers[web[1]].citations[0]["clause_ref"] == "4.2"
    assert "$3.68" in answers[web[1]].citations[0]["quote"]
    assert any(c["kind"] == "policy" and c["clause_ref"] == "2" for c in answers[web[2]].citations)
    assert "0 of 1 open exceptions block payment" in answers[web[3]].answer_md
    assert answers[web[4]].citations[0]["clause_ref"] == "9"
    # cached except the live-data queue question
    assert (
        await cache_get(org, "what does clause 4.2 of the protein supplier agreement say about shrimp")
    ) is not None
    assert (await cache_get(org, web[3])) is None
