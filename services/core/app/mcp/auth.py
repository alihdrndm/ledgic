"""Personal access tokens for the MCP server.

A token is `lgc_pat_<random>`; only its sha256 hex is stored (`mcp_tokens.token_hash`). A token acts as
`mcp_tokens.user_id` inside `mcp_tokens.org_id` with `scopes` ⊆ {read, decide}. Every DB call a tool
makes runs *as that user* (`as_user`), so RLS, role limits and segregation of duties are enforced by
Postgres — the scopes here are only a coarse second gate (a `read` token can never reach a write RPC).

Two ways a request gets its token:
- HTTP: the SDK's bearer middleware calls `LedgicTokenVerifier.verify_token` and stores the resulting
  `AccessToken` in a contextvar (`get_access_token()`), which propagates into tool handlers.
- stdio (and tests): `use_local_token(raw)` pins one raw token for the process; it is re-resolved on
  every call so revocation takes effect immediately.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError

from app.db.pool import connection

log = logging.getLogger(__name__)

TOKEN_PREFIX = "lgc_pat_"
VALID_SCOPES = ("read", "decide")

# contracts/fixtures.json — never change once data exists.
DEMO_ORG_ID = "992e72b7-9d9b-5104-9051-f5ef581c99e0"
DEMO_VIEWER_ID = "2ff0bef9-b811-57ae-98a9-3cc42e42de8d"
DEMO_TOKEN_NAME = "public-demo (read-only)"


class AuthError(ToolError):
    """Missing / invalid / revoked token or missing scope. Surfaces to the model as an is_error result."""


@dataclass(frozen=True)
class TokenContext:
    token_id: str
    user_id: str
    org_id: str
    scopes: tuple[str, ...]
    role: str | None = None
    name: str = ""
    extra: dict[str, str] = field(default_factory=dict, compare=False)

    def has(self, scope: str) -> bool:
        return scope in self.scopes


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode()).hexdigest()


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def looks_like_token(raw: str | None) -> bool:
    return bool(raw) and raw.strip().startswith("lgc_") and 16 <= len(raw.strip()) <= 256


def normalize_scopes(scopes: str | list[str] | tuple[str, ...]) -> list[str]:
    items = scopes.split(",") if isinstance(scopes, str) else list(scopes)
    out = sorted({s.strip() for s in items if s.strip()})
    bad = [s for s in out if s not in VALID_SCOPES]
    if bad:
        raise ValueError(f"unknown scope(s) {bad}; valid: {list(VALID_SCOPES)}")
    if "decide" in out and "read" not in out:
        out.append("read")  # decide implies read
    return [s for s in VALID_SCOPES if s in out]


_RESOLVE_SQL = """
update public.mcp_tokens t
   set last_used_at = now()
 where t.token_hash = %s and t.revoked_at is null
returning t.id::text as token_id, t.user_id::text as user_id, t.org_id::text as org_id, t.scopes, t.name,
          (select m.role::text from public.memberships m
            where m.org_id = t.org_id and m.user_id = t.user_id) as role
"""


async def resolve_token(raw: str | None) -> TokenContext | None:
    """Look up a raw token (service role). None when unknown, revoked, or the user left the org."""
    if not looks_like_token(raw):
        return None
    assert raw is not None
    async with connection() as conn:
        row = await (await conn.execute(_RESOLVE_SQL, (hash_token(raw),))).fetchone()
    if row is None or row["role"] is None:
        return None
    return TokenContext(
        token_id=row["token_id"],
        user_id=row["user_id"],
        org_id=row["org_id"],
        scopes=tuple(row["scopes"] or ()),
        role=row["role"],
        name=row["name"],
    )


class LedgicTokenVerifier:
    """`mcp.server.auth.provider.TokenVerifier` backed by `mcp_tokens`."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            ctx = await resolve_token(token)
        except Exception:  # DB down → treat as unauthenticated rather than 500
            log.exception("mcp token lookup failed")
            return None
        if ctx is None:
            return None
        return AccessToken(
            token=token,
            client_id=f"mcp_token:{ctx.token_id}",
            scopes=list(ctx.scopes),
            subject=ctx.user_id,
            claims={
                "token_id": ctx.token_id,
                "user_id": ctx.user_id,
                "org_id": ctx.org_id,
                "role": ctx.role,
                "name": ctx.name,
            },
        )


# ---- per-process token for stdio / tests -------------------------------------------------------

_local_raw_token: str | None = None


def use_local_token(raw: str | None) -> None:
    """Pin the raw token used when no HTTP bearer token is present (stdio transport, tests)."""
    global _local_raw_token
    _local_raw_token = raw.strip() if raw else None


async def current_token() -> TokenContext:
    at = get_access_token()
    if at is not None and at.claims and at.claims.get("org_id"):
        c = at.claims
        return TokenContext(
            token_id=str(c["token_id"]),
            user_id=str(c["user_id"]),
            org_id=str(c["org_id"]),
            scopes=tuple(at.scopes),
            role=c.get("role"),
            name=str(c.get("name") or ""),
        )
    if _local_raw_token:
        ctx = await resolve_token(_local_raw_token)
        if ctx is None:
            raise AuthError(
                "Unauthenticated: the Ledgic token is invalid or revoked. Mint a new one with "
                "`uv run python -m app.mcp.tokens create ...`."
            )
        return ctx
    raise AuthError("Unauthenticated: no Ledgic token. Set LEDGIC_MCP_TOKEN (stdio) or send a Bearer token.")


async def require(scope: str) -> TokenContext:
    ctx = await current_token()
    if not ctx.has(scope):
        raise AuthError(
            f"Forbidden: this token lacks the '{scope}' scope (has: {', '.join(ctx.scopes) or 'none'})."
            + (" Decisions need a token minted with --scopes read,decide." if scope == "decide" else "")
        )
    return ctx


# ---- minting ----------------------------------------------------------------------------------


async def create_token(
    user_id: str, org_id: str, scopes: str | list[str], name: str, raw: str | None = None
) -> dict:
    """Insert a token row; returns {id, token} — the raw token is only ever returned here.
    `scopes` is a list or a comma-separated string ('read' or 'read,decide')."""
    raw = raw or generate_token()
    if not looks_like_token(raw):
        raise ValueError("token must start with 'lgc_' and be 16-256 characters")
    scope_list = normalize_scopes(scopes)
    async with connection() as conn:
        member = await (
            await conn.execute(
                "select role::text as role from public.memberships where org_id = %s and user_id = %s",
                (org_id, user_id),
            )
        ).fetchone()
        if member is None:
            raise ValueError(f"user {user_id} is not a member of org {org_id}")
        row = await (
            await conn.execute(
                "insert into public.mcp_tokens (user_id, org_id, name, token_hash, scopes) "
                "values (%s, %s, %s, %s, %s) returning id::text as id",
                (user_id, org_id, name, hash_token(raw), scope_list),
            )
        ).fetchone()
    assert row is not None
    return {"id": row["id"], "token": raw, "scopes": scope_list, "role": member["role"]}


async def ensure_demo_token(raw: str | None = None) -> str | None:
    """Upsert the well-known public demo token (env MCP_DEMO_TOKEN) for the demo *viewer*, read-only.

    Idempotent; scopes are forced to ['read'] and revocation is cleared. Returns the token id, or None
    when the env var is unset or the demo org / viewer is not seeded yet.
    """
    raw = (raw or os.environ.get("MCP_DEMO_TOKEN") or "").strip()
    if not raw:
        return None
    if not looks_like_token(raw):
        log.warning("MCP_DEMO_TOKEN ignored: must start with 'lgc_' and be 16-256 characters")
        return None
    async with connection() as conn:
        ok = await (
            await conn.execute(
                "select 1 from public.memberships where org_id = %s and user_id = %s",
                (DEMO_ORG_ID, DEMO_VIEWER_ID),
            )
        ).fetchone()
        if ok is None:
            log.info("demo MCP token not minted: demo org/viewer not seeded yet")
            return None
        row = await (
            await conn.execute(
                """
                insert into public.mcp_tokens (user_id, org_id, name, token_hash, scopes)
                values (%s, %s, %s, %s, '{read}')
                on conflict (token_hash) do update
                   set user_id = excluded.user_id, org_id = excluded.org_id, name = excluded.name,
                       scopes = '{read}', revoked_at = null
                returning id::text as id
                """,
                (DEMO_VIEWER_ID, DEMO_ORG_ID, DEMO_TOKEN_NAME, hash_token(raw)),
            )
        ).fetchone()
    return row["id"] if row else None
