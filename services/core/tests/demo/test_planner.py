from __future__ import annotations

import random
import statistics
from datetime import datetime, timedelta
from decimal import Decimal

from app.demo.corpus.invoices import TZ
from app.demo.planner import (
    backfill_days,
    due_docs,
    historical_coded_lines,
    is_hero_exception,
    prior_short_pays,
    should_auto_resolve,
    simulated_decision,
)

from .conftest import TODAY


def test_due_docs_windows(today_docs):
    t0 = datetime(2026, 10, 14, 9, 0, tzinfo=TZ)
    t1 = t0 + timedelta(minutes=45)
    first = due_docs(today_docs, t0)
    window = due_docs(today_docs, t1, since=t0)
    assert all(d.release_at <= t0 for d in first)
    assert all(t0 < d.release_at <= t1 for d in window)
    assert {d.hero for d in window} >= {"PR-2214", "PS-88214", "BD-104882"}
    assert "NV-0001" in {d.hero for d in first}
    assert len(first) + len(window) == len(due_docs(today_docs, t1))
    everything = due_docs(today_docs, datetime(2026, 10, 14, 23, 59, tzinfo=TZ))
    assert len(everything) == len(today_docs)


def test_simulated_decision_rules():
    rng = random.Random(1)
    assert simulated_decision({"type": "price_variance", "invoice_number": "PS-88214"}, rng) is None
    assert simulated_decision({"type": "duplicate", "invoice_number": "PR 2201"}, rng) is None
    assert simulated_decision({"type": "new_vendor_screen", "invoice_number": "EQ-1"}, rng) is None
    assert simulated_decision({"type": "no_po", "amount_at_risk": "7200.00"}, rng) is None
    delay, act = simulated_decision(
        {
            "type": "price_variance",
            "invoice_number": "PS-100123",
            "recommendation": {
                "action": "short_pay",
                "pay_amount": "10.00",
                "hold_amount": "2.00",
                "confidence": 0.8,
            },
        },
        rng,
    )
    assert act["action"] == "short_pay" and act["pay_amount"] == "10.00" and delay > timedelta(0)
    assert simulated_decision({"type": "duplicate"}, rng)[1]["action"] == "reject_copy"
    assert simulated_decision({"type": "no_po"}, rng)[1]["action"] == "approve_without_po"
    assert simulated_decision({"type": "extraction_review"}, rng)[1]["action"] == "confirm_fields"
    assert is_hero_exception({"hero": True})


def test_decision_delay_is_lognormal_around_9_minutes():
    rng = random.Random(5)
    mins = [simulated_decision({"type": "duplicate"}, rng)[0].total_seconds() / 60 for _ in range(4000)]
    assert 8.0 <= statistics.median(mins) <= 10.0
    assert statistics.mean(mins) > statistics.median(mins)  # right-skewed


def test_auto_resolve():
    now = datetime(2026, 10, 14, 3, 0, tzinfo=TZ)
    old = {"type": "no_po", "created_at": (now - timedelta(days=4)).isoformat(), "invoice_number": "EQ-5"}
    assert should_auto_resolve(old, now)
    assert not should_auto_resolve({**old, "invoice_number": "NV-0001"}, now)
    assert not should_auto_resolve({**old, "created_at": now - timedelta(days=1)}, now)


def test_backfill(catalog):
    days = list(backfill_days(catalog, 3, n=40))
    assert [d for d, _ in days] == [TODAY - timedelta(days=k) for k in (3, 2, 1)]
    for _, docs in days:
        assert len(docs) == 40 and not any(d.hero for d in docs)


def test_historical_coded_lines(catalog):
    lines = list(historical_coded_lines(catalog, months=6, per_day=20))
    assert 3500 <= len(lines) <= 3700
    assert min(ln.date for ln in lines) >= TODAY - timedelta(days=190)
    assert max(ln.date for ln in lines) < TODAY
    gls = {g.number for g in catalog.gl_accounts}
    assert all(ln.gl_account in gls for ln in lines)
    assert {ln.gl_account for ln in lines} >= {"5000", "5010", "6100", "6200"}
    assert lines == list(historical_coded_lines(catalog, months=6, per_day=20))


def test_prior_short_pays(catalog):
    sp = prior_short_pays(catalog)
    assert [s["amount_at_risk"] for s in sp] == ["61.60", "47.20"]
    for s in sp:
        assert s["vendor_key"] == "protein" and s["accepted"] and s["action"] == "short_pay"
        days = (TODAY - datetime.fromisoformat(s["decided_at"]).date()).days
        assert 0 < days <= 90
        assert Decimal(s["pay_amount"]) + Decimal(s["hold_amount"]) == Decimal(s["total"])
