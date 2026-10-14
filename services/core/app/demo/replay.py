"""Demo replay (13-demo-data §6): release today's planned documents into the pipeline, let the
"Demo replay" AP manager decide non-hero exceptions through the same RPCs as people, and keep the
demo tidy (auto-resolve stale exceptions, nightly reset of hero cases, purge old data).

Stateless and idempotent: a planned document is "released" when its stable document id exists, so a
tick, a catch-up after downtime and `seed-today` are the same operation over different windows.

Two processing modes per document:
* live  — released within the last few minutes: create the run and let the worker process it in real time.
* sync  — released earlier (catch-up, seed-today, backfill): processed immediately with a virtual
          clock starting at the planned release time, so timestamps and KPIs are realistic.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection

from app.db.pool import as_user, connection
from app.demo.corpus import PlannedDoc, build_catalog, plan_day
from app.demo.corpus.catalog import ORG_ID, TIMEZONE, Catalog
from app.demo.corpus.rng import rng_for, sha256_hex
from app.demo.planner import is_hero_exception, should_auto_resolve, simulated_decision
from app.orchestrator import Clock, Engine, Options, drive_run
from app.repo import journal
from app.repo import master as master_repo
from app.repo import runs as runs_repo
from app.repo.sql import J, all_, one, val

log = logging.getLogger("ledgic.replay")

TZ = ZoneInfo(TIMEZONE)
REPLAY_USER_ID = "b9801444-eed3-5e24-b95e-c710ce9794a7"  # contracts/fixtures.json users.replay
UNLISTED_VENDOR_KEY = "unlisted"
LIVE_WINDOW = timedelta(minutes=10)
DOCS_PER_DAY = 180

# Set while /v1/admin/reset-demo purges and rebuilds the org. Scheduled ticks stop releasing documents
# so they cannot race the purge (a tick that persisted today's POs before the purge would otherwise
# release every document against deleted POs → all "No PO found").
_reset_in_progress = False


def set_reset_in_progress(value: bool) -> None:
    global _reset_in_progress
    _reset_in_progress = value


def reset_in_progress() -> bool:
    return _reset_in_progress


def local_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(TZ).date()


@lru_cache(maxsize=4)
def catalog_for(today: date) -> Catalog:
    return build_catalog(today)


@lru_cache(maxsize=4)
def schedule_for(day: date, n: int = DOCS_PER_DAY) -> tuple[PlannedDoc, ...]:
    """Today's plan (heroes included); the catalog is built for `day` so rolling dates hold."""
    return tuple(plan_day(catalog_for(day), day, n=n))


def storage_path(org_id: str, doc: PlannedDoc) -> str:
    return f"org/{org_id}/docs/{doc.document_id}/{doc.file_name}"


def source_meta(doc: PlannedDoc) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "replay": True,
        "doc_key": doc.key,
        "demo_day": doc.day.isoformat(),
        "location_id": doc.location_id,
        "extraction_mode": "recorded" if doc.hero else "simulated",
        "condition": doc.condition,
    }
    if doc.hero:
        meta["hero"] = doc.hero
    if doc.channel == "email":
        meta["inbox"] = "ap@northside.ledgic.dev"
    if doc.skew_deg is not None:
        meta["skew_deg"] = doc.skew_deg
    if doc.duplicate_of:
        meta["duplicate_of_key"] = doc.duplicate_of
    return meta


# ------------------------------------------------------------------------------------------- masters


async def persist_masters(conn: AsyncConnection, org_id: str, docs: Iterable[PlannedDoc]) -> int:
    """POs/GRNs for the given docs, before their documents are released (duplicate copies carry none)."""
    seen: set[str] = set()
    n = 0
    for d in docs:
        if d.po and d.po["po_number"] not in seen:
            seen.add(d.po["po_number"])
            await master_repo.upsert_po(conn, org_id, d.po)
            n += 1
            if d.grn:
                await master_repo.upsert_grn(conn, org_id, d.grn)
    return n


async def refresh_unlisted_vendor(conn: AsyncConnection, catalog: Catalog) -> None:
    """The fraud-case vendor must stay ~4 days old (13 §2)."""
    v = catalog.vendor(UNLISTED_VENDOR_KEY)
    created = datetime.combine(v.created_on, datetime.min.time(), tzinfo=TZ) + timedelta(hours=10)
    await conn.execute(
        "update vendors set created_at = %s, remit_address_changed_at = %s where id = %s and created_at <> %s",
        (created, created, v.id, created),
    )


# ------------------------------------------------------------------------------------------- release


@dataclass
class Released:
    document_id: str
    run_id: str
    channel: str
    hero: str | None
    mode: str  # live | sync
    release_at: datetime


@dataclass
class ReplayStats:
    dropped: list[Released] = field(default_factory=list)
    decided: int = 0
    auto_resolved: int = 0


async def release_doc(
    doc: PlannedDoc,
    *,
    org_id: str = ORG_ID,
    render: bool = True,
    live: bool = False,
    workflow_version: str = "v1",
) -> Released | None:
    """Create document + run for a planned doc (idempotent by its stable document id)."""
    async with connection() as conn:
        if await val(conn, "select 1 from documents where id = %s", (doc.document_id,)):
            return None
    path = storage_path(org_id, doc)
    pages, mime, phash = doc.pages, doc.mime, None
    preprocessing = {"skew_deg": doc.skew_deg, "pages": doc.pages} if doc.skew_deg is not None else None
    if render:
        rendered = await asyncio.to_thread(doc.render)
        from app.repo.storage import upload_object

        await upload_object(path, rendered.content, rendered.mime)
        sha, pages, mime = rendered.sha256, rendered.pages, rendered.mime
        try:
            phash = await asyncio.to_thread(rendered.phash)
        except Exception:
            phash = None
        if rendered.skew_deg is not None:
            preprocessing = {"skew_deg": rendered.skew_deg, "pages": pages}
    else:
        sha = sha256_hex(f"planned:{doc.key}")  # not rendered (history): stable synthetic hash
    meta = source_meta(doc)
    if not render:
        meta["not_rendered"] = True
    ctx = {
        "fixture": doc.simulated_extraction,
        "extraction_mode": meta["extraction_mode"],
        "demo_doc_key": doc.key,
    }
    now = datetime.now(UTC)
    async with connection() as conn, conn.transaction():
        row = await runs_repo.insert_document(
            conn,
            org_id=org_id,
            channel=doc.channel,
            storage_path=path,
            sha256=sha,
            mime=mime,
            received_at=doc.release_at,
            page_count=pages,
            phash=phash,
            original_filename=doc.file_name,
            source_meta=meta,
            preprocessing=preprocessing,
            document_id=doc.document_id,
        )
        if row is None:
            return None
        run = await runs_repo.create_run(
            conn,
            org_id=org_id,
            document_id=doc.document_id,
            started_at=doc.release_at if not live else now,
            context=ctx,
            workflow_version=workflow_version,
            lease_owner=None if live else "sync",
            lease_until=None if live else now + timedelta(minutes=15),
            notify=live,
        )
    return Released(
        doc.document_id, str(run["id"]), doc.channel, doc.hero, "live" if live else "sync", doc.release_at
    )


# ------------------------------------------------------------------------------------------- decisions

_FIELD_FOR_KEY = {"vendor": "vendor_name", "po_ref": "po_reference"}


async def _confirm_payload(
    conn: AsyncConnection, invoice_id: str, flagged: list[str]
) -> list[dict[str, Any]]:
    import re

    lines = {
        r["line_no"]: r
        for r in await all_(
            conn,
            "select id::text as id, line_no, qty, unit_price, amount, description, uom from invoice_lines where invoice_id = %s",
            (invoice_id,),
        )
    }
    fields = {
        r["field"]: r["value"]
        for r in await all_(
            conn,
            "select distinct on (field) field, value from invoice_fields where invoice_id = %s order by field, version desc",
            (invoice_id,),
        )
    }
    out: list[dict[str, Any]] = []
    for key in flagged:
        m = re.match(r"^lines\[(\d+)\]\.(\w+)$", key)
        if m:
            ln = lines.get(int(m.group(1)) + 1)
            if ln and ln.get(m.group(2)) is not None:
                v = ln[m.group(2)]
                out.append(
                    {
                        "line_id": ln["id"],
                        "key": m.group(2),
                        "value": format(v, "f") if isinstance(v, Decimal) else str(v),
                    }
                )
        else:
            f = _FIELD_FOR_KEY.get(key, key)
            if fields.get(f) is not None:
                out.append({"field": f, "value": fields[f]})
    return out


async def open_replay_exceptions(conn: AsyncConnection, org_id: str) -> list[dict[str, Any]]:
    return await all_(
        conn,
        "select e.id::text as id, e.type::text as type, e.status::text as status, e.amount_at_risk, e.opened_at, "
        " e.invoice_id::text as invoice_id, e.run_id::text as run_id, i.invoice_number, d.source_meta ->> 'hero' as hero, "
        " d.source_meta ->> 'replay' as replay, r.action::text as rec_action, r.pay_amount, r.hold_amount, r.reasons "
        "from exceptions e join invoices i on i.id = e.invoice_id join documents d on d.id = i.document_id "
        "left join recommendations r on r.exception_id = e.id "
        "where e.org_id = %s and e.status in ('open','escalated') order by e.opened_at",
        (org_id,),
    )


def _exception_view(row: dict[str, Any]) -> dict[str, Any]:
    rec = None
    if row.get("rec_action"):
        rec = {"action": row["rec_action"]}
        if row.get("pay_amount") is not None:
            rec["pay_amount"] = str(row["pay_amount"])
            rec["hold_amount"] = str(row["hold_amount"])
        for r in row.get("reasons") or []:
            po_id = (r.get("facts") or {}).get("po_id")
            if po_id:
                rec["po_id"] = po_id
        if rec["action"] == "link_po" and "po_id" not in rec:
            rec = None
    return {
        "type": row["type"],
        "invoice_number": row["invoice_number"],
        "hero": row.get("hero"),
        "amount_at_risk": str(row["amount_at_risk"]),
        "recommendation": rec,
        "created_at": row["opened_at"],
    }


async def apply_decision(
    exc: dict[str, Any], decision: dict[str, Any], *, decided_at: datetime, time_spent: int, backdate: bool
) -> str | None:
    """Make the replay actor's decision through the RPC (as the Demo replay user). Returns run id."""
    action = decision["action"]
    async with connection() as conn, conn.transaction():
        await as_user(conn, REPLAY_USER_ID)
        if action == "confirm_fields":
            flagged = (
                list(
                    (
                        await val(
                            conn,
                            "select context -> 'flagged' from pipeline_runs where id = %s",
                            (exc["run_id"],),
                        )
                    )
                    or []
                )
                if exc.get("run_id")
                else []
            )
            payload = await _confirm_payload(conn, exc["invoice_id"], flagged)
            if not payload:
                return None
            res = await val(
                conn,
                "select public.rpc_confirm_fields(%s, %s, %s) as r",
                (exc["invoice_id"], J(payload), time_spent),
            )
        else:
            extra: dict[str, Any] = {}
            if action == "link_po":
                extra["po_id"] = decision.get("po_id")
            pay = Decimal(decision["pay_amount"]) if decision.get("pay_amount") else None
            hold = Decimal(decision["hold_amount"]) if decision.get("hold_amount") else None
            res = await val(
                conn,
                "select public.rpc_decide_exception(%s, %s::public.decision_action, %s, %s, %s, %s, %s) as r",
                (exc["id"], action, pay, hold, decision.get("note"), time_spent, J(extra)),
            )
        await conn.execute("reset role")
        await conn.execute("select set_config('request.jwt.claims', '', true)")
        approval_id = (res or {}).get("approval_id")
        run_id = (res or {}).get("run_id")
        if backdate and approval_id:
            await conn.execute(
                "update approvals set decided_at = %s where id = %s", (decided_at, approval_id)
            )
            await conn.execute(
                "update exceptions set resolved_at = %s where id = %s and resolved_at is not null",
                (decided_at, exc["id"]),
            )
            if run_id:
                await conn.execute(
                    "update pipeline_events set at = %s where run_id = %s and status in ('resumed','waiting') "
                    " and detail ->> 'approval_id' = %s",
                    (decided_at, run_id, str(approval_id)),
                )
            if action == "confirm_fields":
                await conn.execute(
                    "update invoice_fields set set_at = %s where invoice_id = %s and source = 'human' and set_by = %s",
                    (decided_at, exc["invoice_id"], REPLAY_USER_ID),
                )
        if run_id and backdate:  # the sync driver will take it from here
            await conn.execute(
                "update pipeline_runs set lease_owner = 'sync', lease_until = now() + interval '15 minutes' where id = %s and status = 'running'",
                (run_id,),
            )
    return str(run_id) if run_id else None


async def decide_due(
    engine: Engine | None, now: datetime, *, org_id: str = ORG_ID, sync_before: datetime | None = None
) -> int:
    """Decide every non-hero exception whose simulated delay has elapsed by `now`.
    Decisions due before `sync_before` are back-dated and their runs driven synchronously."""
    async with connection() as conn:
        rows = await open_replay_exceptions(conn, org_id)
    n = 0
    for row in rows:
        view = _exception_view(row)
        if is_hero_exception(view):
            continue
        sim = simulated_decision(view, rng_for("replay-decision", row["id"]))
        if sim is None:
            continue
        delay, decision = sim
        decided_at = row["opened_at"] + delay
        if decided_at > now:
            continue
        backdate = sync_before is not None and decided_at < sync_before
        try:
            run_id = await apply_decision(
                row,
                decision,
                decided_at=decided_at if backdate else now,
                time_spent=min(1800, int(delay.total_seconds())),
                backdate=backdate,
            )
        except Exception as e:
            log.warning("replay decision on %s (%s) failed: %s", row["id"], decision.get("action"), e)
            continue
        n += 1
        if run_id and backdate and engine is not None:
            await drive_run(engine, run_id, Clock(decided_at), connection_factory=connection)
    return n


async def housekeeping_close(
    exc: dict[str, Any], at: datetime, engine: Engine | None, *, backdate: bool
) -> None:
    """Close a stale exception the replay actor may not decide (fraud hold, above limit): resolved by
    the system, invoice rejected, run closed. Audited as a system action."""
    async with connection() as conn, conn.transaction():
        await conn.execute(
            "update exceptions set status = 'resolved', resolved_at = %s where id = %s", (at, exc["id"])
        )
        await conn.execute("update invoices set status = 'rejected' where id = %s", (exc["invoice_id"],))
        await journal.write_audit(
            conn,
            org_id=ORG_ID,
            actor_type="system",
            actor_id="demo-housekeeping",
            action="exception.auto_closed",
            entity_type="exception",
            entity_id=exc["id"],
            after={"reason": "demo: open more than 3 days", "type": exc["type"]},
            at=at if backdate else None,
        )
        if exc.get("run_id"):
            await conn.execute(
                "update pipeline_runs set status = 'running', next_stage = 'close', wait_exception_id = null, next_attempt_at = now(), "
                " lease_owner = %s, lease_until = now() + interval '15 minutes' where id = %s and status = 'waiting'",
                ("sync" if engine else None, exc["run_id"]),
            )
    if exc.get("run_id") and engine is not None:
        await drive_run(engine, exc["run_id"], Clock(at), connection_factory=connection)


async def auto_resolve_stale(
    engine: Engine | None, now: datetime, *, org_id: str = ORG_ID, backdate: bool = False
) -> int:
    async with connection() as conn:
        rows = await open_replay_exceptions(conn, org_id)
    n = 0
    for row in rows:
        view = _exception_view(row)
        if not should_auto_resolve(view, now):
            continue
        sim = simulated_decision(view, rng_for("replay-decision", row["id"]))
        try:
            if sim is not None:
                run_id = await apply_decision(
                    row,
                    sim[1],
                    decided_at=now,
                    time_spent=min(1800, int(sim[0].total_seconds())),
                    backdate=backdate,
                )
                if run_id and backdate and engine is not None:
                    await drive_run(engine, run_id, Clock(now), connection_factory=connection)
            else:
                await housekeeping_close(row, now, engine if backdate else None, backdate=backdate)
            n += 1
        except Exception as e:
            log.warning("auto-resolve %s failed: %s", row["id"], e)
    return n


# ------------------------------------------------------------------------------------------- tick


def sync_engine(version: str = "v1") -> Engine:
    return Engine(
        options=Options(
            fast=True, drafts=False, erp_latency=False, owner="replay", version=version, hold_lease=True
        )
    )


async def demo_org_exists(org_id: str = ORG_ID) -> bool:
    async with connection() as conn:
        return bool(await val(conn, "select is_demo from orgs where id = %s", (org_id,)))


async def tick(
    now: datetime | None = None,
    *,
    org_id: str = ORG_ID,
    render: bool = True,
    live_window: timedelta = LIVE_WINDOW,
    on_live: Callable[[], None] | None = None,
    n: int = DOCS_PER_DAY,
    version: str = "v1",
    respect_reset: bool = False,
) -> ReplayStats:
    """Release every planned doc of today due by `now` that is not in the database yet; docs within
    `live_window` go to the worker, older ones are processed synchronously (catch-up). Then simulated
    decisions."""
    now = now or datetime.now(UTC)
    today = local_today(now)
    cat = catalog_for(today)
    docs = [d for d in schedule_for(today, n) if d.release_at <= now]
    stats = ReplayStats()
    engine = sync_engine(version)
    async with connection() as conn, conn.transaction():
        await refresh_unlisted_vendor(conn, cat)
        await persist_masters(conn, org_id, schedule_for(today, n))
    for d in docs:
        if respect_reset and reset_in_progress():
            log.info("replay tick stopped: demo reset in progress")
            return stats
        live = (now - d.release_at) <= live_window
        try:
            if d.po:  # idempotent; re-assert in case the org was purged since the tick started
                async with connection() as conn, conn.transaction():
                    if not await val(conn, "select 1 from documents where id = %s", (d.document_id,)):
                        await persist_masters(conn, org_id, [d])
            rel = await release_doc(d, org_id=org_id, render=render, live=live, workflow_version=version)
        except Exception as e:
            log.warning("release of %s failed: %s", d.key, e)
            continue
        if rel is None:
            continue
        stats.dropped.append(rel)
        if not live:
            await drive_run(engine, rel.run_id, Clock(d.release_at), connection_factory=connection)
            stats.decided += await decide_due(
                engine,
                min(now, d.release_at + timedelta(minutes=1)),
                org_id=org_id,
                sync_before=now - live_window,
            )
    if any(r.mode == "live" for r in stats.dropped) and on_live:
        on_live()
    stats.decided += await decide_due(engine, now, org_id=org_id, sync_before=now - live_window)
    return stats


# ------------------------------------------------------------------------------------------- nightly


async def nightly(now: datetime | None = None, *, org_id: str = ORG_ID) -> dict[str, int]:
    """03:00 org-local: auto-resolve stale exceptions, drop earlier days' hero cases (visitor
    decisions on them included — today's heroes are released fresh), purge data older than 30 days,
    and drop stored files of non-hero documents older than 7 days."""
    now = now or datetime.now(UTC)
    today = local_today(now)
    out: dict[str, int] = {}
    out["auto_resolved"] = await auto_resolve_stale(None, now, org_id=org_id)
    start_today = datetime.combine(today, datetime.min.time(), tzinfo=TZ)
    async with connection() as conn, conn.transaction():
        await conn.execute(
            "update pipeline_runs set wait_exception_id = null where org_id = %s and document_id in "
            "(select id from documents where org_id = %s and source_meta ? 'hero' and received_at < %s)",
            (org_id, org_id, start_today),
        )
        cur = await conn.execute(
            "delete from documents where org_id = %s and source_meta ? 'hero' and received_at < %s returning storage_path",
            (org_id, start_today),
        )
        hero_paths = [r["storage_path"] for r in await cur.fetchall()]
        out["hero_docs_reset"] = len(hero_paths)
        await conn.execute(
            "update pipeline_runs set wait_exception_id = null where org_id = %s and document_id in "
            "(select id from documents where org_id = %s and received_at < %s - interval '30 days')",
            (org_id, org_id, now),
        )
        cur = await conn.execute(
            "delete from documents where org_id = %s and received_at < %s - interval '30 days' returning storage_path",
            (org_id, now),
        )
        old_paths = [r["storage_path"] for r in await cur.fetchall()]
        out["purged_docs"] = len(old_paths)
        await conn.execute(
            "delete from cost_ledger where org_id = %s and at < %s - interval '30 days'", (org_id, now)
        )
        await conn.execute(
            "delete from pipeline_events where org_id = %s and at < %s - interval '30 days'", (org_id, now)
        )
        rows = await all_(
            conn,
            "select id, storage_path from documents where org_id = %s and not (source_meta ? 'hero') "
            " and received_at < %s - interval '7 days' and not coalesce((source_meta ->> 'not_rendered')::boolean, false) "
            " and not coalesce((source_meta ->> 'file_purged')::boolean, false)",
            (org_id, now),
        )
        for r in rows:
            await conn.execute(
                "update documents set source_meta = source_meta || '{\"file_purged\": true}' where id = %s",
                (r["id"],),
            )
        stale_paths = [r["storage_path"] for r in rows]
        await refresh_unlisted_vendor(conn, catalog_for(today))
    try:
        from app.repo.storage import delete_objects

        out["files_deleted"] = await delete_objects(hero_paths + old_paths + stale_paths)
    except Exception as e:
        log.warning("storage purge failed: %s", e)
    return out


def rng_delay(key: str) -> random.Random:
    return rng_for("replay-decision", key)


async def run_one(doc_key: str, day: date | None = None) -> dict[str, Any] | None:
    """Helper for tests/tools: release + process one planned doc synchronously."""
    day = day or local_today()
    doc = next((d for d in schedule_for(day) if d.key == doc_key), None)
    if doc is None:
        return None
    async with connection() as conn, conn.transaction():
        await persist_masters(conn, ORG_ID, [doc])
    rel = await release_doc(doc, render=False)
    if rel is None:
        async with connection() as conn:
            return await one(conn, "select * from pipeline_runs where document_id = %s", (doc.document_id,))
    await drive_run(sync_engine(), rel.run_id, Clock(doc.release_at), connection_factory=connection)
    async with connection() as conn:
        return await runs_repo.get_run(conn, rel.run_id)
