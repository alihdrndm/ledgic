"""End-to-end hero assertions over the pure domain layer (no DB): every number the demo shows."""

from datetime import date
from decimal import Decimal

from app.domain import (
    DupInvoice,
    FraudInputs,
    LineAmounts,
    MatchLineInput,
    Neighbour,
    PairLine,
    VendorRecord,
    duplicate_score,
    evaluate_gate,
    fmt_money,
    fraud_screen,
    match_invoice,
    pair_lines,
    predict_gl,
    resolve_vendor,
)

# BD-104882: Broadline Distributor, 14 lines, total $1,982.47 — the touchless reference invoice.
BD_LINES = [
    ("Chicken breast 4oz IQF", "4", "48.75", "cs"),
    ("Ground beef 80/20 10lb", "3", "52.40", "cs"),
    ("Russet potatoes 50lb", "2", "24.15", "cs"),
    ("Yellow onions 50lb", "2", "21.60", "cs"),
    ("Canola oil 35lb", "3", "38.90", "ea"),
    ("All-purpose flour 50lb", "2", "19.85", "ea"),
    ("Granulated sugar 25lb", "2", "17.30", "ea"),
    ("Heavy cream 1/2gal", "12", "6.45", "ea"),
    ("Unsalted butter 36ct", "2", "88.20", "cs"),
    ("Large eggs 15dz", "3", "41.10", "cs"),
    ("Parmesan grated 5lb", "2", "36.80", "ea"),
    ("Tomato paste #10 can", "6", "7.95", "ea"),
    ("Paper towels 12 roll", "4", "29.40", "cs"),
]


def bd_lines() -> list[tuple[str, Decimal, Decimal, Decimal, str]]:
    rows = [(d, Decimal(q), Decimal(u), Decimal(q) * Decimal(u), uom) for d, q, u, uom in BD_LINES]
    remainder = Decimal("1982.47") - sum(r[3] for r in rows)
    rows.append(("Dish detergent 5gal", Decimal(1), remainder, remainder, "ea"))
    return rows


def test_bd104882_clean_14_line_invoice_is_touchless(heroes: dict) -> None:
    hero = heroes["BD-104882"]
    rows = bd_lines()
    assert len(rows) == hero["line_count"] == 14
    assert rows[-1][2] > 0
    assert sum(r[3] for r in rows) == Decimal(hero["total"])

    # 1. Extraction gate: every field at 0.97, arithmetic consistent.
    fields: dict[str, str] = {
        k: hero["expected"]["extraction_conf"]
        for k in ("vendor", "invoice_number", "invoice_date", "total", "po_ref", "terms")
    }
    for i in range(len(rows)):
        for part in ("qty", "unit_price", "amount"):
            fields[f"lines[{i}].{part}"] = "0.97"
    gate = evaluate_gate(fields, lines=[LineAmounts(r[1], r[2], r[3]) for r in rows], total=hero["total"])
    assert gate.passes and gate.doc_confidence == Decimal("0.970")

    # 2. Enrichment: vendor resolves, lines pair to the (shuffled) PO, GL predicted.
    vendor = resolve_vendor("BROADLINE DISTRIBUTOR INC", [VendorRecord("v-bd", "Broadline Distributor")])
    assert vendor.vendor_id == "v-bd"
    po = [PairLine(r[0], r[4]) for r in rows][::-1]
    pairing = pair_lines([PairLine(r[0].upper(), r[4]) for r in rows], po)
    assert len(pairing.pairs) == 14 and pairing.unmatched_invoice == ()
    gl = predict_gl([Neighbour(hero["expected"]["gl"], Decimal("0.93"))] * 7)
    assert gl.gl_code == "5000 COGS-Food"

    # 3. Screening: no duplicate (no prior invoice), no fraud signal.
    fraud = fraud_screen(
        FraudInputs(
            Decimal(hero["total"]),
            700,
            True,
            "fp",
            "fp",
            False,
            tuple(Decimal(x) for x in ("1900", "2050", "1980", "2010", "1940")),
        )
    )
    assert fraud.score == 0 and not fraud.hold

    # 4. Match: every line within tolerance, qty ≤ received.
    lines = []
    for p in pairing.pairs:
        d, q, u, a, uom = rows[p.invoice_index]
        lines.append(
            MatchLineInput(p.invoice_index + 1, d, q, u, a, uom=uom, po_unit_price=u, po_qty=q, grn_qty=q)
        )
    m = match_invoice(lines, invoice_date=date(2026, 7, 13))
    assert m.verdict == hero["expected"]["verdict"] == "clean"
    assert m.verified_text == "14 of 14 lines auto-verified"
    touchless = gate.passes and m.is_clean and not fraud.hold
    assert touchless is hero["expected"]["touchless"]


def test_hero_display_strings(heroes: dict) -> None:
    exp = heroes["PS-88214"]["expected"]
    assert fmt_money(exp["pay"]) == "$2,759.60"
    assert fmt_money(exp["hold"], sign=True) == "+$88.00"


def test_pr2201_score_object_is_hashable_and_hard(heroes: dict) -> None:
    a = DupInvoice("v", "PR-2201", Decimal("612.40"), date(2026, 7, 12))
    s = duplicate_score(a, a)
    assert s.hard and hash(s) is not None
