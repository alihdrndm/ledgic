"""Fixtures for MCP tests: a throwaway org with a viewer and an AP manager, plus tokens.

DB-backed tests skip (with the reason) when the local Supabase DB is not reachable. Data lives in a fresh
org with a random slug and is deleted afterwards, so it never collides with the demo seed.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import psycopg
import pytest

from app.config import get_settings
from app.db import pool as db_pool
from app.mcp import auth


def pytest_asyncio_loop_factories(config, item):
    # psycopg's async driver cannot run on Windows' default Proactor loop.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"asyncio": asyncio.new_event_loop}


def _db_reachable() -> str | None:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=3) as c:
            c.execute("select 1 from public.mcp_tokens limit 1")
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"local Supabase DB not reachable / not migrated ({type(exc).__name__}: {exc})"
    return None


DB_SKIP = _db_reachable()
needs_db = pytest.mark.skipif(DB_SKIP is not None, reason=DB_SKIP or "")


def relation_exists(name: str) -> bool:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=3) as c:
            row = c.execute("select to_regclass(%s) is not null", (f"public.{name}",)).fetchone()
            return bool(row and row[0])
    except Exception:
        return False


def function_exists(name: str) -> bool:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=3) as c:
            row = c.execute(
                "select exists(select 1 from pg_proc "
                "where proname = %s and pronamespace = 'public'::regnamespace)",
                (name,),
            ).fetchone()
            return bool(row and row[0])
    except Exception:
        return False


@dataclass
class Seed:
    org_id: str
    viewer_id: str
    manager_id: str
    viewer_read: str  # raw tokens
    viewer_decide: str  # viewer with decide scope: DB must still refuse
    manager_read: str
    manager_decide: str
    revoked: str
    invoice_number: str = "MCP-1001"
    exception_id: str = ""


@pytest.fixture
async def pool() -> AsyncIterator[None]:
    if DB_SKIP:
        pytest.skip(DB_SKIP)
    await db_pool.open_pool()
    try:
        yield
    finally:
        await db_pool.close_pool()
        auth.use_local_token(None)


@pytest.fixture
def seed() -> Seed:
    if DB_SKIP:
        pytest.skip(DB_SKIP)
    org_id, viewer_id, manager_id = (str(uuid.uuid4()) for _ in range(3))
    tokens = {k: auth.generate_token() for k in ("vr", "vd", "mr", "md", "rv")}
    with psycopg.connect(get_settings().database_url) as c:
        c.execute(
            "insert into public.orgs (id, slug, name, is_demo) values (%s, %s, 'MCP test org', true)",
            (org_id, f"mcp-test-{org_id[:8]}"),
        )
        c.execute("insert into public.org_settings (org_id) values (%s) on conflict do nothing", (org_id,))
        for uid, role, name in (
            (viewer_id, "viewer", "MCP Viewer"),
            (manager_id, "ap_manager", "MCP Manager"),
        ):
            c.execute(
                "insert into auth.users (id, email, aud, role) "
                "values (%s, %s, 'authenticated', 'authenticated')",
                (uid, f"{uid[:8]}@mcp-test.ledgic.dev"),
            )
            c.execute(
                "insert into public.profiles (user_id, full_name, initials) values (%s, %s, 'MT')",
                (uid, name),
            )
            c.execute(
                "insert into public.memberships (org_id, user_id, role) "
                "values (%s, %s, %s::public.member_role)",
                (org_id, uid, role),
            )
        rows = [
            ("vr", viewer_id, ["read"]),
            ("vd", viewer_id, ["read", "decide"]),
            ("mr", manager_id, ["read"]),
            ("md", manager_id, ["read", "decide"]),
            ("rv", manager_id, ["read", "decide"]),
        ]
        for key, uid, scopes in rows:
            c.execute(
                "insert into public.mcp_tokens (user_id, org_id, name, token_hash, scopes, revoked_at) "
                "values (%s, %s, %s, %s, %s, case when %s then now() end)",
                (uid, org_id, f"test-{key}", auth.hash_token(tokens[key]), scopes, key == "rv"),
            )
        # One invoice with an open price-variance exception ($50 at risk, inside the manager limit).
        doc_id, inv_id, exc_id = (str(uuid.uuid4()) for _ in range(3))
        c.execute(
            "insert into public.documents (id, org_id, channel, storage_path, sha256, mime) "
            "values (%s, %s, 'upload', 'test/mcp.pdf', %s, 'application/pdf')",
            (doc_id, org_id, doc_id.replace("-", "")),
        )
        c.execute(
            "insert into public.invoices (id, org_id, document_id, invoice_number, subtotal, total, status, "
            "received_at) values (%s, %s, %s, 'MCP-1001', 1000.00, 1000.00, 'awaiting_decision', now())",
            (inv_id, org_id, doc_id),
        )
        c.execute(
            "insert into public.exceptions "
            "(id, org_id, invoice_id, type, amount_at_risk, reason, sla_due_at) "
            "values (%s, %s, %s, 'price_variance', 50.00, 'Line 1 over contract price', "
            "now() + interval '1 day')",
            (exc_id, org_id, inv_id),
        )
    yield Seed(
        org_id=org_id,
        viewer_id=viewer_id,
        manager_id=manager_id,
        viewer_read=tokens["vr"],
        viewer_decide=tokens["vd"],
        manager_read=tokens["mr"],
        manager_decide=tokens["md"],
        revoked=tokens["rv"],
        exception_id=exc_id,
    )
    with psycopg.connect(get_settings().database_url) as c:
        # demo_purge_org also clears the (immutable) audit rows a decision test writes.
        c.execute("select public.demo_purge_org(%s)", (org_id,))
        c.execute("delete from auth.users where id in (%s, %s)", (viewer_id, manager_id))
