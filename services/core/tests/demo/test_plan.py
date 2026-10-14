from __future__ import annotations

import json
from collections import Counter
from datetime import time, timedelta
from decimal import Decimal

import pytest

from app.demo.corpus import plan_day

from .conftest import TODAY, spec_doc_confidence


def _dump(docs):
    return json.dumps(
        [{**d.label(), "sim": d.simulated_extraction, "po": d.po, "grn": d.grn} for d in docs],
        sort_keys=True,
        default=str,
    )


def _boxes(sim):
    for k, f in sim.items():
        if isinstance(f, dict) and "bbox" in f:
            yield k, f["bbox"]
    for i, ln in enumerate(sim["lines"]):
        for k, f in ln.items():
            yield f"lines[{i}].{k}", f["bbox"]


def test_plan_is_deterministic(catalog, today_docs):
    again = plan_day(catalog, TODAY)
    assert _dump(today_docs) == _dump(again)
    other_seed = plan_day(catalog, TODAY, seed=1)
    assert _dump(today_docs) != _dump(other_seed)


@pytest.mark.parametrize("offset", range(0, 7))
def test_heroes_every_day(catalog, offset):
    day = TODAY + timedelta(days=offset)
    docs = plan_day(catalog, day)
    heroes = {(d.hero, d.channel): d for d in docs if d.hero}
    assert len(heroes) == 6
    ps = heroes[("PS-88214", "email")]
    assert ps.truth["total"] == "2847.60" and ps.truth["po_reference"] == "PO-RS-1873"
    assert ps.truth["lines"][0]["unit_price"] == "4.12" and ps.po["lines"][0]["unit_price"] == "3.68"
    assert ps.grn["grn_number"] == "GRN-RS-4410"
    assert [g["qty_received"] for g in ps.grn["lines"]] == [ln["qty"] for ln in ps.truth["lines"]]
    assert ps.release_at.timetz().replace(tzinfo=None) == time(9, 41)
    pr = heroes[("PR-2214", "photo")]
    assert pr.truth["total"] == "491.60" and pr.skew_deg == 2.0 and pr.smudged_fields == ("lines[1].qty",)
    assert pr.release_at.time() == time(9, 12, 44)
    bd = heroes[("BD-104882", "email")]
    assert bd.truth["total"] == "1982.47" and len(bd.truth["lines"]) == 14 and bd.pages == 2
    assert bd.release_at.time() == time(9, 41, 7)
    nv = heroes[("NV-0001", "email")]
    assert nv.truth["total"] == "2214.85" and nv.po is None and nv.truth["po_reference"] is None
    unl = catalog.vendor("unlisted")
    assert nv.truth["bank_details"] == {"routing": unl.bank_routing, "account": unl.bank_account}
    e, p = heroes[("PR-2201", "email")], heroes[("PR-2201", "photo")]
    assert e.truth == p.truth and e.truth["total"] == "612.40"
    assert e.truth["invoice_date"] == (day - timedelta(days=1)).isoformat()
    assert (e.release_at.time(), p.release_at.time()) == (time(8, 2), time(16, 44))
    assert p.duplicate_of == e.key and p.po is None and e.po is not None


def test_hero_confidences(today_docs):
    by = {(d.hero, d.channel): d for d in today_docs if d.hero}
    pr = by[("PR-2214", "photo")].simulated_extraction
    assert pr["lines"][1]["qty"]["confidence"] == 0.71
    assert round(spec_doc_confidence(pr), 2) == 0.88
    low = [
        k
        for k, w in [(f"lines[{i}].{k}", ln[k]) for i, ln in enumerate(pr["lines"]) for k in ln]
        if w["value"] is not None and w["confidence"] < 0.75
    ]
    assert low == ["lines[1].qty"]
    assert all(
        pr[k]["confidence"] >= 0.75 for k in pr if isinstance(pr[k], dict) and pr[k]["value"] is not None
    )
    for key, ch, target in [
        ("BD-104882", "email", 0.97),
        ("PS-88214", "email", 0.98),
        ("PR-2201", "email", 0.98),
        ("PR-2201", "photo", 0.91),
    ]:
        assert round(spec_doc_confidence(by[(key, ch)].simulated_extraction), 2) == target, key


def test_rates_over_30_days(month_docs):
    n = len(month_docs)
    assert n == 30 * 180
    cond = Counter(d.condition for d in month_docs)
    ch = Counter(d.channel for d in month_docs)
    rate = lambda c: cond[c] / n  # noqa: E731
    assert 0.09 <= rate("price_variance") <= 0.13
    assert 0.03 <= rate("qty_short") <= 0.055
    assert 0.03 <= rate("no_po") <= 0.055
    assert 0.006 <= rate("duplicate") <= 0.016
    assert 0.003 <= rate("fraud") <= 0.014  # includes the daily NV-0001 hero
    smudge = sum(1 for d in month_docs if d.smudged_fields) / n
    assert 0.015 <= smudge <= 0.04
    for c, target in [("email", 0.59), ("photo", 0.18), ("portal", 0.14), ("edi", 0.10)]:
        assert abs(ch[c] / n - target) < 0.03, (c, ch[c] / n)


def test_release_window_and_peak(month_docs):
    hours = []
    for d in month_docs:
        assert d.release_at.tzinfo is not None and str(d.release_at.tzinfo) == "America/New_York"
        t = d.release_at.time()
        assert time(5, 30) <= t <= time(21, 0)
        hours.append(t.hour)
    morning = sum(1 for h in hours if 7 <= h < 11) / len(hours)
    evening = sum(1 for h in hours if 17 <= h < 21) / len(hours)
    assert morning > 2.5 * evening


def test_documents_are_internally_consistent(month_docs, catalog):
    for d in month_docs:
        t = d.truth
        lines_sum = sum(Decimal(ln["amount"]) for ln in t["lines"])
        for ln in t["lines"]:
            assert abs(Decimal(ln["qty"]) * Decimal(ln["unit_price"]) - Decimal(ln["amount"])) <= Decimal(
                "0.01"
            )
        assert Decimal(t["subtotal"]) == lines_sum
        assert lines_sum + Decimal(t["tax"]) + Decimal(t["freight"] or 0) == Decimal(t["total"])
        assert len(d.line_items) == len(t["lines"])
        if d.channel == "edi":
            assert all(f[2] == 1.0 for f in _weighted(d.simulated_extraction))
        for _, b in _boxes(d.simulated_extraction):
            if b is not None:
                assert 0 <= b["x"] <= 1 and 0 <= b["y"] <= 1 and b["x"] + b["w"] <= 1.0001
                assert b["y"] + b["h"] <= 1.0001 and b["w"] > 0 and b["h"] > 0
        if d.condition == "duplicate":
            assert d.duplicate_of and d.po is None
            continue
        if d.condition in ("no_po", "fraud"):
            assert d.po is None and t["po_reference"] is None
            continue
        assert d.po and d.po["po_number"] == t["po_reference"]
        po_lines = d.po["lines"]
        if d.condition == "price_variance" and not d.hero:
            k = d.expected["line"]
            exp = Decimal(po_lines[k]["unit_price"]) * Decimal(t["lines"][k]["qty"])
            delta = Decimal(t["lines"][k]["amount"]) - exp.quantize(Decimal("0.01"))
            assert delta > min(Decimal("0.02") * exp, Decimal("25.00"))
        if d.condition == "qty_short":
            k = d.expected["line"]
            assert Decimal(d.grn["lines"][k]["qty_received"]) < Decimal(t["lines"][k]["qty"])
        if d.condition == "clean" and not d.hero:
            assert [pl["unit_price"] for pl in po_lines] == [ln["unit_price"] for ln in t["lines"]]
            if d.grn:
                assert [g["qty_received"] for g in d.grn["lines"]] == [ln["qty"] for ln in t["lines"]]
        if catalog.vendor(d.vendor_key).match_mode == "two_way":
            assert d.grn is None


def _weighted(sim):
    from app.demo.corpus.confidence import weighted_fields

    return weighted_fields(sim)


def test_smudged_fields_are_low_confidence(month_docs):
    seen = 0
    for d in month_docs:
        for path in d.smudged_fields:
            seen += 1
            sim = d.simulated_extraction
            if path.startswith("lines["):
                i = int(path[6 : path.index("]")])
                c = sim["lines"][i][path.split(".")[1]]["confidence"]
            else:
                c = sim[path]["confidence"]
            assert 0.60 <= c <= 0.74
            assert d.channel == "photo"
    assert seen > 50


def test_no_heroes_option(catalog):
    docs = plan_day(catalog, TODAY, n=50, include_heroes=False)
    assert len(docs) == 50 and not any(d.hero for d in docs)
    numbers = Counter((d.vendor_key, d.truth["invoice_number"]) for d in docs if d.condition != "duplicate")
    assert max(numbers.values()) == 1
