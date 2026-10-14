"""Integration fixtures: local Supabase (after B's migrations + `python -m app.demo.seed`).

Each scenario deletes today's copy of its hero document(s) and re-releases them, so tests are
repeatable against the dev database (they do touch the demo org's data for today).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.db.pool import as_user, close_pool, connection, open_pool
from app.demo import replay
from app.orchestrator import Clock, drive_run
from app.repo.sql import J, all_, one, val

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ORG = "992e72b7-9d9b-5104-9051-f5ef581c99e0"
USERS = {
    "elena": "c1f2540f-4d0c-5e8b-ba81-a0dd3de7ab39",
    "tom": "063f728d-c685-5ba7-8e87-dac4f869ab91",
    "viewer": "2ff0bef9-b811-57ae-98a9-3cc42e42de8d",
    "clerk": "9779a180-97cf-5ce6-86b7-a5eeb87bf626",
    "admin": "386eaeb3-e4ef-5f37-9a8f-0db42b251b60",
}


@pytest.fixture
async def db() -> AsyncIterator[None]:
    try:
        await open_pool()
        async with connection() as conn:
            if not await val(conn, "select 1 from orgs where id = %s", (ORG,)):
                pytest.skip("demo org not seeded (run: uv run python -m app.demo.seed)")
            if not await val(conn, "select to_regproc('public.rpc_decide_exception') is not null as ok"):
                pytest.skip("decision RPCs not migrated")
    except Exception as e:  # pragma: no cover
        await close_pool()
        pytest.skip(f"local Supabase not reachable: {e}")
    yield
    await close_pool()


def hero_docs(key: str) -> list[Any]:
    day = replay.local_today()
    return [d for d in replay.schedule_for(day) if d.hero == key]


async def reset_hero(key: str) -> None:
    """Delete today's documents for a hero (cascades to invoices, runs, events, exceptions, postings)."""
    ids = [d.document_id for d in hero_docs(key)]
    async with connection() as conn, conn.transaction():
        await conn.execute("update pipeline_runs set wait_exception_id = null where document_id = any(%s)", (ids,))
        await conn.execute("delete from documents where id = any(%s)", (ids,))


async def release(doc: Any, *, inject: dict[str, Any] | None = None) -> str:
    async with connection() as conn, conn.transaction():
        await replay.persist_masters(conn, ORG, [doc])
        await replay.refresh_unlisted_vendor(conn, replay.catalog_for(replay.local_today()))
    rel = await replay.release_doc(doc, render=False)
    assert rel is not None
    if inject:
        async with connection() as conn, conn.transaction():
            await conn.execute("update pipeline_runs set context = context || %s where id = %s", (J({"inject": inject}), rel.run_id))
    await drive(rel.run_id)
    return rel.run_id


async def drive(run_id: str) -> str:
    return await drive_run(replay.sync_engine(), run_id, Clock(), connection_factory=connection)


async def run_row(run_id: str) -> dict[str, Any]:
    async with connection() as conn:
        r = await one(conn, "select * from pipeline_runs where id = %s", (run_id,))
    assert r is not None
    return r


async def invoice_of(run_id: str) -> dict[str, Any]:
    async with connection() as conn:
        r = await one(conn, "select i.* from invoices i join pipeline_runs r on r.invoice_id = i.id where r.id = %s", (run_id,))
    assert r is not None
    return r


async def events(run_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        return await all_(conn, "select stage::text, status::text, summary, detail from pipeline_events where run_id = %s order by at, id", (run_id,))


async def decide(user: str, exception_id: str, action: str, *, pay: Any = None, hold: Any = None,
                 comment: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    async with connection() as conn, conn.transaction():
        await as_user(conn, USERS[user])
        res = await val(
            conn,
            "select public.rpc_decide_exception(%s, %s::public.decision_action, %s, %s, %s, %s, %s) as r",
            (exception_id, action, pay, hold, comment, 60, J(extra or {})),
        )
    return res if isinstance(res, dict) else json.loads(res)


async def confirm(user: str, invoice_id: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    async with connection() as conn, conn.transaction():
        await as_user(conn, USERS[user])
        res = await val(conn, "select public.rpc_confirm_fields(%s, %s, %s) as r", (invoice_id, J(fields), 45))
    return res if isinstance(res, dict) else json.loads(res)
