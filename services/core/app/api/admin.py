"""Admin endpoints (HMAC only) + /health."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.db.pool import connection
from app.demo.corpus.catalog import ORG_ID
from app.repo.sql import val

from .auth import Principal, service_only
from .envelope import ApiError, ok

log = logging.getLogger("ledgic.api.admin")
router = APIRouter()
VERSION = os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("GIT_SHA") or "dev"


@router.get("/health")
async def health(request: Request) -> Any:
    db = False
    try:
        async with connection() as conn:
            db = await asyncio.wait_for(val(conn, "select 1 as one"), timeout=3) == 1
    except Exception:
        db = False
    w = getattr(request.app.state, "worker", None)
    settings = request.app.state.settings
    worker = {
        "enabled": settings.worker_enabled,
        "alive": bool(w and w.alive),
        "last_tick_at": w.last_tick_at.isoformat() if w and w.last_tick_at else None,
        "steps": w.steps if w else 0,
    }
    sched = getattr(request.app.state, "scheduler", None)
    status = "ok" if db and (w is None or w.alive or not settings.worker_enabled) else "degraded"
    return ok(
        {
            "status": status,
            "db": db,
            "worker": worker,
            "scheduler": {"leader": bool(sched and sched.is_leader), "replay": settings.replay_enabled}
            if sched
            else None,
            "version": VERSION,
        }
    )


class TickBody(BaseModel):
    org_id: str | None = None
    now: datetime | None = None


class OrgBody(BaseModel):
    org_id: str | None = None


class ResetBody(BaseModel):
    org_id: str | None = None
    backfill_days: int = 30


def _demo_only(org_id: str | None) -> str:
    org = org_id or ORG_ID
    if org != ORG_ID:
        raise ApiError("INVALID", "Replay is only available for the demo organization")
    return org


@router.post("/v1/admin/replay/tick")
async def replay_tick(body: TickBody, request: Request, _: Principal = Depends(service_only)) -> Any:
    from app.demo import replay

    org = _demo_only(body.org_id)
    if not await replay.demo_org_exists(org):
        raise ApiError("NOT_FOUND", "Demo organization is not seeded")
    w = getattr(request.app.state, "worker", None)
    stats = await replay.tick(
        body.now or datetime.now(UTC),
        org_id=org,
        on_live=w.wake if w else None,
        version=request.app.state.settings.orchestrator_version,
    )
    return ok(
        {
            "dropped": [
                {
                    "document_id": r.document_id,
                    "run_id": r.run_id,
                    "channel": r.channel,
                    "hero": r.hero,
                    "mode": r.mode,
                }
                for r in stats.dropped
            ],
            "decided": stats.decided,
        }
    )


@router.post("/v1/admin/seed-today")
async def seed_today(body: OrgBody, _: Principal = Depends(service_only)) -> Any:
    from app.demo import backfill, replay

    org = _demo_only(body.org_id)
    if not await replay.demo_org_exists(org):
        raise ApiError("NOT_FOUND", "Demo organization is not seeded")
    n = await backfill.seed_today(org_id=org)
    return ok({"runs_created": n})


async def seed_master(org_id: str) -> dict[str, Any]:
    """Workstream B's master-data seed (app.demo.seed), imported lazily."""
    try:
        from app.demo import seed as seed_mod  # type: ignore[attr-defined]
    except ImportError as e:
        raise ApiError("INTERNAL", "Master-data seed module is not available") from e
    for name in ("seed_demo", "seed", "run_seed", "main"):
        fn = getattr(seed_mod, name, None)
        if fn is None:
            continue
        res = fn()
        if asyncio.iscoroutine(res):
            res = await res
        return res if isinstance(res, dict) else {"seeded": True}
    raise ApiError("INTERNAL", "Master-data seed entry point not found")


_reset_task: asyncio.Task[Any] | None = None


async def _restore_kb_and_token(org: str) -> dict[str, Any]:
    """Re-index the knowledge base and re-mint the public MCP demo token after a purge."""
    out: dict[str, Any] = {}
    try:
        from app.ai.rag.index import index_kb

        stats = await index_kb(org)
        out["kb_documents"], out["kb_chunks"] = stats.documents, stats.chunks
    except Exception as e:
        log.exception("reset-demo: KB re-index failed")
        out["kb_error"] = str(e)
    try:
        from app.mcp.auth import ensure_demo_token

        out["mcp_demo_token"] = bool(await ensure_demo_token())
    except Exception as e:
        log.exception("reset-demo: MCP demo token re-mint failed")
        out["mcp_token_error"] = str(e)
    return out


async def _precompute_copilot(org: str) -> None:
    """Cached answers for the suggested questions, once today's data (heroes) exists."""
    try:
        from app.ai.copilot import SUGGESTED_QUESTIONS, ask, cache_put

        for q in SUGGESTED_QUESTIONS:
            await cache_put(org, q, await ask(org, q, use_cache=False))
    except Exception:
        log.exception("reset-demo: copilot cache precompute failed")


@router.post("/v1/admin/reset-demo")
async def reset_demo(body: ResetBody, _: Principal = Depends(service_only)) -> Any:
    """Purge the demo org, reseed master data, then backfill history + today in the background."""
    global _reset_task
    org = _demo_only(body.org_id)
    if _reset_task is not None and not _reset_task.done():
        raise ApiError("CONFLICT", "A reset is already running")
    from app.demo import replay as _replay

    _replay.set_reset_in_progress(True)
    purged: dict[str, Any] = {}
    try:
        async with connection() as conn, conn.transaction():
            if await val(conn, "select 1 from orgs where id = %s", (org,)):
                # A full demo org (audit chain + 14-30 days of runs) outlasts Supabase's default timeout.
                await conn.execute("set local statement_timeout = 0")
                purged = await val(conn, "select public.demo_purge_org(%s) as r", (org,)) or {}
        seeded = await seed_master(org)
    except BaseException:
        _replay.set_reset_in_progress(False)
        raise
    # The purge cascades the org's KB (kb_documents/kb_chunks), copilot cache and MCP tokens: restore them.
    seeded["kb"] = await _restore_kb_and_token(org)

    async def _history() -> None:
        from app.demo import backfill

        try:
            if body.backfill_days > 0:
                await backfill.backfill(body.backfill_days, org_id=org, progress=False)
            await backfill.seed_today(org_id=org)
            await _precompute_copilot(org)
        except Exception:
            log.exception("reset-demo history failed")
        finally:
            _replay.set_reset_in_progress(False)

    _reset_task = asyncio.create_task(_history(), name="ledgic-reset-demo")
    return ok(
        {
            "purged": purged,
            "seeded": {**seeded, "history": f"backfilling {body.backfill_days} days in the background"},
        }
    )
