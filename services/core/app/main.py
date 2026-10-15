"""Ledgic core: FastAPI app factory. Runs the API, the durable orchestrator worker, the scheduler and
the MCP server (streamable HTTP at /mcp) in one process.

    uv run uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.db.pool import close_pool, open_pool

from .api import admin, envelope, routes

log = logging.getLogger("ledgic")

if sys.platform == "win32":  # psycopg async needs a selector loop on Windows (local dev only)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _mcp():  # type: ignore[no-untyped-def]
    try:
        from app.mcp.http import http_app, mcp_lifespan

        return http_app, mcp_lifespan
    except Exception as e:  # MCP is optional for the pipeline
        log.warning("MCP server unavailable: %s", e)
        return None, None


def create_app(settings: Settings | None = None, *, start_background: bool = True) -> FastAPI:
    settings = settings or get_settings()
    http_app, mcp_lifespan = _mcp()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        await open_pool()
        async with AsyncExitStack() as stack:
            if mcp_lifespan is not None:
                await stack.enter_async_context(mcp_lifespan())
            worker = scheduler = None
            if start_background and settings.worker_enabled:
                from app.orchestrator import Engine, Options
                from app.orchestrator.worker import Worker

                engine = Engine(
                    options=Options(version=settings.orchestrator_version), byok_keys=app.state.byok_keys
                )
                worker = Worker(engine)
                await worker.start()
                app.state.worker = worker
            if start_background:
                from app.scheduler import Scheduler

                scheduler = Scheduler(on_live_docs=worker.wake if worker else None)
                try:
                    await scheduler.start()
                    app.state.scheduler = scheduler
                except Exception as e:
                    log.warning("scheduler not started: %s", e)
                    scheduler = None
            try:
                yield
            finally:
                if scheduler is not None:
                    await scheduler.stop()
                if worker is not None:
                    await worker.stop()
                from app.orchestrator import drafts

                await drafts.stop()
        await close_pool()

    docs = settings.api_docs
    app = FastAPI(
        title="Ledgic core",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.byok_keys = {}
    app.state.worker = None
    app.state.scheduler = None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-OpenAI-Key", "X-Ledgic-Signature", "Accept"],
    )
    envelope.install(app)
    app.include_router(admin.router)
    app.include_router(routes.router)
    if http_app is not None:
        app.add_route("/mcp", http_app(), methods=["GET", "POST", "DELETE"])
    return app


app = create_app()
