"""Streamable-HTTP transport for the Ledgic MCP server, protected by bearer personal access tokens.

Mounting inside the core FastAPI app (workstream O)::

    from contextlib import asynccontextmanager
    from app.mcp.http import http_app, mcp_lifespan

    @asynccontextmanager
    async def lifespan(app):
        await open_pool()
        async with mcp_lifespan():          # runs the MCP session manager (+ mints MCP_DEMO_TOKEN)
            yield
        await close_pool()

    app = FastAPI(lifespan=lifespan)
    app.add_route("/mcp", http_app(), methods=["GET", "POST", "DELETE"])

Do not use `app.mount("/mcp", ...)`: Starlette would 307-redirect `/mcp` → `/mcp/` and MCP clients do
not follow redirects. Starlette does not run a mounted/routed sub-app's lifespan, hence `mcp_lifespan()`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from .auth import LedgicTokenVerifier, ensure_demo_token
from .server import build_server

log = logging.getLogger(__name__)

MCP_PATH = "/mcp"

_server: MCPServer | None = None
_app: Starlette | None = None


def build_http_app(path: str = MCP_PATH) -> tuple[Starlette, MCPServer]:
    """A fresh (server, ASGI app) pair. The app serves exactly `path`; bearer auth comes from the SDK's
    `BearerAuthBackend` + `RequireAuthMiddleware` driven by `LedgicTokenVerifier` (401 without a valid
    token, 403 without the `read` scope)."""
    server = build_server(
        LedgicTokenVerifier(),
        issuer_url=os.environ.get("CORE_PUBLIC_URL", "http://localhost:8000"),
    )
    app = server.streamable_http_app(
        streamable_http_path=path,
        # Stateless + JSON: every POST is self-contained, so deploys/restarts never strand client sessions
        # and no sticky routing is needed. Ledgic tools never stream server→client notifications.
        stateless_http=True,
        json_response=True,
        # Bearer auth already defeats DNS rebinding (a browser cannot attach the token); the SDK's default
        # localhost-only Host allowlist would reject the deployed hostname.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return app, server


def http_app() -> Starlette:
    """The process-wide MCP ASGI app (created once)."""
    global _app, _server
    if _app is None:
        _app, _server = build_http_app()
    return _app


@asynccontextmanager
async def server_lifespan(server: MCPServer) -> AsyncIterator[None]:
    try:
        await ensure_demo_token()
    except Exception:  # never block startup on the demo token
        log.warning("could not mint MCP_DEMO_TOKEN", exc_info=True)
    async with server.session_manager.run():
        yield


@asynccontextmanager
async def mcp_lifespan() -> AsyncIterator[None]:
    """Run inside the host app's lifespan (after the DB pool is open)."""
    http_app()
    assert _server is not None
    async with server_lifespan(_server):
        yield
