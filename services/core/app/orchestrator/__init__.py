"""Durable pipeline orchestrator (DECISIONS D1): Postgres-backed state machine + worker.

Stage order: intake → extraction → review → enrichment → screening → match → approval → posting → close
Engine.step  — one stage for one locked run, transition applied in the same transaction
Worker       — claims runnable runs (FOR UPDATE SKIP LOCKED, lease), LISTEN ledgic_runs + 2 s poll
drive_run    — synchronous driver with a virtual clock (backfill, catch-up, tests)
"""

from .context import Clock, Options, RunRow, StageContext
from .engine import Engine, StepResult, drive_run, pending_decision
from .routing import PARK, route_resume
from .stages import ORDER, Stage, next_of
from .transitions import MAX_ATTEMPTS, FatalStageError, StageError, Transition, backoff

__all__ = [
    "MAX_ATTEMPTS",
    "ORDER",
    "PARK",
    "Clock",
    "Engine",
    "FatalStageError",
    "Options",
    "RunRow",
    "Stage",
    "StageContext",
    "StageError",
    "StepResult",
    "Transition",
    "backoff",
    "drive_run",
    "next_of",
    "pending_decision",
    "route_resume",
]
