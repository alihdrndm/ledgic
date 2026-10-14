"""Background resolution-agent drafts for new money exceptions (DECISIONS D9).

The pipeline never waits for them and never spends LLM budget on them: drafts made here use a
fixture-mode gateway (recorded hero draft or deterministic template). Visitors can regenerate a live
draft from the Exceptions screen (POST /v1/exceptions/{id}/draft with regenerate=true).
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("ledgic.orchestrator.drafts")

_queue: asyncio.Queue[str] | None = None
_task: asyncio.Task[None] | None = None


def _offline_gateway():  # type: ignore[no-untyped-def]
    from app.ai.gateway import LlmGateway
    from app.config import get_settings

    return LlmGateway(settings=get_settings().model_copy(update={"llm_mode": "fixture"}))


async def make_draft(exception_id: str) -> None:
    try:
        from app.ai import draft_for_exception

        await draft_for_exception(exception_id, gateway=_offline_gateway())
    except Exception as e:  # never break anything for a draft
        log.info("draft for %s skipped: %s", exception_id, e)


async def _drain() -> None:
    assert _queue is not None
    while True:
        exc_id = await _queue.get()
        try:
            await make_draft(exc_id)
        finally:
            _queue.task_done()


def enqueue_draft(exception_id: str) -> None:
    """Queue a draft; a single background consumer works through them one at a time."""
    global _queue, _task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _queue is None:
        _queue = asyncio.Queue(maxsize=500)
    if _task is None or _task.done():
        _task = loop.create_task(_drain(), name="ledgic-drafts")
    try:
        _queue.put_nowait(exception_id)
    except asyncio.QueueFull:
        log.warning("draft queue full; skipping %s", exception_id)


async def stop() -> None:
    global _task, _queue
    if _task is not None:
        _task.cancel()
        _task = None
    _queue = None
