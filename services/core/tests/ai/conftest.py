"""Fixtures for AI tests.

Unit tests never touch the network or the DB (gateway uses an in-memory budget store, retrieval is
mocked). DB-backed tests use a throwaway org (random slug, deleted afterwards) and skip when the local
Supabase DB is not reachable.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app.ai.gateway import LlmGateway, set_gateway
from app.config import Settings, get_settings

REPO = Path(__file__).resolve().parents[4]
HEROES_DIR = REPO / "tools" / "corpus" / "fixtures" / "heroes"


def pytest_asyncio_loop_factories(config, item):
    # psycopg's async driver cannot run on Windows' default Proactor loop.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"asyncio": asyncio.new_event_loop}


class MemoryBudgetStore:
    """In-memory stand-in for llm_budget_reserve / llm_budget_settle / cost_ledger."""

    def __init__(self, cap: Decimal = Decimal("0.50")) -> None:
        self.cap = cap
        self.reserved = Decimal(0)
        self.spent = Decimal(0)
        self.reservations: dict[str, Decimal] = {}
        self.settled: dict[str, Decimal] = {}
        self.ledger: list[dict[str, Any]] = []
        self.reserve_calls = 0

    async def reserve(self, est: Decimal, cap: Decimal) -> str | None:
        self.reserve_calls += 1
        if self.spent + self.reserved + est > self.cap:
            return None
        rid = str(uuid.uuid4())
        self.reservations[rid] = est
        self.reserved += est
        return rid

    async def settle(self, reservation_id: str, actual: Decimal) -> None:
        if reservation_id in self.settled:
            return
        self.reserved -= self.reservations[reservation_id]
        self.spent += actual
        self.settled[reservation_id] = actual

    async def record_cost(self, org_id: str | None, run_id: str | None, amount: Decimal, meta: dict) -> None:
        self.ledger.append({"org_id": org_id, "run_id": run_id, "amount": amount, "meta": meta})


def make_settings(**kw: Any) -> Settings:
    base = {"llm_mode": "fixture", "openai_api_key": "", "llm_daily_cap_usd": Decimal("0.50")}
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def store() -> MemoryBudgetStore:
    return MemoryBudgetStore()


@pytest.fixture
def live_gateway(store: MemoryBudgetStore):
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key="sk-owner-test"), store)
    set_gateway(gw)
    yield gw
    set_gateway(None)


@pytest.fixture
def fixture_gateway(store: MemoryBudgetStore):
    gw = LlmGateway(make_settings(llm_mode="fixture", openai_api_key="sk-owner-test"), store)
    set_gateway(gw)
    yield gw
    set_gateway(None)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any attempt to build an OpenAI client fails the test."""
    import openai

    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("network client constructed")

    monkeypatch.setattr(openai, "AsyncOpenAI", boom)
    monkeypatch.setattr(openai, "OpenAI", boom)


def load_hero(name: str) -> dict[str, Any]:
    return json.loads((HEROES_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------ DB
def _db_reachable() -> str | None:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=3) as c:
            c.execute("select 1 from public.kb_chunks limit 1")
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"local Supabase DB not reachable / not migrated ({type(exc).__name__})"
    return None


DB_SKIP = _db_reachable()
needs_db = pytest.mark.skipif(DB_SKIP is not None, reason=DB_SKIP or "")


@pytest.fixture
async def kb_org() -> AsyncIterator[str]:
    """Throwaway org with the Protein Supplier vendor + contract and the full KB indexed (fixture mode)."""
    from app.ai.rag.index import index_kb
    from app.db import pool as db_pool

    org_id = str(uuid.uuid4())
    url = get_settings().database_url
    with psycopg.connect(url) as c:
        c.execute(
            "insert into public.orgs (id, slug, name, is_demo) values (%s, %s, 'AI test org', true)",
            (org_id, f"ai-test-{org_id[:8]}"),
        )
        vid = c.execute(
            "insert into public.vendors (org_id, display_name) values (%s, 'Protein Supplier') returning id",
            (org_id,),
        ).fetchone()[0]
        c.execute(
            "insert into public.contracts (org_id, vendor_id, title, effective_from, effective_to,"
            " countersigned_at)"
            " values (%s, %s, 'Vendor agreement 2026', '2026-03-01', '2027-03-31', '2026-03-03')",
            (org_id, vid),
        )
    set_gateway(LlmGateway(make_settings(llm_mode="fixture"), MemoryBudgetStore()))
    await db_pool.open_pool()
    try:
        await index_kb(org_id)
        yield org_id
    finally:
        await db_pool.close_pool()
        set_gateway(None)
        with psycopg.connect(url) as c:
            c.execute("delete from public.orgs where id = %s", (org_id,))
