"""What a stage handler returns, and the retry policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from .stages import Stage

Kind = Literal["advance", "park", "retry", "finish", "fail"]

MAX_ATTEMPTS = 5
# WF-20 backoff (06 §2): 10/30/60/120/300 s
BACKOFF_SECONDS = (10, 30, 60, 120, 300)


def backoff(attempt: int) -> timedelta:
    """Delay before attempt number `attempt + 1` (attempt is 1-based count of failures so far)."""
    i = max(0, min(attempt - 1, len(BACKOFF_SECONDS) - 1))
    return timedelta(seconds=BACKOFF_SECONDS[i])


@dataclass
class Transition:
    kind: Kind
    next_stage: Stage | None = None
    exception_id: str | None = None
    delay: timedelta | None = None
    error: str | None = None
    summary: str | None = None
    sub: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)  # merged into pipeline_runs.context
    drop_context: tuple[str, ...] = ()
    run_status: str = "succeeded"  # for finish
    duration_ms: int | None = None  # modeled duration (simulated extraction, mock ERP); else measured
    invoice_id: str | None = None

    # ---- constructors -------------------------------------------------------------------------
    @classmethod
    def advance(
        cls, next_stage: Stage, summary: str | None = None, sub: str | None = None, **kw: Any
    ) -> Transition:
        return cls("advance", next_stage=next_stage, summary=summary, sub=sub, **kw)

    @classmethod
    def park(
        cls, exception_id: str, summary: str | None = None, sub: str | None = None, **kw: Any
    ) -> Transition:
        return cls("park", exception_id=exception_id, summary=summary, sub=sub, **kw)

    @classmethod
    def retry(cls, error: str, delay: timedelta | None = None, **kw: Any) -> Transition:
        return cls("retry", error=error, delay=delay, **kw)

    @classmethod
    def finish(
        cls, summary: str | None = None, sub: str | None = None, run_status: str = "succeeded", **kw: Any
    ) -> Transition:
        return cls("finish", summary=summary, sub=sub, run_status=run_status, **kw)

    @classmethod
    def fail(cls, error: str, **kw: Any) -> Transition:
        return cls("fail", error=error, **kw)


class StageError(Exception):
    """Raised by handlers for a retryable failure (the txn is rolled back, then the run is retried)."""


class FatalStageError(Exception):
    """Raised by handlers for a non-retryable failure (run fails immediately + dead letter)."""
