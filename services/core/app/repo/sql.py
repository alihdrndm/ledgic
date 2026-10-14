"""Small helpers shared by the SQL repositories (psycopg 3, dict rows)."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb


def _default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return format(o, "f")
    if isinstance(o, datetime | date):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    if isinstance(o, set | frozenset | tuple):
        return list(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=_default, ensure_ascii=False)


def J(obj: Any) -> Jsonb:
    """jsonb parameter; Decimal → decimal string, dates → ISO."""
    return Jsonb(obj, dumps=dumps)


def jsonable(obj: Any) -> Any:
    return json.loads(dumps(obj))


async def one(conn: AsyncConnection, sql: str, params: Any = None) -> dict[str, Any] | None:
    cur = await conn.execute(sql, params)
    return await cur.fetchone()  # type: ignore[return-value]


async def all_(conn: AsyncConnection, sql: str, params: Any = None) -> list[dict[str, Any]]:
    cur = await conn.execute(sql, params)
    return await cur.fetchall()  # type: ignore[return-value]


async def val(conn: AsyncConnection, sql: str, params: Any = None) -> Any:
    row = await one(conn, sql, params)
    if row is None:
        return None
    return next(iter(row.values()))


async def exists_fn(conn: AsyncConnection, name: str) -> bool:
    """True when a function public.<name> exists (B's migrations may not be applied yet)."""
    return bool(
        await val(
            conn,
            "select exists(select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
            "where n.nspname = 'public' and p.proname = %s) as e",
            (name,),
        )
    )


async def exists_rel(conn: AsyncConnection, name: str) -> bool:
    return bool(await val(conn, "select to_regclass(%s) is not null as e", (f"public.{name}",)))
