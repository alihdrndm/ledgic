"""Backfill demo history through the real orchestrator stages (synchronous fast path).

    uv run python -m app.demo.backfill --days 30 [--per-day 180] [--today]

Every historical document goes through the same stage handlers as live documents — simulated
extraction, enrichment, screening, three-way match, mock ERP posting (no latency sleeps) — with a
virtual clock starting at its planned release time. Non-hero exceptions are decided by the
"Demo replay" AP manager via the decision RPCs after their simulated delay; anything it may not
decide is closed by demo housekeeping after 3 days. The KPIs are therefore genuinely computed.
Heroes are not backfilled (their numbers are stable); `--today` (or POST /v1/admin/seed-today)
releases today's documents up to now, heroes included.

Idempotent: documents that already exist are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from app.db.pool import close_pool, connection, open_pool
from app.demo.corpus.catalog import ORG_ID
from app.demo.planner import backfill_days
from app.orchestrator import Clock, drive_run
from app.repo.sql import exists_fn, val

from .replay import (
    TZ,
    auto_resolve_stale,
    catalog_for,
    decide_due,
    local_today,
    persist_masters,
    refresh_unlisted_vendor,
    release_doc,
    sync_engine,
    tick,
)

log = logging.getLogger("ledgic.backfill")


async def refresh_kpis() -> None:
    async with connection() as conn:
        if await exists_fn(conn, "refresh_kpis"):
            await conn.execute("select public.refresh_kpis()")


async def backfill(
    days: int, per_day: int = 180, *, org_id: str = ORG_ID, progress: bool = True
) -> dict[str, int]:
    today = local_today()
    cat = catalog_for(today)
    engine = sync_engine()
    far = datetime.now(UTC) + timedelta(days=3650)
    totals = {"days": 0, "runs": 0, "decided": 0, "auto_resolved": 0}
    async with connection() as conn, conn.transaction():
        if not await val(conn, "select 1 from orgs where id = %s", (org_id,)):
            raise SystemExit(f"org {org_id} is not seeded — run the master-data seed first")
        await refresh_unlisted_vendor(conn, cat)
    for day, docs in backfill_days(cat, days, n=per_day):
        t0 = time.perf_counter()
        async with connection() as conn, conn.transaction():
            await persist_masters(conn, org_id, docs)
        created = 0
        for d in docs:
            totals["decided"] += await decide_due(engine, d.release_at, org_id=org_id, sync_before=far)
            rel = await release_doc(d, org_id=org_id, render=False, live=False)
            if rel is None:
                continue
            created += 1
            await drive_run(engine, rel.run_id, Clock(d.release_at), connection_factory=connection)
        end_of_day = datetime.combine(day, datetime.max.time(), tzinfo=TZ).replace(microsecond=0)
        totals["decided"] += await decide_due(engine, end_of_day, org_id=org_id, sync_before=far)
        totals["auto_resolved"] += await auto_resolve_stale(engine, end_of_day, org_id=org_id, backdate=True)
        totals["runs"] += created
        totals["days"] += 1
        if progress:
            print(f"{day}: {created} runs in {time.perf_counter() - t0:.1f}s", flush=True)
    await refresh_kpis()
    return totals


async def seed_today(*, render: bool = True, per_day: int = 180, org_id: str = ORG_ID) -> int:
    """Release today's planned documents up to now (heroes included), processed synchronously."""
    stats = await tick(datetime.now(UTC), org_id=org_id, render=render, live_window=timedelta(0), n=per_day)
    await refresh_kpis()
    return len(stats.dropped)


async def _main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--per-day", type=int, default=180)
    ap.add_argument("--today", action="store_true", help="also release today's documents up to now")
    ap.add_argument("--no-render", action="store_true", help="with --today: do not render/upload files")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    await open_pool()
    try:
        t0 = time.perf_counter()
        if args.days > 0:
            print(await backfill(args.days, args.per_day))
        if args.today:
            print({"today_runs": await seed_today(render=not args.no_render, per_day=args.per_day)})
        print(f"done in {time.perf_counter() - t0:.0f}s")
    finally:
        await close_pool()


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
