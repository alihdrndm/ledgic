"""Build, push and deploy the Ledgic core to an Amazon Lightsail container service.

    aws login                                       # short-lived credentials, never the root user
    python tools/deploy/core_lightsail.py --check   # validate the env file only, no AWS calls
    python tools/deploy/core_lightsail.py           # build, push, deploy, smoke test

Production values are read from `.env.production.core` in the repo root (git-ignored). They are never
printed: Lightsail echoes a deployment's environment in its responses, so every AWS call asks for named
fields only, and error output is masked. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.production.core"
REGION = "us-east-1"
SERVICE = "ledgic-core"
CONTAINER = "core"
PORT = 8000

REQUIRED = (
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "CORE_HMAC_SECRET",
    "CORS_ORIGINS",
    "LLM_MODE",
)
OPTIONAL = (
    "SUPABASE_ANON_KEY",
    "SUPABASE_JWT_SECRET",
    "OPENAI_API_KEY",
    "LLM_MODEL",
    "EMBED_MODEL",
    "EMBED_DIMS",
    "LLM_DAILY_CAP_USD",
    "WORKER_ENABLED",
    "REPLAY_ENABLED",
    "ORCHESTRATOR_VERSION",
    "API_DOCS",
    "MCP_DEMO_TOKEN",
    "CORE_PUBLIC_URL",
    "DEMO_VIEWER_PASSWORD",
    "DEMO_ELENA_PASSWORD",
)
_LINE = re.compile(r"(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)")
_IMAGE = re.compile(r'"(:[a-z0-9.-]+\.[a-z0-9-]+\.\d+)"')


class DeployError(Exception):
    """A check or command failed. The message never contains a configured value."""


def parse_env(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.fullmatch(line)
        if m is None:
            raise DeployError(f"line {n} is not NAME=value")
        name, value = m.group(1), m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name in env:
            raise DeployError(f"{name} is set twice")
        if value:
            env[name] = value
    return env


def problems(env: Mapping[str, str]) -> list[str]:
    """Everything wrong with a production environment. Names only, never values."""
    out = [f"{n} is missing" for n in REQUIRED if n not in env]
    out += [f"{n} is not a core variable" for n in env if n not in REQUIRED + OPTIONAL]

    if db := env.get("DATABASE_URL"):
        try:
            url = urlsplit(db)
            port, host = url.port, url.hostname or ""
        except ValueError:
            out.append("DATABASE_URL is not a valid URL (percent-encode the password)")
        else:
            if host in ("", "localhost", "127.0.0.1"):
                out.append("DATABASE_URL points at a local database")
            if port == 6543:
                out.append("DATABASE_URL uses the transaction pooler; use the session pooler (port 5432)")
            if parse_qs(url.query).get("sslmode", [""])[-1] not in ("require", "verify-ca", "verify-full"):
                out.append("DATABASE_URL needs ?sslmode=require")
    for name in ("SUPABASE_URL", "CORE_PUBLIC_URL"):
        if name in env and not env[name].startswith("https://"):
            out.append(f"{name} must be an https:// URL")
    origins = [o.strip() for o in env.get("CORS_ORIGINS", "").split(",") if o.strip()]
    if any(not o.startswith("https://") or "*" in o for o in origins):
        out.append("CORS_ORIGINS must list exact https:// origins")
    if len(env.get("CORE_HMAC_SECRET", "x" * 32)) < 32:
        out.append("CORE_HMAC_SECRET is shorter than 32 characters")
    mode = env.get("LLM_MODE")
    if mode not in (None, "fixture", "live"):
        out.append("LLM_MODE must be fixture or live")
    if mode == "fixture" and "OPENAI_API_KEY" in env:
        out.append("OPENAI_API_KEY is not needed in fixture mode; leave it off the server")
    if mode == "live" and "LLM_DAILY_CAP_USD" not in env:
        out.append("LLM_DAILY_CAP_USD must be set explicitly in live mode")
    if env.get("API_DOCS", "false").lower() != "false":
        out.append("API_DOCS must be false in production")
    return out


def deployment(env: Mapping[str, str], image: str, sha: str) -> dict[str, Any]:
    return {
        "serviceName": SERVICE,
        "containers": {
            CONTAINER: {
                "image": image,
                "environment": {**env, "PORT": str(PORT), "GIT_SHA": sha},
                "ports": {str(PORT): "HTTP"},
            }
        },
        "publicEndpoint": {
            "containerName": CONTAINER,
            "containerPort": PORT,
            "healthCheck": {
                "path": "/health",
                "successCodes": "200",
                "intervalSeconds": 30,
                "timeoutSeconds": 10,
                "healthyThreshold": 2,
                "unhealthyThreshold": 5,
            },
        },
    }


def mask(text: str, env: Mapping[str, str]) -> str:
    for value in sorted(env.values(), key=len, reverse=True):
        if len(value) >= 8:
            text = text.replace(value, "***")
    return text


def unhealthy(body: Mapping[str, Any], sha: str) -> list[str]:
    d = body.get("data") or {}
    out = []
    if d.get("version") != sha:
        out.append("the new version is not serving yet")
    if d.get("status") != "ok" or d.get("db") is not True:
        out.append("status or database check is not ok")
    worker = d.get("worker") or {}
    if worker.get("enabled") and not worker.get("alive"):
        out.append("the worker is not alive")
    if not (d.get("scheduler") or {}).get("leader"):
        out.append("the scheduler is not leader yet")
    return out


def run(*cmd: str, env: Mapping[str, str], stream: bool = False) -> str:
    try:
        p = subprocess.run(
            cmd, cwd=ROOT, capture_output=not stream, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError as e:
        raise DeployError(f"{cmd[0]} is not installed or not on PATH") from e
    if p.returncode != 0:
        detail = "" if stream else mask((p.stderr or p.stdout).strip(), env)[-1500:]
        raise DeployError(f"{' '.join(cmd[:3])} failed\n{detail}")
    return "" if stream else p.stdout.strip()


def aws(*args: str, query: str, env: Mapping[str, str]) -> Any:
    """`query` is required on purpose: unfiltered Lightsail output contains the environment."""
    out = run("aws", *args, "--region", REGION, "--query", query, "--output", "json", env=env)
    return json.loads(out) if out else None


def service(query: str, env: Mapping[str, str]) -> Any:
    args = ("lightsail", "get-container-services", "--service-name", SERVICE)
    return aws(*args, query=f"containerServices[0].{query}", env=env)


def preflight(env: Mapping[str, str]) -> str:
    if run("git", "status", "--porcelain", env=env):
        raise DeployError("the working tree has changes; commit or stash them")
    run("git", "fetch", "--quiet", "origin", "main", env=env)
    sha = run("git", "rev-parse", "HEAD", env=env)
    if sha != run("git", "rev-parse", "origin/main", env=env):
        raise DeployError("HEAD is not origin/main; only main is deployed")
    arn = aws("sts", "get-caller-identity", query="Arn", env=env)
    if str(arn).endswith(":root"):
        raise DeployError("signed in as the root user; use the deployer identity (aws login)")
    power, scale = service("[power, scale]", env)
    if scale != 1:
        raise DeployError(f"{SERVICE} has {scale} nodes; the core runs as exactly one")
    print(f"{SERVICE}: {power} x {scale}, deploying {sha[:12]}", flush=True)
    return sha


def build_and_push(sha: str, env: Mapping[str, str]) -> str:
    tag = f"{SERVICE}:{sha[:12]}"
    build = ("docker", "build", "--platform", "linux/amd64", "--provenance=false")
    run(*build, "-f", "services/core/Dockerfile", "-t", tag, ".", env=env, stream=True)
    # A corrupt layer cache can build "successfully" with nothing installed; never push that.
    run("docker", "run", "--rm", "--entrypoint", "python", tag, "-c", "import uvicorn, app.main", env=env)
    push = ("aws", "lightsail", "push-container-image", "--region", REGION)
    out = run(*push, "--service-name", SERVICE, "--label", CONTAINER, "--image", tag, env=env)
    m = _IMAGE.search(out)
    if m is None:
        raise DeployError("could not read the pushed image name from the AWS CLI output")
    return m.group(1)


def create_deployment(body: Mapping[str, Any], env: Mapping[str, str]) -> int:
    fd, name = tempfile.mkstemp(suffix=".json")  # readable by the current user only
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f)
        args = ("lightsail", "create-container-service-deployment", "--cli-input-json")
        version = aws(
            *args, f"file://{path.as_posix()}", query="containerService.nextDeployment.version", env=env
        )
    finally:
        path.unlink()
    return int(version)


def wait_active(version: int, env: Mapping[str, str], *, timeout_s: int = 900) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        current, pending, url = service("[currentDeployment.version, nextDeployment.version, url]", env)
        if current == version:
            return str(url).rstrip("/")
        if pending != version:
            raise DeployError(
                f"deployment {version} failed; version {current} is still serving. Read the container log."
            )
        print(f"  deployment {version} is starting...", flush=True)
        time.sleep(15)
    raise DeployError(f"deployment {version} was not active after {timeout_s} s")


def smoke(url: str, sha: str, *, attempts: int = 24) -> None:
    left = ["no response"]
    for _ in range(attempts):  # the scheduler takes over once the previous container releases its lock
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=15) as r:
                left = unhealthy(json.load(r), sha)
        except Exception as e:
            left = [f"/health failed: {type(e).__name__}"]
        if not left:
            return
        time.sleep(15)
    raise DeployError("smoke test failed: " + "; ".join(left))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deploy the Ledgic core to Lightsail")
    ap.add_argument("--check", action="store_true", help="validate the env file and stop")
    args = ap.parse_args(argv)
    try:
        if not ENV_FILE.exists():
            raise DeployError(f"{ENV_FILE.name} not found in the repo root")
        env = parse_env(ENV_FILE.read_text(encoding="utf-8-sig"))
        if found := problems(env):
            raise DeployError("fix these in " + ENV_FILE.name + ":\n  - " + "\n  - ".join(found))
        if args.check:
            print(f"{ENV_FILE.name}: {len(env)} variables, all checks passed")
            return 0
        sha = preflight(env)
        image = build_and_push(sha, env)
        version = create_deployment(deployment(env, image, sha), env)
        url = wait_active(version, env)
        smoke(url, sha)
    except DeployError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"deployed version {version}: {url}/health is ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
