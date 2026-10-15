"""API unit tests: envelope, auth (HMAC / JWT), validation — no database needed."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api import auth
from app.api.envelope import ApiError, map_db_error
from app.api.routes import sniff_mime
from app.config import Settings
from app.main import create_app

SECRET = "test-hmac-secret"
JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    s = Settings(core_hmac_secret=SECRET, supabase_jwt_secret=JWT_SECRET, database_url="postgresql://x:y@127.0.0.1:1/none",
                 worker_enabled=False, replay_enabled=False)
    monkeypatch.setattr(auth, "get_settings", lambda: s)
    app = create_app(s, start_background=False)
    return TestClient(app, raise_server_exceptions=False)  # no `with`: lifespan (pool) not started


def test_sign_and_verify_roundtrip() -> None:
    body = b'{"org_id":"x"}'
    header = auth.sign(body, SECRET)
    assert auth.verify_signature(header, body, SECRET)
    assert not auth.verify_signature(header, body + b" ", SECRET)
    assert not auth.verify_signature(header, body, "other")
    old = auth.sign(body, SECRET, t=int(time.time()) - 301)
    assert not auth.verify_signature(old, body, SECRET)
    assert not auth.verify_signature("garbage", body, SECRET)
    assert auth.verify_signature(auth.sign(b"", SECRET), b"", SECRET)


def test_admin_requires_signature(client: TestClient) -> None:
    r = client.post("/v1/admin/replay/tick", json={})
    assert r.status_code == 401
    assert r.json() == {"ok": False, "error": {"code": "INVALID_SIGNATURE", "message": "Admin endpoints need X-Ledgic-Signature", "retryable": False}}
    r = client.post("/v1/admin/replay/tick", content=b"{}", headers={"X-Ledgic-Signature": "t=1,v1=00", "Content-Type": "application/json"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_SIGNATURE"


def test_admin_rejects_non_demo_org(client: TestClient) -> None:
    body = b'{"org_id": "00000000-0000-0000-0000-000000000000"}'
    r = client.post("/v1/admin/seed-today", content=body, headers={"X-Ledgic-Signature": auth.sign(body, SECRET), "Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID"


def test_user_endpoints_need_auth(client: TestClient) -> None:
    r = client.get("/v1/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
    r = client.post("/v1/copilot/ask", json={"org_id": "o", "question": "hi"})
    assert r.status_code == 401


def test_bad_jwt_rejected(client: TestClient) -> None:
    bad = jwt.encode({"sub": "u", "aud": "authenticated", "exp": int(time.time()) + 60}, "wrong-secret-wrong-secret-wrong-secret!!", algorithm="HS256")
    r = client.get("/v1/runs/x", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401
    expired = jwt.encode({"sub": "u", "aud": "authenticated", "exp": int(time.time()) - 10}, JWT_SECRET, algorithm="HS256")
    r = client.get("/v1/runs/x", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Session expired"


async def test_valid_jwt_resolves_user(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings(supabase_jwt_secret=JWT_SECRET)
    monkeypatch.setattr(auth, "get_settings", lambda: s)
    tok = jwt.encode({"sub": "user-1", "aud": "authenticated", "exp": int(time.time()) + 60}, JWT_SECRET, algorithm="HS256")
    assert await auth._user_from_token(tok) == "user-1"


def test_validation_errors_use_envelope(client: TestClient) -> None:
    body = b'{"org_id": "o"}'
    r = client.post("/v1/documents/ingest", content=body, headers={"X-Ledgic-Signature": auth.sign(body, SECRET), "Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["ok"] is False and r.json()["error"]["code"] == "INVALID"


def test_health_reports_degraded_without_db(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["db"] is False and d["status"] == "degraded"
    assert "budget_remaining_usd" not in d and "llm_mode" not in d  # public endpoint: no spend/config details
    assert "version" in d and d["worker"]["alive"] is False


def test_sniff_mime() -> None:
    assert sniff_mime(b"%PDF-1.7 ...", "a.pdf") == "application/pdf"
    assert sniff_mime(b"\xff\xd8\xff\xe0....", None) == "image/jpeg"
    assert sniff_mime(b"\x89PNG\r\n\x1a\n...", None) == "image/png"
    with pytest.raises(ApiError):
        sniff_mime(b"GIF89a", "x.gif")


def test_map_db_error_prefixes() -> None:
    class Diag:
        message_primary = "LEDGIC_FORBIDDEN: Needs controller"

    class E(Exception):
        diag = Diag()

    m = map_db_error(E())  # type: ignore[arg-type]
    assert m is not None and m.code == "FORBIDDEN" and m.status == 403 and m.message == "Needs controller"
    Diag.message_primary = "LEDGIC_CONFLICT: Exception already resolved"
    m = map_db_error(E())  # type: ignore[arg-type]
    assert m is not None and m.status == 409
    Diag.message_primary = "relation does not exist"
    assert map_db_error(E()) is None  # type: ignore[arg-type]


def test_api_docs_can_be_disabled() -> None:
    s = Settings(core_hmac_secret=SECRET, supabase_jwt_secret=JWT_SECRET, database_url="postgresql://x:y@127.0.0.1:1/none",
                 api_docs=False)
    c = TestClient(create_app(s, start_background=False))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(path).status_code == 404
