"""Hardening from the 2026-10 security audit: config refuses the public placeholder secret, admin bodies
are strict, and draft regeneration is rate limited."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest
from pydantic import ValidationError

from app.api import routes
from app.api.auth import Principal
from app.api.envelope import ApiError
from app.config import PLACEHOLDER_HMAC_SECRET, Settings

HOSTED_DB = "postgresql://u:p@aws-0-eu.pooler.supabase.com:6543/postgres"


@pytest.mark.parametrize("secret", [PLACEHOLDER_HMAC_SECRET, "short-secret"])
def test_deployed_core_refuses_a_placeholder_or_short_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="CORE_HMAC_SECRET"):
        Settings(_env_file=None, database_url=HOSTED_DB, core_hmac_secret=secret)


def test_deployed_core_starts_with_a_real_secret_and_local_dev_keeps_the_default() -> None:
    assert Settings(_env_file=None, database_url=HOSTED_DB, core_hmac_secret="x" * 40).is_deployed
    local = Settings(_env_file=None)
    assert not local.is_deployed and local.core_hmac_secret == PLACEHOLDER_HMAC_SECRET
    assert local.api_docs is False  # docs are opt-in


def test_admin_bodies_reject_fields_from_other_endpoints() -> None:
    from app.api.admin import ResetBody

    with pytest.raises(ValidationError):
        ResetBody.model_validate({"org_id": None, "storage_path": "org/x/uploads/y.pdf"})


@pytest.fixture
def draft_route(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """`exception_draft` with the DB, role check and agent faked; records the limit keys it checks."""
    keys: list[str] = []

    @asynccontextmanager
    async def conn() -> Any:
        yield None

    async def val(*a: Any, **k: Any) -> str:
        return "org-1"

    async def allowed(*a: Any, **k: Any) -> None:
        return None

    async def over(key: str, limit: int, window: int) -> bool:
        keys.append(key)
        return True

    monkeypatch.setattr(routes, "connection", conn)
    monkeypatch.setattr(routes, "val", val)
    monkeypatch.setattr(routes, "require_role", allowed)
    monkeypatch.setattr(routes, "_over_limit", over)
    return keys


async def test_regenerating_drafts_is_rate_limited_per_user(draft_route: list[str]) -> None:
    body = routes.DraftBody(regenerate=True)
    with pytest.raises(ApiError) as e:
        await routes.exception_draft("exc-1", body, None, Principal("user", "user-1"))  # type: ignore[arg-type]
    assert e.value.code == "RATE_LIMITED" and draft_route == ["draft:user:user-1"]
