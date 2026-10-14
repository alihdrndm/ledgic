"""Shared psycopg connection pool.

Every module that touches Postgres goes through `connection()` (service role) or
`as_user(conn, user_id)` so RLS, role limits and segregation of duties are enforced
by the database for user-initiated actions (web, MCP, demo replay actor).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

_pool: AsyncConnectionPool | None = None


async def _configure(conn: AsyncConnection) -> None:
    await conn.execute("set search_path = public, extensions")
    await conn.commit()


def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=8,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": False, "prepare_threshold": None},
            configure=_configure,
        )
    return _pool


async def open_pool() -> None:
    await get_pool().open(wait=True)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    """Service-role connection; commits on success, rolls back on error."""
    async with get_pool().connection() as conn:
        yield conn


async def as_user(conn: AsyncConnection, user_id: str, role: str = "authenticated") -> None:
    """Make the rest of the current transaction run as a Supabase user.

    Uses `set local`, so it lasts until commit/rollback. auth.uid() then returns user_id
    and RLS + security-definer RPC checks apply exactly as for a browser request.
    """
    claims = json.dumps({"sub": user_id, "role": role})
    await conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    await conn.execute(f"set local role {role}")
