"""Streamable HTTP transport mounted the way core's FastAPI app mounts it (`add_route("/mcp", ...)`)."""

from __future__ import annotations

import httpx2
from fastapi import FastAPI
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.mcp.http import build_http_app, server_lifespan

from .conftest import Seed, needs_db

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "0"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _host_app():
    mcp_app, server = build_http_app()
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    app.add_route("/mcp", mcp_app, methods=["GET", "POST", "DELETE"])
    return app, server


@needs_db
async def test_http_rejects_missing_and_invalid_tokens(pool, seed: Seed):
    app, server = _host_app()
    async with server_lifespan(server):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://core.test") as hc:
            assert (await hc.get("/health")).status_code == 200
            r = await hc.post("/mcp", json=INIT, headers=HEADERS)
            assert r.status_code == 401
            assert "Bearer" in r.headers["www-authenticate"]
            for bad in ("lgc_pat_nope-nope-nope-nope", seed.revoked, "garbage"):
                r = await hc.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": f"Bearer {bad}"})
                assert r.status_code == 401, bad
            r = await hc.post(
                "/mcp", json=INIT, headers={**HEADERS, "Authorization": f"Bearer {seed.viewer_read}"}
            )
            assert r.status_code == 200, r.text


@needs_db
async def test_http_client_session_with_scopes(pool, seed: Seed):
    app, server = _host_app()
    async with server_lifespan(server):
        transport = httpx2.ASGITransport(app=app)

        async def session(token: str):
            hc = httpx2.AsyncClient(
                transport=transport, base_url="http://core.test", headers={"Authorization": f"Bearer {token}"}
            )
            return hc, Client(streamable_http_client("http://core.test/mcp", http_client=hc))

        hc, client = await session(seed.viewer_read)
        async with hc, client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert "decide_exception" in names
            res = await client.call_tool(
                "decide_exception",
                {"exception_id": "00000000-0000-0000-0000-000000000001", "action": "dispute", "comment": "x"},
            )
            assert res.is_error and "lacks the 'decide' scope" in res.content[0].text

        # A decide-scoped token passes the scope gate and reaches the database, which answers for itself.
        hc, client = await session(seed.manager_decide)
        async with hc, client:
            res = await client.call_tool(
                "decide_exception",
                {"exception_id": "00000000-0000-0000-0000-000000000001", "action": "dispute", "comment": "x"},
            )
            assert res.is_error
            text = res.content[0].text
            assert "scope" not in text
            assert ("Not found" in text) or ("Not available yet" in text), text
