"""The five hero cases (13-demo-data §4), authored to match contracts/fixtures.json exactly.

Constants are embedded (the Railway image does not ship ``contracts/``); a test asserts they equal
fixtures.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

HERO_KEYS = ("BD-104882", "PS-88214", "PR-2214", "PR-2201", "NV-0001")

Line = tuple[str, str, str, str, str]  # description, qty, uom, unit_price, amount


@dataclass(frozen=True)
class HeroCopy:
    channel: str
    release: time
    file_name: str
    doc_confidence: float | None  # target; None = authored per-field values (PR-2214)
    skew_deg: float | None = None


@dataclass(frozen=True)
class HeroSpec:
    key: str
    vendor: str
    location: str
    copies: tuple[HeroCopy, ...]
    lines: tuple[Line, ...]
    total: str
    po: str | None
    grn: str | None
    po_prices: dict[int, str]  # line index -> PO unit price where it differs from the invoice
    invoice_date_offset: int  # days relative to the demo day
    smudged: tuple[str, ...] = ()
    expected: dict | None = None


HEROES: dict[str, HeroSpec] = {
    "PS-88214": HeroSpec(
        key="PS-88214",
        vendor="protein",
        location="RS",
        copies=(HeroCopy("email", time(9, 41, 0), "Invoice_PS-88214.pdf", 0.98),),
        lines=(
            ("Shrimp 16/20 IQF 2lb × 10", "200", "lb", "4.12", "824.00"),
            ("Cod loin 10lb case", "12", "cs", "68.40", "820.80"),
            ("Scallops U-10 dry 2lb", "8", "ea", "54.25", "434.00"),
            ("Crab claw meat 5lb", "6", "ea", "71.90", "431.40"),
            ("Oysters select 1gal", "4", "ea", "84.35", "337.40"),
        ),
        total="2847.60",
        po="PO-RS-1873",
        grn="GRN-RS-4410",
        po_prices={0: "3.68"},
        invoice_date_offset=0,
        expected={
            "verdict": "price_variance",
            "exceptions": ["price_variance"],
            "expected_ext": "736.00",
            "invoice_ext": "824.00",
            "delta": "88.00",
            "allowed": "14.72",
            "delta_pct_display": "+12.0%",
            "pay": "2759.60",
            "hold": "88.00",
            "recommendation": "short_pay",
            "recommendation_confidence": "0.94",
            "clause": "4.2",
        },
    ),
    "PR-2214": HeroSpec(
        key="PR-2214",
        vendor="produce",
        location="RS",
        copies=(HeroCopy("photo", time(9, 12, 44), "IMG_4187.jpg", None, skew_deg=2.0),),
        lines=(
            ("Romaine hearts 24ct", "6", "cs", "18.40", "110.40"),
            ("Heirloom tomato 10lb", "4", "cs", "31.25", "125.00"),
            ("Lemons 115ct case", "3", "cs", "42.80", "128.40"),
            ("Shallots 5lb bag", "4", "ea", "19.90", "79.60"),
            ("Flat-leaf parsley 60ct", "2", "cs", "24.10", "48.20"),
        ),
        total="491.60",
        po="PO-RS-1866",
        grn="GRN-RS-4402",
        po_prices={},
        invoice_date_offset=0,
        smudged=("lines[1].qty",),
        expected={
            "verdict": "clean",
            "exceptions": ["extraction_review"],
            "flagged_field": "lines[1].qty",
            "flagged_confidence": "0.71",
            "doc_confidence": "0.88",
            "skew_deg": "2.0",
        },
    ),
    "PR-2201": HeroSpec(
        key="PR-2201",
        vendor="produce",
        location="RS",
        copies=(
            HeroCopy("email", time(8, 2, 0), "Invoice_PR-2201.pdf", 0.98),
            HeroCopy("photo", time(16, 44, 0), "IMG_4166.jpg", 0.91),
        ),
        lines=(
            ("Romaine hearts 24ct", "8", "cs", "18.40", "147.20"),
            ("Heirloom tomato 10lb", "6", "cs", "31.25", "187.50"),
            ("Lemons 115ct case", "2", "cs", "42.80", "85.60"),
            ("Shallots 5lb bag", "5", "ea", "19.90", "99.50"),
            ("Yellow onions 50lb", "4", "bag", "23.15", "92.60"),
        ),
        total="612.40",
        po="PO-RS-1859",
        grn="GRN-RS-4396",
        po_prices={},
        invoice_date_offset=-1,
        expected={
            "verdict": "clean",
            "exceptions": ["duplicate"],
            "similarity_min": "0.90",
            "held_copy": "photo",
        },
    ),
    "NV-0001": HeroSpec(
        key="NV-0001",
        vendor="unlisted",
        location="CM",
        copies=(HeroCopy("email", time(9, 0, 0), "Invoice_NV-0001.pdf", 0.96),),
        lines=(
            ("Imported saffron threads 1oz", "6", "ea", "147.35", "884.10"),
            ("Truffle oil white 250ml", "12", "ea", "38.65", "463.80"),
            ("Vanilla beans grade A 1/2lb", "5", "ea", "121.47", "607.35"),
            ("Smoked sea salt 1kg", "8", "ea", "32.45", "259.60"),
        ),
        total="2214.85",
        po=None,
        grn=None,
        po_prices={},
        invoice_date_offset=0,
        expected={
            "verdict": "no_po",
            "exceptions": ["new_vendor_screen"],
            "fraud_score": "0.90",
            "signals": ["bank_mismatch_w9", "vendor_age_lt_14d", "no_po", "remit_address_new"],
            "assigned_role": "controller",
        },
    ),
    "BD-104882": HeroSpec(
        key="BD-104882",
        vendor="broadline",
        location="BS",
        copies=(HeroCopy("email", time(9, 41, 7), "Invoice_BD-104882.pdf", 0.97),),
        lines=(
            ("Canola fry oil 35lb jug", "4", "ea", "38.17", "152.68"),
            ("All-purpose flour 50lb", "3", "bag", "21.63", "64.89"),
            ("Granulated sugar 25lb", "2", "bag", "18.94", "37.88"),
            ("Kosher salt 3lb box", "6", "ea", "4.37", "26.22"),
            ("Black peppercorn 18oz", "2", "ea", "16.82", "33.64"),
            ("Tomato paste #10 can", "6", "ea", "7.49", "44.94"),
            ("San Marzano tomato 28oz × 12", "2", "cs", "41.26", "82.52"),
            ("Arborio rice 10lb", "2", "bag", "23.57", "47.14"),
            ("Penne rigate 20lb", "3", "cs", "27.83", "83.49"),
            ("Extra virgin olive oil 3L", "4", "ea", "29.61", "118.44"),
            ("Chicken stock base 1lb", "3", "ea", "14.29", "42.87"),
            ("Unsalted butter 36ct 1lb", "2", "cs", "118.46", "236.92"),
            ("Heavy cream 36% 1/2gal × 6", "3", "cs", "46.38", "139.14"),
            ("Ground chuck 80/20 10lb chub", "10", "cs", "87.17", "871.70"),
        ),
        total="1982.47",
        po="PO-BS-2041",
        grn="GRN-BS-5518",
        po_prices={},
        invoice_date_offset=0,
        expected={
            "verdict": "clean",
            "exceptions": [],
            "touchless": True,
            "erp": "quickbooks",
            "gl": "5000 COGS-Food",
            "pages": 2,
        },
    ),
}

# PR-2214 authored per-field confidences (dock photo, slightly soft). With the spec weights
# (01 §4.3) these give a weighted geometric mean of 0.8797 -> 0.88; only lines[1].qty is < 0.75.
PR2214_CONFIDENCES = {
    "vendor_name": 0.94,
    "invoice_number": 0.90,
    "invoice_date": 0.86,
    "due_date": 0.88,
    "terms": 0.83,
    "po_reference": 0.85,
    "subtotal": 0.90,
    "tax": 0.89,
    "freight": 0.89,
    "total": 0.91,
    "currency": 0.93,
    "remit_to": 0.87,
    "bank_details": 0.0,
    "lines": [
        {"description": 0.95, "qty": 0.90, "uom": 0.92, "unit_price": 0.91, "amount": 0.92},
        {"description": 0.93, "qty": 0.71, "uom": 0.88, "unit_price": 0.80, "amount": 0.86},
        {"description": 0.94, "qty": 0.88, "uom": 0.91, "unit_price": 0.89, "amount": 0.90},
        {"description": 0.95, "qty": 0.91, "uom": 0.90, "unit_price": 0.87, "amount": 0.90},
        {"description": 0.92, "qty": 0.85, "uom": 0.89, "unit_price": 0.87, "amount": 0.88},
    ],
}

# Two prior accepted shrimp short-pays by the Protein Supplier (drive recommendation confidence 0.94).
PRIOR_SHORT_PAYS = (
    {
        "days_ago": 12,
        "invoice_number": "PS-87731",
        "qty": "140",
        "billed_unit": "4.12",
        "contract_unit": "3.68",
        "delta": "61.60",
        "po": "PO-RS-1790",
        "grn": "GRN-RS-4291",
    },
    {
        "days_ago": 5,
        "invoice_number": "PS-88019",
        "qty": "80",
        "billed_unit": "4.27",
        "contract_unit": "3.68",
        "delta": "47.20",
        "po": "PO-RS-1838",
        "grn": "GRN-RS-4367",
    },
)
