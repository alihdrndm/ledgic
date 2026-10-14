"""Manage MCP personal access tokens.

    uv run python -m app.mcp.tokens create --user <uuid> --org <uuid> --scopes read[,decide] --name demo
    uv run python -m app.mcp.tokens list   [--org <uuid>]
    uv run python -m app.mcp.tokens revoke --id <token-id>
    uv run python -m app.mcp.tokens demo   # upsert MCP_DEMO_TOKEN as the read-only demo viewer token

The raw token is printed once by `create` and never stored (only its sha256).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.db.pool import close_pool, connection, open_pool

from .auth import create_token, ensure_demo_token


async def _create(a: argparse.Namespace) -> int:
    out = await create_token(a.user, a.org, a.scopes, a.name)
    print(out["token"])
    print(
        f"# token id {out['id']} · user role {out['role']} · scopes {','.join(out['scopes'])}"
        " — shown once, store it now",
        file=sys.stderr,
    )
    return 0


async def _list(a: argparse.Namespace) -> int:
    async with connection() as conn:
        cur = await conn.execute(
            """
            select t.id::text as id, t.name, t.user_id::text as user_id, t.org_id::text as org_id, t.scopes,
                   t.created_at, t.last_used_at, t.revoked_at
              from public.mcp_tokens t
             where %(org)s::uuid is null or t.org_id = %(org)s::uuid
             order by t.created_at
            """,
            {"org": a.org},
        )
        for r in await cur.fetchall():
            state = "revoked" if r["revoked_at"] else "active"
            print(f"{r['id']}  {state:7}  {','.join(r['scopes']):12}  user={r['user_id']}  {r['name']}")
    return 0


async def _revoke(a: argparse.Namespace) -> int:
    async with connection() as conn:
        cur = await conn.execute(
            "update public.mcp_tokens set revoked_at = now() "
            "where id = %s and revoked_at is null returning id",
            (a.id,),
        )
        row = await cur.fetchone()
    print("revoked" if row else "no active token with that id", file=sys.stderr)
    return 0 if row else 1


async def _demo(_: argparse.Namespace) -> int:
    token_id = await ensure_demo_token()
    if token_id is None:
        print("MCP_DEMO_TOKEN unset/invalid, or demo org not seeded", file=sys.stderr)
        return 1
    print(f"demo token ready (id {token_id}, read-only, demo viewer)", file=sys.stderr)
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.mcp.tokens", description="Ledgic MCP personal access tokens"
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="mint a token and print it once")
    c.add_argument("--user", required=True, help="auth.users id the token acts as")
    c.add_argument("--org", required=True, help="org id (user must be a member)")
    c.add_argument("--scopes", default="read", help="'read' or 'read,decide' (default read)")
    c.add_argument("--name", default="mcp", help="label shown in `list`")
    c.set_defaults(fn=_create)
    ls = sub.add_parser("list", help="list tokens (never shows raw tokens)")
    ls.add_argument("--org", default=None)
    ls.set_defaults(fn=_list)
    r = sub.add_parser("revoke", help="revoke a token by id")
    r.add_argument("--id", required=True)
    r.set_defaults(fn=_revoke)
    d = sub.add_parser("demo", help="upsert MCP_DEMO_TOKEN as the read-only demo viewer token")
    d.set_defaults(fn=_demo)
    return p


async def _main(argv: list[str] | None) -> int:
    args = _parser().parse_args(argv)
    await open_pool()
    try:
        return await args.fn(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        await close_pool()


def main(argv: list[str] | None = None) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    sys.exit(asyncio.run(_main(argv), loop_factory=loop_factory))


if __name__ == "__main__":
    main()
