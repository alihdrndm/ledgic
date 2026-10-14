from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.demo.corpus import HEROES, build_catalog
from app.demo.corpus.catalog import ORG_ID

from .conftest import TODAY

FIXTURES = Path(__file__).resolve().parents[4] / "contracts" / "fixtures.json"


def test_master_data_shape(catalog):
    assert len(catalog.entities) == 3
    assert catalog.entity(3).erp == "netsuite"
    codes = [loc.code for loc in catalog.locations]
    assert len(codes) == 34 and len(set(codes)) == 34
    assert all(len(c) == 2 and c.isupper() for c in codes)
    for code, name in [
        ("RS", "Riverside"),
        ("BS", "Bayside"),
        ("CM", "Commissary"),
        ("LS", "Lakeshore"),
        ("OM", "Old Mill"),
        ("PH", "Pierhead"),
        ("SB", "Saltbox"),
        ("CS", "Canal Street"),
    ]:
        assert catalog.location(code).name == name
    assert catalog.location("CM").entity_n == 3
    assert {v.display_name for v in catalog.vendors} == {
        "Broadline Distributor",
        "Protein Supplier",
        "Produce Supplier",
        "Janitorial Services",
        "Equipment Supplier",
        "Beverage Distributor",
        "Dairy Supplier",
        "Bakery Supplier",
        "Paper Goods Supplier",
        "Unlisted Supplier",
    }
    assert catalog.vendor("janitorial").match_mode == "two_way"
    assert 170 <= len(catalog.items) <= 200
    assert len({i.key for i in catalog.items}) == len(catalog.items)
    assert all(i.unit_price % 1 != 0 for i in catalog.items), "prices are never round"
    assert {g.number for g in catalog.gl_accounts} >= {"5000", "5010", "6100", "6200", "2000"}
    assert catalog.org["id"] == ORG_ID


def test_unlisted_supplier_is_the_fraud_case(catalog):
    u = catalog.vendor("unlisted")
    assert u.created_on == TODAY - timedelta(days=4)
    assert u.bank_fingerprint != u.w9_bank_fingerprint
    for v in catalog.vendors:
        if v.key != "unlisted":
            assert v.bank_fingerprint == v.w9_bank_fingerprint


def test_contracts(catalog):
    protein = next(c for c in catalog.contracts if c.vendor_key == "protein")
    assert protein.title == "Vendor agreement 2026"
    assert protein.effective_from == date(2026, 3, 1) and protein.countersigned_at == date(2026, 3, 3)
    assert protein.effective_to == date(2027, 3, 31)  # rolling, DECISIONS D8
    shrimp = catalog.item("protein", "Shrimp 16/20 IQF 2lb × 10")
    c, p = catalog.contract_price(shrimp.key, TODAY)
    assert (p.unit_price, p.uom, p.clause_ref) == (Decimal("3.68"), "lb", "4.2")
    for vkey in ("broadline", "produce"):
        con = next(c for c in catalog.contracts if c.vendor_key == vkey)
        share = len(con.prices) / len(catalog.items_for(vkey))
        assert 0.45 <= share <= 0.75, (vkey, share)
    assert not [c for c in catalog.contracts if c.vendor_key in catalog.riverside_new_suppliers]
    later = build_catalog(date(2027, 6, 2))
    assert next(c for c in later.contracts if c.vendor_key == "protein").effective_to == date(2027, 11, 30)


def test_catalog_deterministic():
    a, b = build_catalog(TODAY), build_catalog(TODAY)
    assert [asdict(v) for v in a.vendors] == [asdict(v) for v in b.vendors]
    assert [asdict(i) for i in a.items] == [asdict(i) for i in b.items]
    assert [asdict(c) for c in a.contracts] == [asdict(c) for c in b.contracts]


@pytest.mark.skipif(not FIXTURES.exists(), reason="contracts/fixtures.json not present")
def test_heroes_match_fixtures():
    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))["heroes"]
    for key, spec in HEROES.items():
        f = fx[key]
        assert spec.total == f["total"], key
        assert spec.location == f["location"]
        if "lines" in f:
            assert [(d, q, u, p, a) for d, q, u, p, a in spec.lines] == [
                (ln["description"], ln["qty"], ln["uom"], ln["unit_price"], ln["amount"]) for ln in f["lines"]
            ]
        if "line_count" in f:
            assert len(spec.lines) == f["line_count"]
        if "po" in f:
            assert spec.po == f["po"]
        if "grn" in f:
            assert spec.grn == f["grn"]
        if "release_time" in f:
            assert spec.copies[0].release.isoformat() == f["release_time"]
        if "copies" in f:
            assert [(c.channel, c.release.isoformat()) for c in spec.copies] == [
                (c["channel"], c["release_time"]) for c in f["copies"]
            ]
        assert sum(Decimal(a) for *_, a in spec.lines) == Decimal(spec.total)
