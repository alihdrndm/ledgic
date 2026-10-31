"""Seed builders (pure) + an optional integration run against local Supabase."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.demo.corpus import build_catalog
from app.demo.corpus.catalog import ORG_ID
from app.demo.seed import (
    USERS,
    eval_rows,
    history_rows,
    master_rows,
    score_doc,
    short_pay_bundle,
    simulated_read,
    week_starts,
)

TODAY = date(2026, 10, 14)
FIXTURES = Path(__file__).resolve().parents[4] / "contracts" / "fixtures.json"


@pytest.fixture(scope="module")
def cat():
    return build_catalog(TODAY)


def test_users_match_contract_fixtures():
    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert fx["org"]["id"] == ORG_ID
    got = {u.key: (u.id, u.email, u.full_name, u.initials, u.role) for u in USERS}
    want = {
        k: (v["id"], v["email"], v["full_name"], v["initials"], v["role"]) for k, v in fx["users"].items()
    }
    assert got == want
    assert {u.key: u.password_env for u in USERS if u.password_env} == fx["demo_passwords_env"]


def test_master_rows(cat):
    m = master_rows(cat)
    assert len(m["locations"]) == 34
    assert len(m["entities"]) == 3
    assert {r["code"] for r in m["locations"]} >= {"RS", "BS", "CM", "LS", "OM", "PH", "SB", "CS"}
    assert len(m["gl_accounts"]) == 3 * 8
    shrimp = next(it for it in cat.items if it.description == "Shrimp 16/20 IQF 2lb × 10")
    cp = next(p for p in m["contract_prices"] if p["item_id"] == shrimp.id)
    assert cp["unit_price"] == Decimal("3.68") and cp["clause_ref"] == "4.2"
    protein = next(c for c in m["contracts"] if c["title"] == "Vendor agreement 2026")
    assert protein["effective_to"] == date(2027, 3, 31)  # rolling: last day of the 5th month after today (D8)
    unlisted = next(v for v in m["vendors"] if v["display_name"] == "Unlisted Supplier")
    assert unlisted["created_by"] == next(u.id for u in USERS if u.key == "admin")
    assert unlisted["bank_fingerprint"] != unlisted["w9_bank_fingerprint"]
    assert all("embedding" not in r for r in m["items"])  # filled by the AI seed


def test_master_rows_are_deterministic(cat):
    a, b = master_rows(cat), master_rows(build_catalog(TODAY))
    assert [r["id"] for r in a["vendors"]] == [r["id"] for r in b["vendors"]]
    assert [r["id"] for r in a["contract_prices"]] == [r["id"] for r in b["contract_prices"]]


def test_history_is_small_coded_and_older_than_backfill(cat):
    h = history_rows(cat)
    assert 2000 <= len(h.lines) <= 3000
    assert all(ln["gl_account_id"] for ln in h.lines)
    assert max(i["received_at"].date() for i in h.invoices) < date(2026, 9, 14)
    assert len({i["invoice_number"] for i in h.invoices}) == len(h.invoices)
    assert len({p["po_number"] for p in h.pos}) == len(h.pos)
    for inv in h.invoices[:50]:
        lines = [ln for ln in h.lines if ln["invoice_id"] == inv["id"]]
        assert inv["subtotal"] == sum(ln["amount"] for ln in lines)
        assert inv["total"] == inv["subtotal"] + inv["tax"]
    # re-running yields the same ids (idempotent upserts)
    assert [i["id"] for i in history_rows(cat).invoices] == [i["id"] for i in h.invoices]


def test_prior_short_pays(cat):
    b = short_pay_bundle(cat)
    assert [x["approval"]["hold_amount"] for x in b] == [Decimal("61.60"), Decimal("47.20")]
    for x in b:
        appr, inv = x["approval"], x["invoice"]
        assert appr["pay_amount"] + appr["hold_amount"] == inv["total"]
        assert (TODAY - appr["decided_at"].date()).days <= 90
        assert x["exception"]["status"] == "resolved" and x["run"]["status"] == "succeeded"
    assert [x["recommendation"]["confidence"] for x in b] == [Decimal("0.80"), Decimal("0.87")]


def test_eval_scoring_is_a_real_comparison(cat):
    from app.demo.corpus import plan_day
    from app.demo.corpus.rng import rng_for

    doc = plan_day(cat, date(2026, 9, 1), n=5, include_heroes=False)[0]
    perfect = {
        k: f["value"] for k, f in doc.simulated_extraction.items() if isinstance(f, dict) and "value" in f
    }
    for i, ln in enumerate(doc.simulated_extraction["lines"]):
        perfect.update({f"lines[{i}].{k}": v["value"] for k, v in ln.items()})
    scores = score_doc(doc, perfect)
    assert all(lab == ok for lab, ok in scores.values())
    wrong = dict(perfect, total="999999.99")
    assert score_doc(doc, wrong)["total"] == (1, 0)
    # a simulated read differs from the truth on some fields over many documents
    r = rng_for(1, "t")
    reads = [simulated_read(d, r) for d in plan_day(cat, date(2026, 9, 2), n=60, include_heroes=False)]
    assert reads


def test_eval_rows_shape(cat):
    rows = eval_rows(cat, weeks=2, sample=40, docs_per_day=8)
    assert [r["week_start"] for r in rows] == week_starts(TODAY, 2)
    for r in rows:
        assert r["week_start"].weekday() == 0
        assert 0 < r["fields_correct"] <= r["fields_labeled"]
        assert 0.85 < r["fields_correct"] / r["fields_labeled"] < 1.0
        assert r["prompt_version"] == "p-1"


@pytest.mark.integration
async def test_seed_against_local_supabase():
    import asyncio
    import sys

    if sys.platform == "win32" and not isinstance(asyncio.get_running_loop(), asyncio.SelectorEventLoop):
        pytest.skip("psycopg async needs a selector event loop on Windows")
    from app.db.pool import close_pool, connection, open_pool
    from app.demo.corpus.heroes import PRIOR_SHORT_PAYS
    from app.demo.corpus.rng import stable_uuid
    from app.demo.seed import seed
    from app.repo.sql import val

    # The seeded history's own approvals (stable ids): scenarios on the same database add more short-pays.
    seeded_ids = [
        stable_uuid("approval", f"prior-short-pay:{sp['invoice_number']}") for sp in PRIOR_SHORT_PAYS
    ]

    await open_pool()
    try:
        first = await seed(TODAY, with_eval=False)
        second = await seed(TODAY, with_eval=False)
        async with connection() as conn:
            seeded_short_pays = await val(
                conn,
                "select count(*) from public.approvals where action = 'short_pay' and id = any(%s::uuid[])",
                (seeded_ids,),
            )
    finally:
        await close_pool()
    assert first["counts"] == second["counts"]
    assert first["counts"]["locations"] == 34
    assert seeded_short_pays == 2
