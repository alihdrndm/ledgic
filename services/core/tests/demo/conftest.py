from __future__ import annotations

import math
from datetime import date

import pytest

from app.demo.corpus import build_catalog, plan_day

TODAY = date(2026, 10, 14)


def spec_doc_confidence(sim: dict) -> float:
    """01 §4.3 weighted geometric mean (local copy; the domain package owns the real gate)."""
    header = {
        "vendor_name": 3,
        "invoice_number": 3,
        "invoice_date": 2,
        "total": 3,
        "po_reference": 2,
        "terms": 1,
    }
    num = den = 0.0
    for k, w in header.items():
        if sim[k]["value"] is not None:
            num += w * math.log(sim[k]["confidence"])
            den += w
    for ln in sim["lines"]:
        for k in ("qty", "unit_price", "amount"):
            if ln[k]["value"] is not None:
                num += math.log(ln[k]["confidence"])
                den += 1
    return math.exp(num / den)


@pytest.fixture(scope="session")
def catalog():
    return build_catalog(TODAY)


@pytest.fixture(scope="session")
def today_docs(catalog):
    return plan_day(catalog, TODAY)


@pytest.fixture(scope="session")
def month_docs(catalog):
    from datetime import timedelta

    out = []
    for k in range(30):
        out.extend(plan_day(catalog, TODAY - timedelta(days=k)))
    return out
