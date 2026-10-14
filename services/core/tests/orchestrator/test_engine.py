"""Engine transitions and resume branching with a fake repository (no database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.orchestrator import engine as engine_mod
from app.orchestrator.context import Clock, Options, RunRow, StageContext
from app.orchestrator.engine import Engine, pending_decision
from app.orchestrator.stages import Stage
from app.orchestrator.transitions import MAX_ATTEMPTS, StageError, Transition

T0 = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)


class FakeRuns:
    def __init__(self, rows: dict[str, dict[str, Any]]) -> None:
        self.rows = rows
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.dead: list[dict[str, Any]] = []

    async def update_run(self, conn: Any, run_id: str, **fields: Any) -> None:
        self.updates.append((run_id, fields))
        self.rows[run_id].update(fields)

    async def insert_dead_letter(self, conn: Any, **kw: Any) -> None:
        self.dead.append(kw)

    async def lock_run(self, conn: Any, run_id: str, **kw: Any) -> dict[str, Any] | None:
        return self.rows.get(run_id)


class FakeJournal:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.audit: list[dict[str, Any]] = []

    async def emit_event(self, conn: Any, **kw: Any) -> int:
        self.events.append(kw)
        return len(self.events)

    async def write_audit(self, conn: Any, **kw: Any) -> None:
        self.audit.append(kw)


class FakeConn:
    def __init__(self) -> None:
        self.sql: list[tuple[str, Any]] = []

    async def execute(self, sql: str, params: Any = None) -> None:
        self.sql.append((sql, params))


def row(**over: Any) -> dict[str, Any]:
    base = {
        "id": "run-1",
        "run_number": 7,
        "org_id": "org-1",
        "document_id": "doc-1",
        "invoice_id": "inv-1",
        "status": "running",
        "current_stage": "intake",
        "next_stage": "intake",
        "attempt": 0,
        "context": {},
        "wait_exception_id": None,
        "started_at": T0,
        "workflow_version": "v1",
    }
    base.update(over)
    return base


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeRuns, FakeJournal]:
    runs = FakeRuns({})
    journal = FakeJournal()
    monkeypatch.setattr(engine_mod, "runs_repo", runs)
    monkeypatch.setattr(engine_mod, "journal", journal)

    async def _noop_invoice(conn: Any, invoice_id: str, **kw: Any) -> None:
        return None

    monkeypatch.setattr(engine_mod, "update_invoice", _noop_invoice)
    return runs, journal


async def _policy(conn: Any, org_id: str) -> dict[str, Any]:
    return {"sla_hours": 24}


def make_engine(handlers: dict[Stage, Any], exhausted: dict[Stage, Any] | None = None, **opt: Any) -> Engine:
    return Engine(handlers=handlers, exhausted=exhausted or {}, options=Options(**opt), policy_loader=_policy)


async def test_advance_updates_run_and_emits_succeeded(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    r = row()
    runs.rows["run-1"] = r

    async def intake(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.advance(Stage.EXTRACTION, "Received — email PDF, 2 pages", "ap@x · SHA-256 stored")

    eng = make_engine({Stage.INTAKE: intake})
    res = await eng.step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    assert res.stage == Stage.INTAKE
    _, upd = runs.updates[-1]
    assert upd["next_stage"] == "extraction" and upd["status"] == "running" and upd["attempt"] == 0
    assert upd["lease_owner"] is None
    ev = journal.events[-1]
    assert ev["status"] == "succeeded" and ev["stage"] == "intake"
    assert ev["summary"] == "Received — email PDF, 2 pages" and ev["sub"] == "ap@x · SHA-256 stored"


async def test_virtual_clock_advances_by_modeled_duration(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    r = row(next_stage="extraction")
    runs.rows["run-1"] = r

    async def extraction(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.advance(Stage.ENRICHMENT, "Extracted", duration_ms=4200)

    clock = Clock(T0)
    await make_engine({Stage.EXTRACTION: extraction}).step(FakeConn(), r, clock)  # type: ignore[arg-type]
    assert clock.now() == T0 + timedelta(milliseconds=4200)
    assert journal.events[-1]["at"] == T0 + timedelta(milliseconds=4200)
    assert journal.events[-1]["duration_ms"] == 4200


async def test_park_sets_waiting_and_links_exception(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    r = row(next_stage="approval")
    runs.rows["run-1"] = r

    async def approval(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.park("exc-9", "Waiting for AP manager — price variance")

    conn = FakeConn()
    await make_engine({Stage.APPROVAL: approval}).step(conn, r, Clock(T0))  # type: ignore[arg-type]
    _, upd = runs.updates[-1]
    assert upd["status"] == "waiting" and upd["wait_exception_id"] == "exc-9"
    assert upd["context"]["parked_stage"] == "approval"
    assert journal.events[-1]["status"] == "waiting"
    assert any("update exceptions set run_id" in s for s, _ in conn.sql)


async def test_retry_backoff_then_exhausted_hook(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    r = row(next_stage="posting")
    runs.rows["run-1"] = r

    async def posting(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.retry("QuickBooks API 503")

    hook_calls: list[str] = []

    async def exhausted(ctx: StageContext, run: RunRow, err: str) -> Transition:
        hook_calls.append(err)
        return Transition.park("exc-pf", "Posting failed — QuickBooks unavailable")

    eng = make_engine({Stage.POSTING: posting}, {Stage.POSTING: exhausted})
    await eng.step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    _, upd = runs.updates[-1]
    assert upd["attempt"] == 1 and upd["next_attempt_at"] == T0 + timedelta(seconds=10)
    assert journal.events[-1]["status"] == "failed"
    for _ in range(MAX_ATTEMPTS - 1):
        await eng.step(FakeConn(), runs.rows["run-1"], Clock(T0))  # type: ignore[arg-type]
    assert hook_calls == ["QuickBooks API 503"]
    assert runs.rows["run-1"]["status"] == "waiting"
    assert runs.rows["run-1"]["wait_exception_id"] == "exc-pf"
    assert not runs.dead


async def test_retry_exhausted_without_hook_fails_and_dead_letters(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    r = row(next_stage="enrichment", attempt=MAX_ATTEMPTS - 1)
    runs.rows["run-1"] = r

    async def enrichment(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.retry("boom")

    await make_engine({Stage.ENRICHMENT: enrichment}).step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    assert runs.rows["run-1"]["status"] == "failed"
    assert runs.dead and "gave up" in runs.dead[0]["error"]
    assert journal.audit[-1]["action"] == "run.failed"


async def test_fast_mode_retries_immediately(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, _ = fakes
    r = row(next_stage="posting")
    runs.rows["run-1"] = r

    async def posting(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.retry("down")

    await make_engine({Stage.POSTING: posting}, fast=True).step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    assert runs.rows["run-1"]["next_attempt_at"] == T0


async def test_record_failure_schedules_retry(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    runs.rows["run-1"] = row(next_stage="match", attempt=2)
    eng = make_engine({})
    tr = await eng.record_failure(FakeConn(), "run-1", StageError("db hiccup"), Clock(T0))  # type: ignore[arg-type]
    assert tr is not None and tr.kind == "retry"
    assert runs.rows["run-1"]["attempt"] == 3
    assert runs.rows["run-1"]["next_attempt_at"] == T0 + timedelta(seconds=60)
    assert "db hiccup" in journal.events[-1]["detail"]["error"]


@pytest.mark.parametrize(
    ("action", "stage"),
    [
        ("short_pay", Stage.POSTING),
        ("approve_as_is", Stage.POSTING),
        ("approve_without_po", Stage.POSTING),
        ("retry_posting", Stage.POSTING),
        ("link_po", Stage.MATCH),
        ("release_hold", Stage.SCREENING),
        ("not_duplicate", Stage.SCREENING),
        ("reject_invoice", Stage.CLOSE),
        ("reject_copy", Stage.CLOSE),
        ("confirm_fields", Stage.REVIEW),
    ],
)
async def test_resume_runs_the_routed_stage(fakes: tuple[FakeRuns, FakeJournal], action: str, stage: Stage) -> None:
    runs, _ = fakes
    decision = {"action": action, "approval_id": "ap-1", "pay_amount": "2759.60", "hold_amount": "88.00"}
    r = row(current_stage="approval", next_stage="posting", context={"decision": decision, "parked_stage": "approval"})
    runs.rows["run-1"] = r
    seen: list[tuple[Stage, dict[str, Any] | None]] = []

    def handler_for(s: Stage) -> Any:
        async def h(ctx: StageContext, run: RunRow) -> Transition:
            seen.append((s, ctx.decision))
            return Transition.finish("done")

        return h

    eng = make_engine({s: handler_for(s) for s in Stage})
    await eng.step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    assert seen[0][0] == stage
    assert seen[0][1] is not None and seen[0][1]["action"] == action
    ctx = runs.rows["run-1"]["context"]
    assert ctx["consumed_decision"] == "ap-1"
    assert ctx["decisions"][-1]["action"] == action
    # a consumed decision is not replayed
    assert pending_decision(RunRow.of(runs.rows["run-1"])) is None


async def test_dispute_keeps_the_run_parked(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, journal = fakes
    r = row(
        current_stage="approval",
        context={"decision": {"action": "dispute", "approval_id": "ap-2"}, "last_exception_id": "exc-1"},
        wait_exception_id=None,
    )
    runs.rows["run-1"] = r
    await make_engine({}).step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    assert runs.rows["run-1"]["status"] == "waiting"
    assert runs.rows["run-1"]["wait_exception_id"] == "exc-1"


async def test_merge_keeps_this_invoice_continues(fakes: tuple[FakeRuns, FakeJournal], monkeypatch: pytest.MonkeyPatch) -> None:
    runs, _ = fakes
    status = {"value": "screened"}

    async def fake_val(conn: Any, sql: str, params: Any = None) -> Any:
        return status["value"]

    monkeypatch.setattr(engine_mod, "val", fake_val)
    seen: list[Stage] = []

    def handler_for(s: Stage) -> Any:
        async def h(ctx: StageContext, run: RunRow) -> Transition:
            seen.append(s)
            return Transition.finish("done")

        return h

    eng = make_engine({s: handler_for(s) for s in Stage})
    r = row(context={"decision": {"action": "merge", "approval_id": "m1"}})
    runs.rows["run-1"] = r
    await eng.step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    status["value"] = "duplicate"
    r2 = row(id="run-1", context={"decision": {"action": "merge", "approval_id": "m2"}})
    runs.rows["run-1"] = r2
    await eng.step(FakeConn(), r2, Clock(T0))  # type: ignore[arg-type]
    assert seen == [Stage.SCREENING, Stage.CLOSE]


def test_pending_decision_infers_confirm_fields_at_review() -> None:
    run = RunRow.of(row(context={"decision": {"approval_id": "x"}, "parked_stage": "review"}))
    d = pending_decision(run)
    assert d is not None and d["action"] == "confirm_fields"


async def test_sync_driver_holds_lease_between_steps(fakes: tuple[FakeRuns, FakeJournal]) -> None:
    runs, _ = fakes
    r = row()
    runs.rows["run-1"] = r

    async def intake(ctx: StageContext, run: RunRow) -> Transition:
        return Transition.advance(Stage.EXTRACTION, "ok")

    await make_engine({Stage.INTAKE: intake}, hold_lease=True).step(FakeConn(), r, Clock(T0))  # type: ignore[arg-type]
    assert runs.rows["run-1"]["lease_owner"] == "sync"
