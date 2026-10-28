"""MCP server tests via the SDK's in-memory client (stdio-equivalent auth path: `use_local_token`)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp import Client

from app.mcp import auth
from app.mcp.server import build_server

from .conftest import Seed, function_exists, needs_db, relation_exists

EXPECTED_TOOLS = {
    "list_exceptions",
    "get_invoice",
    "explain_match",
    "search_contracts",
    "ask_ledgic",
    "get_kpis",
    "verify_audit_chain",
    "decide_exception",
}


def _text(result: Any) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


def _data(result: Any) -> dict[str, Any]:
    assert not result.is_error, _text(result)
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    return json.loads(_text(result))


# ---- surface (no DB) ----------------------------------------------------------------------------


async def test_lists_tools_resources_prompts():
    async with Client(build_server()) as client:
        tools = (await client.list_tools()).tools
        names = {t.name for t in tools}
        assert names == EXPECTED_TOOLS
        for t in tools:
            assert t.description and len(t.description) > 60, t.name
        by_name = {t.name: t for t in tools}
        assert by_name["get_kpis"].annotations.read_only_hint is True
        assert by_name["decide_exception"].annotations.read_only_hint is False
        action_schema = json.dumps(by_name["decide_exception"].input_schema)
        assert "short_pay" in action_schema and "release_hold" in action_schema

        uris = {str(r.uri) for r in (await client.list_resources()).resources}
        assert {"ledgic://policy/ap", "ledgic://exceptions/open"} <= uris
        prompts = {p.name for p in (await client.list_prompts()).prompts}
        assert {"triage_exceptions", "explain_invoice"} <= prompts
        assert "decide_exception" in (client.instructions or "")


async def test_policy_resource_readable():
    async with Client(build_server()) as client:
        res = await client.read_resource("ledgic://policy/ap")
        text = res.contents[0].text
        assert "tolerance" in text.lower()


async def test_prompt_renders():
    async with Client(build_server()) as client:
        p = await client.get_prompt("explain_invoice", {"invoice_number": "PS-88214"})
        assert "PS-88214" in p.messages[0].content.text


async def test_missing_token_rejected():
    auth.use_local_token(None)
    async with Client(build_server()) as client:
        res = await client.call_tool("get_kpis", {})
        assert res.is_error
        assert "Unauthenticated" in _text(res)


async def test_argument_validation():
    async with Client(build_server()) as client:
        res = await client.call_tool("list_exceptions", {"status": "bogus"})
        assert res.is_error


# ---- auth against the DB --------------------------------------------------------------------------


@needs_db
async def test_invalid_and_revoked_tokens_rejected(pool, seed: Seed):
    for raw in ("lgc_pat_this-token-does-not-exist-anywhere", seed.revoked, "not-a-ledgic-token"):
        auth.use_local_token(raw)
        async with Client(build_server()) as client:
            res = await client.call_tool("verify_audit_chain", {})
            assert res.is_error
            assert "invalid or revoked" in _text(res)


@needs_db
async def test_token_resolves_and_touches_last_used(pool, seed: Seed):
    ctx = await auth.resolve_token(seed.manager_decide)
    assert ctx is not None
    assert (ctx.user_id, ctx.org_id, ctx.role) == (seed.manager_id, seed.org_id, "ap_manager")
    assert ctx.scopes == ("read", "decide")
    from app.db.pool import connection

    async with connection() as conn:
        row = await (
            await conn.execute(
                "select last_used_at from public.mcp_tokens where token_hash = %s",
                (auth.hash_token(seed.manager_decide),),
            )
        ).fetchone()
    assert row["last_used_at"] is not None


@needs_db
async def test_read_scope_cannot_decide(pool, seed: Seed):
    auth.use_local_token(seed.viewer_read)
    async with Client(build_server()) as client:
        res = await client.call_tool(
            "decide_exception",
            {
                "exception_id": "00000000-0000-0000-0000-000000000001",
                "action": "approve_as_is",
                "comment": "x",
            },
        )
        assert res.is_error
        assert "lacks the 'decide' scope" in _text(res)


@needs_db
async def test_create_token_requires_membership(pool, seed: Seed):
    with pytest.raises(ValueError, match="not a member"):
        await auth.create_token(seed.viewer_id, "00000000-0000-0000-0000-000000000000", ["read"], "x")
    out = await auth.create_token(seed.viewer_id, seed.org_id, "read", "cli-test")
    assert out["token"].startswith("lgc_pat_") and out["scopes"] == ["read"]
    assert (await auth.resolve_token(out["token"])).role == "viewer"


def test_normalize_scopes():
    assert auth.normalize_scopes("decide") == ["read", "decide"]
    assert auth.normalize_scopes(["read", " read "]) == ["read"]
    with pytest.raises(ValueError):
        auth.normalize_scopes("admin")


@needs_db
async def test_audit_chain_tool(pool, seed: Seed):
    if not function_exists("audit_verify_org"):
        pytest.skip("audit_verify_org() not migrated yet (workstream B2)")
    auth.use_local_token(seed.viewer_read)
    async with Client(build_server()) as client:
        data = _data(await client.call_tool("verify_audit_chain", {}))
        assert data["ok"] is True
        assert "intact" in data["message"]


# ---- read tools (need B2's views) -----------------------------------------------------------------


@needs_db
async def test_get_kpis_and_list_exceptions(pool, seed: Seed):
    missing = [v for v in ("v_ops_period", "v_status_bar", "v_exception_queue") if not relation_exists(v)]
    if missing:
        pytest.skip(f"views not migrated yet (workstream B2): {', '.join(missing)}")
    auth.use_local_token(seed.viewer_read)
    async with Client(build_server()) as client:
        kpis = _data(await client.call_tool("get_kpis", {"period": "mtd"}))
        assert kpis["period"] == "mtd"
        assert "kpis" in kpis and "today" in kpis
        exc = _data(await client.call_tool("list_exceptions", {"limit": 5}))
        assert exc["status_filter"] == "open"
        assert exc["total"] == 1
        row = exc["exceptions"][0]
        assert row["exception_id"] == seed.exception_id
        assert row["amount_at_risk"] == "50.00" and row["invoice_number"] == "MCP-1001"
        none = _data(await client.call_tool("list_exceptions", {"type": "duplicate"}))
        assert none["total"] == 0

        inv = _data(await client.call_tool("get_invoice", {"invoice_number": "mcp 1001"}))
        assert inv["invoice_number"] == "MCP-1001" and inv["total"] == "1000.00"
        assert [e["exception_id"] for e in inv["exceptions"]] == [seed.exception_id]
        m = _data(await client.call_tool("explain_match", {"invoice_number": "MCP-1001"}))
        assert m["verdict"] is None and "not been through three-way match" in m["message"]
        res = await client.call_tool("get_invoice", {"invoice_number": "NOPE-1"})
        assert res.is_error and "Not found" in _text(res)


@needs_db
async def test_viewer_decide_refused_by_database(pool, seed: Seed):
    """A viewer holding a token *with* the decide scope still cannot decide: the RPC refuses."""
    if not function_exists("rpc_decide_exception"):
        pytest.skip("rpc_decide_exception not migrated yet (workstream B2)")
    auth.use_local_token(seed.viewer_decide)
    async with Client(build_server()) as client:
        res = await client.call_tool(
            "decide_exception",
            {
                "exception_id": seed.exception_id,
                "action": "dispute",
                "comment": "vendor billed above contract",
            },
        )
        assert res.is_error
        assert "Forbidden: Read-only access" in _text(res), _text(res)
        still = _data(await client.call_tool("list_exceptions", {}))
        assert still["exceptions"][0]["status"] == "open"


@needs_db
async def test_manager_decision_enforced_and_audited(pool, seed: Seed):
    if not function_exists("rpc_decide_exception"):
        pytest.skip("rpc_decide_exception not migrated yet (workstream B2)")
    auth.use_local_token(seed.manager_decide)
    async with Client(build_server()) as client:
        res = await client.call_tool(
            "decide_exception", {"exception_id": seed.exception_id, "action": "merge"}
        )
        assert res.is_error and "Invalid" in _text(res), _text(res)  # merge is not a price-variance action
        res = await client.call_tool(
            "decide_exception", {"exception_id": seed.exception_id, "action": "dispute"}
        )
        assert res.is_error and "Invalid" in _text(res), _text(res)  # dispute needs a comment
        ok = _data(
            await client.call_tool(
                "decide_exception",
                {
                    "exception_id": seed.exception_id,
                    "action": "dispute",
                    "comment": "Asked vendor for credit",
                },
            )
        )
        assert ok["ok"] is True and ok["exception_status"] == "disputed"
        chain = _data(await client.call_tool("verify_audit_chain", {}))
        assert chain["ok"] is True and int(chain["entries"]) >= 1


@needs_db
async def test_search_contracts_degrades_to_text(pool, seed: Seed):
    auth.use_local_token(seed.viewer_read)
    async with Client(build_server()) as client:
        data = _data(await client.call_tool("search_contracts", {"query": "shrimp price", "k": 3}))
        assert data["mode"] in ("hybrid", "text_only")
        assert isinstance(data["results"], list)


# ---- the demo org (when seeded): viewer is refused by the DATABASE -------------------------------


# One action each exception type accepts (rpc_decide_exception's allow-list).
VALID_ACTION = {
    "price_variance": "dispute",
    "qty_mismatch": "dispute",
    "unmatched_line": "dispute",
    "no_po": "reject_invoice",
    "duplicate": "not_duplicate",
    "new_vendor_screen": "reject_invoice",
    "posting_failed": "reject_invoice",
}


@needs_db
async def test_demo_viewer_decide_denied_by_database(pool):
    if not function_exists("rpc_decide_exception") or not relation_exists("v_exception_queue"):
        pytest.skip("rpc_decide_exception / v_exception_queue not migrated yet (workstream B2)")
    from app.db.pool import connection

    async with connection() as conn:
        member = await (
            await conn.execute(
                "select 1 from public.memberships where org_id = %s and user_id = %s",
                (auth.DEMO_ORG_ID, auth.DEMO_VIEWER_ID),
            )
        ).fetchone()
        exc = await (
            await conn.execute(
                "select id::text as id, type::text as type from public.exceptions where org_id = %s "
                "and status <> 'resolved' and type <> 'extraction_review' order by opened_at limit 1",
                (auth.DEMO_ORG_ID,),
            )
        ).fetchone()
    if member is None or exc is None:
        pytest.skip("demo org not seeded / no open exception")
    # Even a token *with* the decide scope must be refused: the viewer's role is read-only in the DB.
    out = await auth.create_token(auth.DEMO_VIEWER_ID, auth.DEMO_ORG_ID, "read,decide", "pytest-viewer")
    try:
        auth.use_local_token(out["token"])
        async with Client(build_server()) as client:
            listed = _data(await client.call_tool("list_exceptions", {"limit": 3}))
            assert listed["total"] >= 1
            # An action valid for the type, so the refusal comes from the role check, not the action check.
            action = VALID_ACTION[exc["type"]]
            res = await client.call_tool(
                "decide_exception", {"exception_id": exc["id"], "action": action, "comment": "pytest"}
            )
            assert res.is_error
            assert "Forbidden: Read-only access" in _text(res), _text(res)
    finally:
        async with connection() as conn:
            await conn.execute("delete from public.mcp_tokens where id = %s", (out["id"],))


# ---- the real stdio entry point (`ledgic-mcp`) as a subprocess ------------------------------------


@needs_db
async def test_stdio_entry_point(pool, seed: Seed):
    import os
    import sys
    from pathlib import Path

    from mcp.client.stdio import StdioServerParameters

    from app.config import get_settings

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.stdio"],
        cwd=str(Path(__file__).resolve().parents[2]),
        env={
            **os.environ,
            "LEDGIC_MCP_TOKEN": seed.viewer_read,
            "DATABASE_URL": get_settings().database_url,
        },
    )
    async with Client(params) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert names == EXPECTED_TOOLS
        res = await client.call_tool("decide_exception", {"exception_id": seed.org_id, "action": "dispute"})
        assert res.is_error and "lacks the 'decide' scope" in _text(res)
