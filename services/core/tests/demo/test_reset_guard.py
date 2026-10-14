"""Scheduled replay ticks must not run while /v1/admin/reset-demo rebuilds the org."""

from __future__ import annotations

from app.demo import replay
from app.scheduler.jobs import Scheduler


async def test_scheduled_tick_skips_during_reset(monkeypatch):
    async def exists(*_a, **_k):
        return True

    async def boom(*_a, **_k):  # pragma: no cover - must not be called
        raise AssertionError("tick ran during a reset")

    monkeypatch.setattr(replay, "demo_org_exists", exists)
    monkeypatch.setattr(replay, "tick", boom)
    replay.set_reset_in_progress(True)
    try:
        assert await Scheduler()._replay() == "demo reset in progress"
    finally:
        replay.set_reset_in_progress(False)
    assert replay.reset_in_progress() is False
