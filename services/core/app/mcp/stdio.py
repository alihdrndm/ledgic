"""`ledgic-mcp` — stdio transport for Claude Desktop / Cursor / Claude Code.

Environment:
- LEDGIC_MCP_TOKEN  personal access token (`lgc_pat_...`), required
- DATABASE_URL      Postgres connection string (direct mode; defaults to the local Supabase DB)

Run: `uv run --project services/core ledgic-mcp`. Logs go to stderr; stdout carries the protocol.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from app.db.pool import close_pool, open_pool

from .auth import resolve_token, use_local_token
from .server import build_server


async def _run() -> int:
    raw = os.environ.get("LEDGIC_MCP_TOKEN", "").strip()
    if not raw:
        print(
            "ledgic-mcp: set LEDGIC_MCP_TOKEN to a Ledgic personal access token (lgc_pat_...).",
            file=sys.stderr,
        )
        return 2
    await open_pool()
    try:
        ctx = await resolve_token(raw)
        if ctx is None:
            print("ledgic-mcp: LEDGIC_MCP_TOKEN is invalid or revoked.", file=sys.stderr)
            return 2
        print(
            f"ledgic-mcp: acting as user {ctx.user_id} ({ctx.role}) in org {ctx.org_id}, "
            f"scopes={list(ctx.scopes)}",
            file=sys.stderr,
        )
        use_local_token(raw)
        await build_server().run_stdio_async()
        return 0
    finally:
        await close_pool()


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    # psycopg's async driver needs a selector event loop on Windows (the default Proactor loop fails).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    sys.exit(asyncio.run(_run(), loop_factory=loop_factory))


if __name__ == "__main__":
    main()
