"""Safety checks of tools/deploy/core_lightsail.py (no AWS, no Docker)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "deploy" / "core_lightsail.py"


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location("core_lightsail", SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def good() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql://u:p@pooler.example.com:5432/postgres?sslmode=require",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-value",
        "CORE_HMAC_SECRET": "h" * 64,
        "CORS_ORIGINS": "https://app.example.com",
        "LLM_MODE": "fixture",
    }


def test_valid_environment_passes(mod: ModuleType) -> None:
    assert mod.problems(good()) == []


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        ({"DATABASE_URL": "postgresql://u:p@h.example.com:6543/x?sslmode=require"}, "transaction pooler"),
        ({"DATABASE_URL": "postgresql://u:p@h.example.com:5432/x"}, "sslmode"),
        ({"DATABASE_URL": "postgresql://u:p@h.example.com:5432/x?sslmode=prefer"}, "sslmode"),
        ({"DATABASE_URL": "postgresql://u:p@127.0.0.1:54322/x?sslmode=require"}, "local"),
        ({"DATABASE_URL": "postgresql://u:a/b@h.example.com:5432/x?sslmode=require"}, "valid URL"),
        ({"SUPABASE_URL": "http://example.com"}, "https://"),
        ({"CORS_ORIGINS": "*"}, "CORS_ORIGINS"),
        ({"CORS_ORIGINS": "https://*.example.com"}, "CORS_ORIGINS"),
        ({"CORE_HMAC_SECRET": "too-short"}, "32 characters"),
        ({"LLM_MODE": "maybe"}, "LLM_MODE"),
        ({"OPENAI_API_KEY": "sk-placeholder"}, "not needed"),
        ({"LLM_MODE": "live", "OPENAI_API_KEY": "sk-placeholder"}, "LLM_DAILY_CAP_USD"),
        ({"API_DOCS": "true"}, "API_DOCS"),
        ({"SUPABASE_DB_PASSWORD_PROD": "placeholder"}, "not a core variable"),
    ],
)
def test_unsafe_environment_is_refused(mod: ModuleType, change: dict[str, str], needle: str) -> None:
    found = mod.problems(good() | change)
    assert any(needle in p for p in found), found


def test_problems_never_contain_values(mod: ModuleType) -> None:
    env = {k: f"leaky-value-{i}" for i, k in enumerate(mod.REQUIRED + mod.OPTIONAL)}
    report = "\n".join(mod.problems(env))
    assert report and "leaky-value" not in report


def test_missing_variables_are_named(mod: ModuleType) -> None:
    assert len(mod.problems({})) == len(mod.REQUIRED)


def test_parse_env(mod: ModuleType) -> None:
    text = "# note\nexport A='x=y'\nB=\"two words\"\nEMPTY=\n\nC=plain#not-a-comment\n"
    assert mod.parse_env(text) == {"A": "x=y", "B": "two words", "C": "plain#not-a-comment"}
    with pytest.raises(mod.DeployError, match="twice"):
        mod.parse_env("A=1\nA=2")
    with pytest.raises(mod.DeployError) as e:
        mod.parse_env("A=1\nsecret-without-a-name")
    assert "secret" not in str(e.value)


def test_deployment_runs_one_public_http_container(mod: ModuleType) -> None:
    body = mod.deployment(good(), ":ledgic-core.core.1", "abc")
    assert list(body["containers"]) == ["core"]
    c = body["containers"]["core"]
    assert c["environment"]["GIT_SHA"] == "abc" and c["environment"]["PORT"] == "8000"
    assert c["ports"] == {"8000": "HTTP"}
    assert body["publicEndpoint"]["healthCheck"]["path"] == "/health"


def test_create_deployment_filters_output_and_removes_the_temp_file(
    mod: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def fake_run(*cmd: str, env: dict[str, str], stream: bool = False) -> str:
        seen.extend(cmd)
        body = json.loads(Path(cmd[cmd.index("--cli-input-json") + 1].removeprefix("file://")).read_text())
        assert body["serviceName"] == "ledgic-core"
        return "7"

    monkeypatch.setattr(mod, "run", fake_run)
    assert mod.create_deployment(mod.deployment(good(), ":i.c.1", "abc"), good()) == 7
    assert "--query" in seen
    assert not any("service-role-value" in part for part in seen)  # nothing on the command line
    assert not Path(seen[seen.index("--cli-input-json") + 1].removeprefix("file://")).exists()


def test_root_user_is_refused(mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*cmd: str, env: dict[str, str], stream: bool = False) -> str:
        if cmd[:2] == ("git", "rev-parse"):
            return "abc"
        return json.dumps("arn:aws:iam::111122223333:root") if cmd[0] == "aws" else ""

    monkeypatch.setattr(mod, "run", fake_run)
    with pytest.raises(mod.DeployError, match="root user"):
        mod.preflight(good())


def test_failed_deployment_is_reported(mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "service", lambda q, env: [3, None, "https://x.example.com/"])
    assert mod.wait_active(3, good()) == "https://x.example.com"
    with pytest.raises(mod.DeployError, match="deployment 4 failed"):
        mod.wait_active(4, good())


def test_mask_hides_values(mod: ModuleType) -> None:
    env = good()
    masked = mod.mask(json.dumps(env), env)
    assert env["CORE_HMAC_SECRET"] not in masked and env["SUPABASE_SERVICE_ROLE_KEY"] not in masked


def test_pushed_image_name_is_read(mod: ModuleType) -> None:
    out = 'Digest: sha256:0a\nRefer to this image as ":ledgic-core.core.12" in deployments.'
    assert mod._IMAGE.search(out).group(1) == ":ledgic-core.core.12"


def test_health_verdict(mod: ModuleType) -> None:
    data = {
        "status": "ok",
        "db": True,
        "version": "abc",
        "worker": {"enabled": True, "alive": True},
        "scheduler": {"leader": True},
    }
    assert mod.unhealthy({"ok": True, "data": data}, "abc") == []
    assert mod.unhealthy({"ok": True, "data": data | {"db": False, "status": "degraded"}}, "abc")
    assert mod.unhealthy({"ok": True, "data": data | {"scheduler": None}}, "abc")
    assert mod.unhealthy({"ok": True, "data": data}, "other")
