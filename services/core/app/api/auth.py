"""Auth dependencies: Supabase user JWT (HS256 locally, else /auth/v1/user) and admin HMAC."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Request

from app.config import get_settings
from app.db.pool import connection
from app.repo.sql import val

from .envelope import ApiError

ROLE_RANK = {"viewer": 0, "ap_clerk": 1, "ap_manager": 2, "controller": 3, "admin": 3}
HMAC_SKEW_S = 300
_user_cache: dict[str, tuple[float, str]] = {}


@dataclass(frozen=True)
class Principal:
    kind: str  # user | service
    user_id: str | None = None

    @property
    def is_service(self) -> bool:
        return self.kind == "service"


# ------------------------------------------------------------------------------------------- HMAC


def sign(body: bytes, secret: str, t: int | None = None) -> str:
    t = int(time.time()) if t is None else t
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def verify_signature(header: str, body: bytes, secret: str, now: float | None = None) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        t = int(parts["t"])
        v1 = parts["v1"]
    except (ValueError, KeyError):
        return False
    if abs((now or time.time()) - t) > HMAC_SKEW_S:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


async def _hmac(request: Request) -> Principal | None:
    header = request.headers.get("x-ledgic-signature")
    if not header:
        return None
    body = await request.body()
    if not verify_signature(header, body, get_settings().core_hmac_secret):
        raise ApiError("INVALID_SIGNATURE", "Invalid signature")
    return Principal("service")


# ------------------------------------------------------------------------------------------- JWT


async def _user_from_token(token: str) -> str:
    s = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError as e:
        raise ApiError("UNAUTHENTICATED", "Invalid token") from e
    if alg == "HS256" and s.supabase_jwt_secret:
        try:
            claims = jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        except jwt.ExpiredSignatureError as e:
            raise ApiError("UNAUTHENTICATED", "Session expired") from e
        except jwt.PyJWTError as e:
            raise ApiError("UNAUTHENTICATED", "Invalid token") from e
        if not claims.get("sub"):
            raise ApiError("UNAUTHENTICATED", "Invalid token")
        return str(claims["sub"])
    # asymmetric signing keys (ES256/RS256): ask Supabase Auth
    key = hashlib.sha256(token.encode()).hexdigest()
    hit = _user_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    apikey = s.supabase_service_role_key
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{s.supabase_url.rstrip('/')}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": apikey},
            )
    except httpx.HTTPError as e:
        raise ApiError("UNAUTHENTICATED", "Could not verify session") from e
    if r.status_code != 200:
        raise ApiError("UNAUTHENTICATED", "Invalid token")
    uid = str(r.json()["id"])
    _user_cache[key] = (time.monotonic() + 60, uid)
    return uid


async def _bearer(request: Request) -> Principal | None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if token.startswith("lgc_pat_"):
        return None
    return Principal("user", await _user_from_token(token))


async def user_or_service(request: Request) -> Principal:
    p = await _hmac(request)
    if p:
        return p
    p = await _bearer(request)
    if p:
        return p
    raise ApiError("UNAUTHENTICATED", "Sign in required")


async def user_only(request: Request) -> Principal:
    p = await _bearer(request)
    if p:
        return p
    p = await _hmac(request)  # service callers may act on behalf of the web for copilot
    if p:
        return p
    raise ApiError("UNAUTHENTICATED", "Sign in required")


async def service_only(request: Request) -> Principal:
    p = await _hmac(request)
    if p is None:
        raise ApiError("INVALID_SIGNATURE", "Admin endpoints need X-Ledgic-Signature")
    return p


async def require_role(p: Principal, org_id: str, minimum: str) -> str:
    """Caller's role in org (service → 'admin'). Raises FORBIDDEN/NOT_FOUND."""
    if p.is_service:
        return "admin"
    async with connection() as conn:
        role = await val(
            conn, "select role::text from memberships where org_id = %s and user_id = %s", (org_id, p.user_id)
        )
    if role is None:
        raise ApiError("NOT_FOUND", "Organization not found")
    if ROLE_RANK.get(role, 0) < ROLE_RANK[minimum]:
        raise ApiError("FORBIDDEN", "Read-only access" if role == "viewer" else "Needs AP manager")
    return role


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def byok(request: Request) -> str | None:
    k = request.headers.get("x-openai-key")
    return k.strip() if k and k.strip() else None
