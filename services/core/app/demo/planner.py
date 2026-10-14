"""Replay planning helpers (13-demo-data §6). Pure functions: no database, no network.

The scheduler/orchestrator owns persistence and the real channels; this module decides *what*
happens and *when*:

    schedule = plan_day(catalog, today)          # nightly 04:00 org-local
    for doc in due_docs(schedule, now, since=last_tick): release(doc)   # every 5 minutes
    simulated_decision(exception, rng)           # "Demo replay" actor on non-hero exceptions
    backfill_days(catalog, 30)                   # history so Operations has data
    historical_coded_lines(catalog)              # 6 months of coded lines for GL kNN
    prior_short_pays(catalog)                    # the two accepted PS short-pays ($61.60, $47.20)
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from .corpus.catalog import Catalog
from .corpus.heroes import HERO_KEYS, PRIOR_SHORT_PAYS
from .corpus.invoices import TZ, PlannedDoc, plan_day
from .corpus.rng import SEED, rng_for, stable_uuid

DECISION_MEDIAN_MIN = 9.0
DECISION_SIGMA = 0.6
MANAGER_LIMIT = Decimal("5000.00")
STALE_AFTER = timedelta(days=3)

__all__ = [
    "CodedLine",
    "backfill_days",
    "due_docs",
    "historical_coded_lines",
    "is_hero_exception",
    "plan_day",
    "prior_short_pays",
    "should_auto_resolve",
    "simulated_decision",
]


# --------------------------------------------------------------------------------------------- release


def due_docs(
    schedule: Sequence[PlannedDoc], now: datetime, since: datetime | None = None
) -> list[PlannedDoc]:
    """Documents with ``since < release_at <= now`` (``since=None`` = everything up to now), in order."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return sorted(
        (d for d in schedule if d.release_at <= now and (since is None or d.release_at > since)),
        key=lambda d: (d.release_at, d.key),
    )


# --------------------------------------------------------------------------------------------- decisions

_HERO_NUMBERS = {re.sub(r"[^A-Z0-9]", "", k.upper()) for k in HERO_KEYS}


def is_hero_exception(exception: Mapping[str, Any]) -> bool:
    if exception.get("hero"):
        return True
    num = str(exception.get("invoice_number") or "")
    return re.sub(r"[^A-Z0-9]", "", num.upper()) in _HERO_NUMBERS


def _delay(rng: random.Random) -> timedelta:
    minutes = math.exp(rng.gauss(math.log(DECISION_MEDIAN_MIN), DECISION_SIGMA))
    return timedelta(seconds=round(min(180.0, max(0.75, minutes)) * 60))


def simulated_decision(
    exception: Mapping[str, Any], rng: random.Random
) -> tuple[timedelta, dict[str, Any]] | None:
    """What the "Demo replay" AP manager does with a non-hero exception, and after how long.

    ``exception`` keys used: ``type`` (exception_type), ``invoice_number`` / ``hero``, ``amount_at_risk``,
    optional ``recommendation`` {action, pay_amount?, hold_amount?, po_id?, confidence?}.
    Returns ``(delay, {"action": decision_action, ...params, "note": str})`` or ``None`` when the replay
    must leave it open: hero cases (visitors decide them), fraud holds (controller only), or impact
    above the manager limit.
    """
    if is_hero_exception(exception):
        return None
    etype = exception.get("type")
    if etype == "new_vendor_screen":
        return None
    impact = Decimal(str(exception.get("amount_at_risk") or "0"))
    if impact > MANAGER_LIMIT and etype != "extraction_review":
        return None
    rec = exception.get("recommendation") or {}
    delay = _delay(rng)
    if rec.get("action"):
        action = {k: v for k, v in rec.items() if k in ("action", "pay_amount", "hold_amount", "po_id")}
        action["note"] = "Accepted recommendation (demo replay)"
        return delay, action
    default = {
        "extraction_review": "confirm_fields",
        "price_variance": "approve_as_is",
        "qty_mismatch": "approve_as_is",
        "no_po": "approve_without_po",
        "unmatched_line": "approve_as_is",
        "duplicate": "reject_copy",
        "posting_failed": "retry_posting",
    }.get(str(etype))
    if default is None:
        return None
    return delay, {"action": default, "note": "Default action (demo replay)"}


def should_auto_resolve(exception: Mapping[str, Any], now: datetime) -> bool:
    """Nightly close-out: non-hero exceptions older than 3 days are resolved by the replay actor."""
    created = exception.get("created_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    return bool(created) and not is_hero_exception(exception) and now - created > STALE_AFTER


# --------------------------------------------------------------------------------------------- history


def backfill_days(
    catalog: Catalog, days: int, n: int = 180, seed: int = SEED, end: date | None = None
) -> Iterator[tuple[date, list[PlannedDoc]]]:
    """Plans for the ``days`` days before ``end`` (default catalog.today), oldest first, heroes excluded
    (hero invoice numbers are stable and would collide as duplicates)."""
    end = end or catalog.today
    for k in range(days, 0, -1):
        day = end - timedelta(days=k)
        yield day, plan_day(catalog, day, n=n, seed=seed, include_heroes=False)


@dataclass(frozen=True)
class CodedLine:
    id: str
    date: date
    vendor_key: str
    vendor_id: str
    location_code: str
    location_id: str
    entity_n: int
    item_key: str
    description: str  # as printed on the historical invoice (noisy variants)
    gl_account: str  # e.g. "5000"
    amount: str


def _variant(desc: str, r: random.Random) -> str:
    x = r.random()
    if x < 0.25:
        return desc.upper()
    if x < 0.4:
        return desc.replace(" × ", " x ").replace("×", "x")
    if x < 0.55:
        return re.sub(r"\s+\d+(\.\d+)?(lb|oz|ct|gal|L|ml|kg|in|qt)\b", "", desc) or desc
    if x < 0.65:
        return desc.lower()
    if x < 0.75:
        return f"{desc} - fresh" if r.random() < 0.5 else f"{desc} (sub)"
    return desc


def historical_coded_lines(
    catalog: Catalog, months: int = 6, per_day: int = 60, seed: int = SEED
) -> Iterator[CodedLine]:
    """Back-history of coded invoice lines for GL kNN (default 6 months × 60 lines/day ≈ 11k rows)."""
    start = catalog.today - timedelta(days=round(months * 30.4))
    vendors = [v for v in catalog.vendors if v.key != "unlisted"]
    weights = {
        "produce": 5,
        "broadline": 4,
        "protein": 3,
        "bakery": 2,
        "dairy": 2,
        "beverage": 1.5,
        "paper": 1.2,
        "equipment": 0.8,
        "janitorial": 0.5,
    }
    locs = catalog.locations
    day = start
    while day < catalog.today:
        r = rng_for(seed, "history", day.isoformat())
        for j in range(per_day):
            v = r.choices(vendors, weights=[weights[v.key] for v in vendors])[0]
            it = r.choice(catalog.items_for(v.key))
            loc = r.choices(locs, weights=[x.weight for x in locs])[0]
            if loc.code == "CM" and v.key == "janitorial":
                loc = catalog.location("RS")
            amt = (it.unit_price * r.randint(1, 8)).quantize(Decimal("0.01"))
            yield CodedLine(
                stable_uuid("coded_line", f"{day}:{j}"),
                day,
                v.key,
                v.id,
                loc.code,
                loc.id,
                loc.entity_n,
                it.key,
                _variant(it.description, r),
                it.default_gl,
                f"{amt:f}",
            )
        day += timedelta(days=1)


def prior_short_pays(catalog: Catalog) -> list[dict[str, Any]]:
    """The two accepted Protein Supplier shrimp short-pays at Riverside within the last 90 days.

    Each record has everything the seed needs to create the invoice, PO, GRN, exception and the
    accepted ``short_pay`` approval: amounts are Decimal strings; dates are relative to catalog.today.
    """
    v, loc = catalog.vendor("protein"), catalog.location("RS")
    shrimp = catalog.item("protein", "Shrimp 16/20 IQF 2lb × 10")
    cod = catalog.item("protein", "Cod loin 10lb case")
    out = []
    for sp in PRIOR_SHORT_PAYS:
        day = catalog.today - timedelta(days=sp["days_ago"])
        qty, billed, contract = Decimal(sp["qty"]), Decimal(sp["billed_unit"]), Decimal(sp["contract_unit"])
        shrimp_amt = (qty * billed).quantize(Decimal("0.01"))
        expected = (qty * contract).quantize(Decimal("0.01"))
        delta = shrimp_amt - expected
        assert f"{delta:f}" == sp["delta"], sp
        cod_qty = Decimal(6)
        cod_amt = (cod_qty * cod.unit_price).quantize(Decimal("0.01"))
        total = shrimp_amt + cod_amt
        received = datetime.combine(day, datetime.min.time(), tzinfo=TZ) + timedelta(hours=6, minutes=50)
        out.append(
            {
                "invoice_id": stable_uuid("invoice", sp["invoice_number"]),
                "invoice_number": sp["invoice_number"],
                "invoice_date": day.isoformat(),
                "vendor_key": v.key,
                "vendor_id": v.id,
                "location_code": loc.code,
                "location_id": loc.id,
                "entity_n": loc.entity_n,
                "po_number": sp["po"],
                "grn_number": sp["grn"],
                "lines": [
                    {
                        "item_key": shrimp.key,
                        "item_id": shrimp.id,
                        "description": shrimp.description,
                        "qty": sp["qty"],
                        "uom": "lb",
                        "unit_price": sp["billed_unit"],
                        "po_unit_price": sp["contract_unit"],
                        "amount": f"{shrimp_amt:f}",
                        "clause": "4.2",
                    },
                    {
                        "item_key": cod.key,
                        "item_id": cod.id,
                        "description": cod.description,
                        "qty": "6",
                        "uom": "cs",
                        "unit_price": f"{cod.unit_price:f}",
                        "po_unit_price": f"{cod.unit_price:f}",
                        "amount": f"{cod_amt:f}",
                    },
                ],
                "total": f"{total:f}",
                "amount_at_risk": sp["delta"],
                "pay_amount": f"{total - delta:f}",
                "hold_amount": sp["delta"],
                "exception_type": "price_variance",
                "action": "short_pay",
                "accepted": True,
                "received_at": (received + timedelta(hours=3)).isoformat(),
                "decided_at": (received + timedelta(hours=3, minutes=14)).isoformat(),
                "decided_by": "elena",
            }
        )
    return out


def iter_docs(days: Iterable[tuple[date, list[PlannedDoc]]]) -> Iterator[PlannedDoc]:
    for _, docs in days:
        yield from docs
