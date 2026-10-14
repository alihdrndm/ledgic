"""The durable state machine: run one stage for one run and persist the transition atomically.

    claim (FOR UPDATE SKIP LOCKED) → resolve stage (resume routing) → handler → apply transition
    → pipeline_events + audit_log (+ cost_ledger in handlers) → commit

A handler exception rolls the whole step back; `record_failure` then schedules a retry with backoff
(10/30/60/120/300 s), and after 5 failures either the stage's exhausted hook (posting → posting_failed
exception) or fail + dead letter.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg import AsyncConnection

from app.repo import journal
from app.repo import runs as runs_repo
from app.repo.invoices import update_invoice
from app.repo.master import org_policy
from app.repo.sql import val

from .context import Clock, Options, RunRow, StageContext
from .routing import PARK, route_resume
from .stages import Stage
from .transitions import MAX_ATTEMPTS, FatalStageError, Transition, backoff

log = logging.getLogger("ledgic.orchestrator")

Handler = Callable[[StageContext, RunRow], Awaitable[Transition]]
ExhaustedHook = Callable[[StageContext, RunRow, str], Awaitable[Transition]]


@dataclass
class StepResult:
    run_id: str
    stage: Stage | str
    transition: Transition
    after_commit: list[Callable[[], Any]] = field(default_factory=list)


def pending_decision(run: RunRow) -> dict[str, Any] | None:
    """The decision written by an RPC that this orchestrator has not consumed yet."""
    d = run.context.get("decision")
    if not isinstance(d, dict) or not d:
        return None
    key = str(d.get("approval_id") or d.get("action") or "")
    if not key or key == run.context.get("consumed_decision"):
        return None
    d = dict(d)
    if not d.get("action") and run.context.get("parked_stage") == Stage.REVIEW:
        d["action"] = "confirm_fields"
    return d


class Engine:
    def __init__(
        self,
        handlers: dict[Stage, Handler] | None = None,
        exhausted: dict[Stage, ExhaustedHook] | None = None,
        options: Options | None = None,
        byok_keys: dict[str, str] | None = None,
        policy_loader: Callable[[AsyncConnection, str], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        if handlers is None or exhausted is None:
            from .handlers import EXHAUSTED, HANDLERS

            handlers = handlers if handlers is not None else HANDLERS
            exhausted = exhausted if exhausted is not None else EXHAUSTED
        self.handlers = handlers
        self.exhausted = exhausted
        self.options = options or Options()
        self.byok_keys = byok_keys if byok_keys is not None else {}
        self._policy_loader = policy_loader or org_policy
        self._policy_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def _policy(self, conn: AsyncConnection, org_id: str) -> dict[str, Any]:
        hit = self._policy_cache.get(org_id)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        p = await self._policy_loader(conn, org_id)
        self._policy_cache[org_id] = (time.monotonic() + 30, p)
        return p

    def _ctx(self, conn: AsyncConnection, run: RunRow, clock: Clock, policy: dict[str, Any]) -> StageContext:
        return StageContext(
            conn=conn, clock=clock, options=self.options, policy=policy, byok_key=self.byok_keys.get(run.id)
        )

    # ------------------------------------------------------------------------------------------ step

    async def resolve_stage(
        self, conn: AsyncConnection, run: RunRow
    ) -> tuple[Stage | str, dict[str, Any] | None]:
        decision = pending_decision(run)
        if decision is None:
            return Stage(run.next_stage or Stage.INTAKE), None
        status = None
        if decision.get("action") == "merge" and run.invoice_id:
            status = await val(conn, "select status::text from invoices where id = %s", (run.invoice_id,))
        return route_resume(str(decision["action"]), invoice_status=status), decision

    async def step(self, conn: AsyncConnection, row: dict[str, Any], clock: Clock) -> StepResult:
        """Run the next stage of a locked, running run inside the caller's transaction."""
        run = RunRow.of(row)
        policy = await self._policy(conn, run.org_id)
        ctx = self._ctx(conn, run, clock, policy)
        stage, decision = await self.resolve_stage(conn, run)
        consumed: dict[str, Any] = {}
        if decision is not None:
            ctx.decision = decision
            history = list(run.context.get("decisions") or [])
            history.append(decision)
            consumed = {
                "consumed_decision": str(decision.get("approval_id") or decision.get("action")),
                "decisions": history,
            }
            run.context.update(consumed)
        if stage == PARK:
            exc = run.wait_exception_id or run.context.get("last_exception_id")
            tr = (
                Transition.park(str(exc), summary="Waiting — on hold", context=consumed)
                if exc
                else Transition.fail("dispute without exception")
            )
            await self.apply(ctx, run, Stage(run.current_stage), tr, 0)
            return StepResult(run.id, stage, tr, ctx.after_commit)
        stage = Stage(stage)
        handler = self.handlers[stage]
        t0 = time.perf_counter()
        try:
            tr = await handler(ctx, run)
        except FatalStageError as e:
            tr = Transition.fail(str(e))
        measured = int((time.perf_counter() - t0) * 1000)
        tr.context = {**consumed, **tr.context}
        await self.apply(ctx, run, stage, tr, measured)
        return StepResult(run.id, stage, tr, ctx.after_commit)

    # ------------------------------------------------------------------------------------------ apply

    async def apply(
        self, ctx: StageContext, run: RunRow, stage: Stage, tr: Transition, measured_ms: int
    ) -> None:
        conn = ctx.conn
        dur = tr.duration_ms if tr.duration_ms is not None else measured_ms
        ctx.clock.advance(timedelta(milliseconds=dur))
        now = ctx.now()
        new_ctx = {**run.context, **tr.context}
        for k in tr.drop_context:
            new_ctx.pop(k, None)
        common: dict[str, Any] = {
            "lease_owner": None,
            "lease_until": None,
            "orchestrator_version": self.options.version,
        }
        if self.options.hold_lease and tr.kind in ("advance", "retry"):
            # synchronous driver: keep the worker away while this process drives the run
            common["lease_owner"] = "sync"
            common["lease_until"] = datetime.now(UTC) + timedelta(minutes=15)
        if tr.invoice_id:
            common["invoice_id"] = tr.invoice_id
            run.invoice_id = tr.invoice_id
        detail = dict(tr.detail)

        if tr.kind == "retry":
            attempt = run.attempt + 1
            if attempt >= MAX_ATTEMPTS:
                hook = self.exhausted.get(stage)
                err = tr.error or "failed"
                if hook is not None:
                    await journal.emit_event(
                        conn,
                        org_id=run.org_id,
                        run_id=run.id,
                        stage=stage.value,
                        status="failed",
                        at=now,
                        duration_ms=dur,
                        summary=tr.summary or f"Failed — {err}",
                        sub=f"gave up after {attempt} attempts",
                        detail={**detail, "attempt": attempt, "error": err},
                    )
                    follow = await hook(ctx, run, err)
                    follow.context = {**tr.context, **follow.context}
                    run.attempt = 0
                    await self.apply(ctx, run, stage, follow, 0)
                    return
                tr = Transition.fail(f"{err} (gave up after {attempt} attempts)")
            else:
                delay = tr.delay if tr.delay is not None else backoff(attempt)
                if self.options.fast:
                    delay = timedelta(0)
                await runs_repo.update_run(
                    conn,
                    run.id,
                    status="running",
                    current_stage=stage.value,
                    next_stage=stage.value,
                    attempt=attempt,
                    next_attempt_at=now + delay,
                    last_error=tr.error,
                    context=new_ctx,
                    **common,
                )
                await journal.emit_event(
                    conn,
                    org_id=run.org_id,
                    run_id=run.id,
                    stage=stage.value,
                    status="failed",
                    at=now,
                    duration_ms=dur,
                    summary=tr.summary or f"Retrying — {tr.error}",
                    sub=tr.sub
                    or f"attempt {attempt} of {MAX_ATTEMPTS} · next try in {int(delay.total_seconds())}s",
                    detail={
                        **detail,
                        "attempt": attempt,
                        "error": tr.error,
                        "retry_in_s": int(delay.total_seconds()),
                    },
                )
                return

        if tr.kind == "advance":
            assert tr.next_stage is not None
            await runs_repo.update_run(
                conn,
                run.id,
                status="running",
                current_stage=stage.value,
                next_stage=tr.next_stage.value,
                attempt=0,
                next_attempt_at=now,
                last_error=None,
                wait_exception_id=None,
                context=new_ctx,
                **common,
            )
            await journal.emit_event(
                conn,
                org_id=run.org_id,
                run_id=run.id,
                stage=stage.value,
                status="succeeded",
                at=now,
                duration_ms=dur,
                summary=tr.summary,
                sub=tr.sub,
                detail=detail,
            )
        elif tr.kind == "park":
            assert tr.exception_id
            new_ctx["parked_stage"] = stage.value
            new_ctx["last_exception_id"] = tr.exception_id
            await runs_repo.update_run(
                conn,
                run.id,
                status="waiting",
                current_stage=stage.value,
                next_stage=stage.value,
                attempt=0,
                wait_exception_id=tr.exception_id,
                last_error=None,
                context=new_ctx,
                **common,
            )
            await conn.execute(
                "update exceptions set run_id = %s where id = %s and run_id is null",
                (run.id, tr.exception_id),
            )
            await journal.emit_event(
                conn,
                org_id=run.org_id,
                run_id=run.id,
                stage=stage.value,
                status="waiting",
                at=now,
                duration_ms=dur,
                summary=tr.summary,
                sub=tr.sub,
                detail={**detail, "exception_id": tr.exception_id},
            )
        elif tr.kind == "finish":
            await runs_repo.update_run(
                conn,
                run.id,
                status=tr.run_status,
                current_stage=stage.value,
                next_stage=None,
                attempt=0,
                finished_at=now,
                wait_exception_id=None,
                last_error=None,
                context=new_ctx,
                **common,
            )
            await journal.emit_event(
                conn,
                org_id=run.org_id,
                run_id=run.id,
                stage=stage.value,
                status="succeeded",
                at=now,
                duration_ms=dur,
                summary=tr.summary,
                sub=tr.sub,
                detail=detail,
            )
        elif tr.kind == "fail":
            err = tr.error or "failed"
            await runs_repo.update_run(
                conn,
                run.id,
                status="failed",
                current_stage=stage.value,
                next_stage=None,
                finished_at=now,
                last_error=err,
                context=new_ctx,
                **common,
            )
            await runs_repo.insert_dead_letter(
                conn,
                org_id=run.org_id,
                run_id=run.id,
                stage=stage.value,
                error=err,
                payload={
                    "attempt": run.attempt,
                    "context": {k: v for k, v in new_ctx.items() if k != "fixture"},
                },
            )
            if run.invoice_id:
                await update_invoice(conn, run.invoice_id, status="failed")
            await journal.emit_event(
                conn,
                org_id=run.org_id,
                run_id=run.id,
                stage=stage.value,
                status="failed",
                at=now,
                duration_ms=dur,
                summary=tr.summary or f"Failed — {err}",
                sub=tr.sub or "moved to the dead-letter queue",
                detail={**detail, "error": err},
            )
            await journal.write_audit(
                conn,
                org_id=run.org_id,
                actor_type="core",
                actor_id=self.options.owner,
                action="run.failed",
                entity_type="pipeline_run",
                entity_id=run.id,
                after={"stage": stage.value, "error": err},
                at=now,
            )
        else:  # pragma: no cover
            raise ValueError(tr.kind)

    # ------------------------------------------------------------------------------------------ failures

    async def record_failure(
        self, conn: AsyncConnection, run_id: str, error: BaseException, clock: Clock
    ) -> Transition | None:
        """After a rolled-back step: schedule a retry (or exhaust). Runs in a fresh transaction."""
        row = await runs_repo.lock_run(conn, run_id)
        if row is None or row["status"] != "running":
            return None
        run = RunRow.of(row)
        policy = await self._policy(conn, run.org_id)
        ctx = self._ctx(conn, run, clock, policy)
        try:
            stage, _ = await self.resolve_stage(conn, run)
        except Exception:
            stage = Stage(run.next_stage or Stage.INTAKE)
        stage = Stage(stage) if stage != PARK else Stage(run.current_stage)
        msg = f"{type(error).__name__}: {error}"[:500]
        tr = Transition.fail(msg) if isinstance(error, FatalStageError) else Transition.retry(msg)
        await self.apply(ctx, run, stage, tr, 0)
        return tr


# ---------------------------------------------------------------------------------------------- drivers


async def run_after_commit(callbacks: list[Callable[[], Any]]) -> None:
    for cb in callbacks:
        try:
            res = cb()
            if hasattr(res, "__await__"):
                await res
        except Exception:  # never let a side job break the pipeline
            log.exception("after-commit callback failed")


async def drive_run(
    engine: Engine,
    run_id: str,
    clock: Clock,
    *,
    connection_factory: Callable[[], Any],
    max_steps: int = 40,
) -> str:
    """Synchronously advance one run until it waits, finishes or fails (backfill, catch-up, tests).
    Returns the final run status. Each step is its own transaction."""
    status = "running"
    for _ in range(max_steps):
        callbacks: list[Callable[[], Any]] = []
        failed: BaseException | None = None
        async with connection_factory() as conn:
            try:
                async with conn.transaction():
                    row = await runs_repo.lock_run(conn, run_id)
                    if row is None:
                        return "missing"
                    status = row["status"]
                    if status != "running":
                        return status
                    res = await engine.step(conn, row, clock)
                    callbacks = res.after_commit
            except Exception as e:  # rolled back
                failed = e
            if failed is not None:
                log.warning("run %s step failed: %s", run_id, failed)
                async with conn.transaction():
                    await engine.record_failure(conn, run_id, failed, clock)
        await run_after_commit(callbacks)
    return status
