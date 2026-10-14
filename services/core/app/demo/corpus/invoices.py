"""Plan one demo day: POs/GRNs + invoice documents with injected conditions and heroes.

``plan_day`` is pure and cheap (no rendering): it lays every document out (layout.py) so
``simulated_extraction`` carries bboxes that match what ``PlannedDoc.render()`` later draws.

Injected condition rates (per base invoice, 13-demo-data §3): price variance ~11%, short delivery
~4%, no PO ~4%, fraud screen ~0.5%; ~1% of documents are a second copy of an invoice via another
channel; ~14% of dock photos carry a smudged field (~2.5% of all documents).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .catalog import TIMEZONE, Catalog, Item, Location, Vendor
from .confidence import fit_doc_confidence
from .heroes import HEROES, PR2214_CONFIDENCES, HeroSpec
from .layout import build_layout
from .photo import map_bbox, photo_params
from .rng import SEED, derive_seed, rng_for, stable_uuid

TZ = ZoneInfo(TIMEZONE)
CENT = Decimal("0.01")
TAX_RATE = Decimal("0.08875")
DAY_EPOCH = date(2025, 1, 1)

CHANNEL_MIX = (("email", 0.59), ("photo", 0.18), ("portal", 0.14), ("edi", 0.10))
RATES = {"fraud": 0.005, "no_po": 0.04, "price_variance": 0.11, "qty_short": 0.04}
DUPLICATE_RATE = 0.01
PHOTO_SMUDGE_RATE = 0.14

HEADER_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "terms",
    "po_reference",
    "subtotal",
    "tax",
    "freight",
    "total",
    "currency",
    "remit_to",
    "bank_details",
)
LINE_FIELDS = ("description", "qty", "uom", "unit_price", "amount")

VENDOR_WEIGHT = {
    "produce": 5.0,
    "broadline": 4.0,
    "protein": 3.0,
    "bakery": 2.0,
    "dairy": 2.0,
    "beverage": 1.5,
    "paper": 1.2,
    "equipment": 0.8,
    "janitorial": 0.4,
}
CHANNEL_VENDORS = {
    "email": (
        "produce",
        "broadline",
        "protein",
        "bakery",
        "dairy",
        "beverage",
        "paper",
        "equipment",
        "janitorial",
    ),
    "photo": ("produce", "protein", "dairy", "bakery", "broadline"),
    "portal": ("broadline", "beverage", "paper", "dairy", "janitorial", "equipment"),
    "edi": ("broadline", "beverage", "dairy"),
}
EDI_WEIGHT = {"broadline": 6.0, "beverage": 2.5, "dairy": 1.5}
LINE_COUNT = {
    "produce": (3, 9),
    "protein": (2, 6),
    "broadline": (5, 16),
    "dairy": (3, 8),
    "bakery": (2, 6),
    "beverage": (3, 10),
    "paper": (2, 7),
    "janitorial": (1, 3),
    "equipment": (1, 4),
    "unlisted": (2, 4),
}
INVOICE_BASE = {
    "broadline": 300000,
    "protein": 100000,
    "produce": 10000,
    "janitorial": 5000,
    "equipment": 20000,
    "beverage": 40000,
    "dairy": 60000,
    "bakery": 70000,
    "paper": 80000,
    "unlisted": 1000,
}
FRAUD_VENDORS = ("equipment", "paper", "beverage", "janitorial")


@dataclass(frozen=True)
class RenderedDoc:
    content: bytes
    mime: str
    filename: str
    pages: int
    sha256: str
    bboxes: dict[str, dict[str, Any]]
    skew_deg: float | None

    def phash(self) -> str:
        from .photo import phash_hex

        return phash_hex(self.content, self.mime)


@dataclass
class PlannedDoc:
    """One document to release into a channel. ``truth`` is the 06 §5.1 schema without confidences;
    ``simulated_extraction`` is the same schema with {value, confidence, bbox} per field."""

    key: str
    document_id: str
    day: date
    release_at: datetime
    channel: str  # email | photo | portal | edi
    vendor_key: str
    vendor_id: str
    location_code: str
    location_id: str
    entity_n: int
    hero: str | None
    condition: str  # clean | price_variance | qty_short | no_po | duplicate | fraud
    conditions: tuple[str, ...]  # condition plus "smudge" when a field is smudged
    truth: dict[str, Any]
    po: dict[str, Any] | None  # persist before release; None on a duplicate copy (see duplicate_of)
    grn: dict[str, Any] | None
    line_items: list[dict[str, Any]]  # parallel to truth["lines"]: item_key, item_id, sku, gl
    simulated_extraction: dict[str, Any]
    expected: dict[str, Any]
    file_name: str
    mime: str
    template: str
    pages: int
    render_ctx: dict[str, Any] = field(repr=False)
    duplicate_of: str | None = None
    smudged_fields: tuple[str, ...] = ()
    skew_deg: float | None = None
    photo_seed: int | None = None

    @property
    def extraction_mode(self) -> str:
        return "simulated"

    def render(self) -> RenderedDoc:
        from .render import render_pdf
        from .rng import sha256_hex

        pdf = render_pdf(self.truth, self.render_ctx)
        if self.channel != "photo":
            return RenderedDoc(
                pdf.content,
                "application/pdf",
                self.file_name,
                pdf.pages,
                sha256_hex(pdf.content),
                pdf.bboxes,
                None,
            )
        from .photo import render_photo

        params = photo_params(self.photo_seed or 0, self.skew_deg)
        smudges = [pdf.bboxes[f] for f in self.smudged_fields if f in pdf.bboxes]
        jpeg = render_photo(pdf.content, params, smudges, pdf.layout.anchors.get("signature"))
        boxes = {k: map_bbox(b, params) for k, b in pdf.bboxes.items() if b["page"] == 1}
        return RenderedDoc(jpeg, "image/jpeg", self.file_name, 1, sha256_hex(jpeg), boxes, params.skew_deg)

    def label(self, sha256: str | None = None) -> dict[str, Any]:
        return {
            "sha256": sha256,
            "doc_key": self.key,
            "document_id": self.document_id,
            "file": self.file_name,
            "channel": self.channel,
            "hero": self.hero,
            "condition": self.condition,
            "conditions": list(self.conditions),
            "vendor": self.vendor_key,
            "location": self.location_code,
            "release_at": self.release_at.isoformat(),
            "truth": self.truth,
            "expected": self.expected,
            "smudged_fields": list(self.smudged_fields),
            "skew_deg": self.skew_deg,
            "duplicate_of": self.duplicate_of,
        }


# --------------------------------------------------------------------------------------------- helpers


def _d(v: Any) -> Decimal:
    return Decimal(str(v))


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def _s(v: Decimal) -> str:
    return f"{_q(v):f}"


def _qty_s(v: Decimal) -> str:
    return f"{v.normalize():f}" if v == v.to_integral() else f"{v:f}"


def day_index(day: date) -> int:
    return (day - DAY_EPOCH).days


def _weighted(r: random.Random, pairs: list[tuple[Any, float]]) -> Any:
    total = sum(w for _, w in pairs)
    x = r.random() * total
    for v, w in pairs:
        x -= w
        if x <= 0:
            return v
    return pairs[-1][0]


def _at(day: date, hours: float) -> datetime:
    secs = int(round(hours * 3600))
    return datetime.combine(day, time(0, 0), tzinfo=TZ) + timedelta(seconds=secs)


def _release_hours(r: random.Random, channel: str) -> float:
    if channel == "photo":  # dock deliveries cluster early
        h = r.gauss(8.2, 1.4)
    elif channel == "edi":  # batch drops
        h = r.choice([6.0, 6.0, 12.0, 18.0]) + r.uniform(0.02, 0.4)
    elif channel == "portal":
        h = r.gauss(9.5, 2.0) if r.random() < 0.6 else r.uniform(5.5, 21.0)
    else:
        h = r.gauss(9.0, 1.6) if r.random() < 0.62 else r.uniform(5.5, 21.0)
    return min(20.98, max(5.5, h))


def _qty_for(r: random.Random, item: Item) -> Decimal:
    u = item.uom
    if u == "lb":
        return Decimal(r.choice([40, 60, 80, 100, 120, 140, 160, 200]))
    if u == "svc":
        return Decimal(1)
    if u in ("bag", "bdl"):
        return Decimal(r.randint(1, 6))
    if u == "cs":
        return Decimal(r.choice([1, 1, 2, 2, 2, 3, 3, 4, 4, 5, 6, 8, 10, 12]))
    return Decimal(r.choice([1, 2, 2, 3, 4, 4, 6, 8, 10, 12]))


def location_ctx(loc: Location) -> dict[str, str]:
    street = loc.address.split(",")[0]
    return {
        "sold_to": f"Northside Group — {loc.name}",
        "sold_to_line2": f"Site {loc.site_no} · {street}",
        "sold_to_short": f"{loc.name} ({loc.code})",
    }


def vendor_ctx(v: Vendor) -> dict[str, str]:
    return {"tagline": v.tagline, "address": v.remit_address, "phone": v.phone, "email": v.contact_email}


# --------------------------------------------------------------------------------------------- extraction sim


def _sim_field(value: Any, conf: float, bbox: dict | None) -> dict[str, Any]:
    if value is None:
        return {"value": None, "confidence": 0.0, "bbox": None}
    return {"value": value, "confidence": round(conf, 3), "bbox": bbox}


def simulate_extraction(
    truth: dict[str, Any],
    bboxes: dict[str, dict],
    channel: str,
    r: random.Random,
    smudged: tuple[str, ...] = (),
    authored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if channel == "edi":
        lo, hi = 1.0, 1.0
    elif channel == "photo":
        lo, hi = 0.90, 0.985
    else:
        lo, hi = 0.93, 0.995

    def conf(path: str, auth: float | None) -> float:
        if auth is not None:
            return auth
        if path in smudged:
            return r.uniform(0.60, 0.74)
        return r.uniform(lo, hi)

    sim: dict[str, Any] = {}
    for k in HEADER_FIELDS:
        a = authored.get(k) if authored else None
        sim[k] = _sim_field(truth.get(k), conf(k, a), bboxes.get(k))
    sim["lines"] = []
    for i, ln in enumerate(truth["lines"]):
        row = {}
        for k in LINE_FIELDS:
            path = f"lines[{i}].{k}"
            a = authored["lines"][i][k] if authored else None
            row[k] = _sim_field(ln.get(k), conf(path, a), bboxes.get(path))
        sim["lines"].append(row)
    sim["document_type"] = truth["document_type"]
    sim["multiple_invoices_detected"] = truth["multiple_invoices_detected"]
    return sim


# --------------------------------------------------------------------------------------------- doc assembly


def _truth(
    v: Vendor,
    number: str,
    inv_date: date,
    po_ref: str | None,
    lines: list[dict[str, str]],
    taxable: bool,
    freight: Decimal | None,
    remit: dict[str, str] | None = None,
    bank: dict[str, str] | None = None,
) -> dict[str, Any]:
    subtotal = sum((_d(ln["amount"]) for ln in lines), Decimal(0))
    tax = _q(subtotal * TAX_RATE) if taxable else Decimal(0)
    total = subtotal + tax + (freight or Decimal(0))
    return {
        "vendor_name": v.display_name,
        "invoice_number": number,
        "invoice_date": inv_date.isoformat(),
        "due_date": (inv_date + timedelta(days=v.terms_days)).isoformat(),
        "terms": v.terms,
        "po_reference": po_ref,
        "subtotal": _s(subtotal),
        "tax": _s(tax),
        "freight": _s(freight) if freight is not None else None,
        "total": _s(total),
        "currency": "USD",
        "remit_to": remit or {"name": v.remit_name, "address": v.remit_address},
        "bank_details": bank
        if bank is not None
        else ({"routing": v.bank_routing, "account": v.bank_account} if v.prints_bank else None),
        "lines": lines,
        "document_type": "invoice",
        "multiple_invoices_detected": False,
    }


def _make_doc(
    cat: Catalog,
    *,
    key: str,
    day: date,
    release_at: datetime,
    channel: str,
    v: Vendor,
    loc: Location,
    truth: dict[str, Any],
    po: dict | None,
    grn: dict | None,
    line_items: list[dict[str, Any]],
    condition: str,
    smudged: tuple[str, ...],
    hero: str | None,
    expected: dict[str, Any],
    file_name: str,
    r: random.Random,
    seed: int,
    target_conf: float | None = None,
    authored: dict | None = None,
    skew_deg: float | None = None,
    duplicate_of: str | None = None,
) -> PlannedDoc:
    template = "D" if channel in ("portal", "edi") else v.template
    ctx: dict[str, Any] = {
        "template": template,
        "vendor": vendor_ctx(v),
        **location_ctx(loc),
        "route": f"route {derive_seed(seed, 'route', loc.code, v.key) % 9 + 1}",
        "skus": [li.get("sku") or "" for li in line_items],
        "channel": channel,
    }
    if channel == "edi":
        ctx["portal_note"] = f"EDI 810 rendition · ISA control {derive_seed(seed, key) % 10**9:09d}"
    elif channel == "portal":
        ctx["portal_note"] = "Issued via supplier portal"
    lay = build_layout(truth, ctx)
    boxes = {k: b for k in lay.fields if (b := lay.norm_bbox(k)) is not None}
    photo_seed = None
    if channel == "photo":
        photo_seed = derive_seed(seed, "photo", key)
        params = photo_params(photo_seed, skew_deg)
        skew_deg = params.skew_deg
        boxes = {k: map_bbox(b, params) for k, b in boxes.items() if b["page"] == 1}
    sim = simulate_extraction(truth, boxes, channel, r, smudged, authored)
    if target_conf is not None:
        fit_doc_confidence(sim, target_conf)
    conditions = (condition,) + (("smudge",) if smudged else ())
    mime = "image/jpeg" if channel == "photo" else "application/pdf"
    return PlannedDoc(
        key=key,
        document_id=stable_uuid("document", key),
        day=day,
        release_at=release_at,
        channel=channel,
        vendor_key=v.key,
        vendor_id=v.id,
        location_code=loc.code,
        location_id=loc.id,
        entity_n=loc.entity_n,
        hero=hero,
        condition=condition,
        conditions=conditions,
        truth=truth,
        po=po,
        grn=grn,
        line_items=line_items,
        simulated_extraction=sim,
        expected=expected,
        file_name=file_name,
        mime=mime,
        template=template,
        pages=1 if channel == "photo" else len(lay.pages),
        render_ctx=ctx,
        duplicate_of=duplicate_of,
        smudged_fields=smudged,
        skew_deg=skew_deg if channel == "photo" else None,
        photo_seed=photo_seed,
    )


def _po_dict(
    number: str,
    v: Vendor,
    loc: Location,
    ordered_at: datetime,
    lines: list[tuple[Item | None, str, Decimal, str, Decimal]],
) -> dict[str, Any]:
    out_lines = []
    total = Decimal(0)
    for n, (it, desc, q, uom, unit) in enumerate(lines, start=1):
        amt = _q(q * unit)
        total += amt
        out_lines.append(
            {
                "line_no": n,
                "item_key": it.key if it else None,
                "item_id": it.id if it else None,
                "description": desc,
                "qty": _qty_s(q),
                "uom": uom,
                "unit_price": f"{unit:f}",
                "amount": _s(amt),
            }
        )
    return {
        "id": stable_uuid("po", number),
        "po_number": number,
        "vendor_key": v.key,
        "vendor_id": v.id,
        "location_code": loc.code,
        "location_id": loc.id,
        "entity_n": loc.entity_n,
        "ordered_at": ordered_at.isoformat(),
        "total": _s(total),
        "lines": out_lines,
        "source": "quickbooks",
    }


def _grn_dict(
    number: str, po: dict[str, Any], received_at: datetime, received: list[Decimal], received_by: str
) -> dict[str, Any]:
    return {
        "id": stable_uuid("grn", number),
        "grn_number": number,
        "po_number": po["po_number"],
        "po_id": po["id"],
        "received_at": received_at.isoformat(),
        "received_by": received_by,
        "lines": [
            {"po_line_no": pl["line_no"], "qty_received": _qty_s(q), "uom": pl["uom"]}
            for pl, q in zip(po["lines"], received, strict=True)
        ],
    }


# --------------------------------------------------------------------------------------------- heroes


def hero_docs(cat: Catalog, day: date, seed: int = SEED) -> list[PlannedDoc]:
    docs = []
    for spec in HEROES.values():
        docs.extend(_hero(cat, spec, day, seed))
    return docs


def _hero(cat: Catalog, spec: HeroSpec, day: date, seed: int) -> list[PlannedDoc]:
    v, loc = cat.vendor(spec.vendor), cat.location(spec.location)
    inv_date = day + timedelta(days=spec.invoice_date_offset)
    items = [cat.item(v.key, d) for d, *_ in spec.lines]
    lines = [
        {"description": d, "qty": q, "uom": u, "unit_price": p, "amount": a} for d, q, u, p, a in spec.lines
    ]
    line_items = [{"item_key": it.key, "item_id": it.id, "sku": it.sku, "gl": it.default_gl} for it in items]
    po = grn = None
    if spec.po:
        ordered = _at(inv_date - timedelta(days=2), 14.25)
        po = _po_dict(
            spec.po,
            v,
            loc,
            ordered,
            [
                (it, d, _d(q), u, _d(spec.po_prices.get(i, p)))
                for i, (it, (d, q, u, p, _a)) in enumerate(zip(items, spec.lines, strict=True))
            ],
        )
        if spec.grn:
            grn = _grn_dict(
                spec.grn,
                po,
                _at(inv_date, 6.67),
                [_d(q) for _, q, *_ in spec.lines],
                "Dock · Riverside" if loc.code == "RS" else f"Dock · {loc.name}",
            )
    truth = _truth(v, spec.key, inv_date, spec.po, lines, taxable=False, freight=None)
    assert truth["total"] == spec.total, (spec.key, truth["total"])
    out = []
    for ci, copy in enumerate(spec.copies):
        key = f"{day.isoformat()}:hero:{spec.key}" + (f":{copy.channel}" if len(spec.copies) > 1 else "")
        r = rng_for(seed, "hero", spec.key, copy.channel)
        is_second = ci > 0
        condition = (
            "duplicate"
            if is_second
            else {"PS-88214": "price_variance", "NV-0001": "fraud"}.get(spec.key, "clean")
        )
        smudged = spec.smudged if copy.channel == "photo" else ()
        authored = PR2214_CONFIDENCES if spec.key == "PR-2214" else None
        expected = dict(spec.expected or {})
        if spec.key == "PR-2201":
            expected["exceptions"] = ["duplicate"] if is_second else []
        out.append(
            _make_doc(
                cat,
                key=key,
                day=day,
                release_at=datetime.combine(day, copy.release, tzinfo=TZ),
                channel=copy.channel,
                v=v,
                loc=loc,
                truth=truth,
                po=None if is_second else po,
                grn=None if is_second else grn,
                line_items=line_items,
                condition=condition,
                smudged=smudged,
                hero=spec.key,
                expected=expected,
                file_name=copy.file_name,
                r=r,
                seed=seed,
                target_conf=copy.doc_confidence,
                authored=authored,
                skew_deg=copy.skew_deg,
                duplicate_of=out[0].key if is_second else None,
            )
        )
    return out


# --------------------------------------------------------------------------------------------- generated


def _choose_vendor(cat: Catalog, r: random.Random, day: date, channel: str) -> Vendor:
    pairs = []
    for key in CHANNEL_VENDORS[channel]:
        w = EDI_WEIGHT[key] if channel == "edi" else VENDOR_WEIGHT[key]
        sched = cat.schedule(key)
        if sched.cadence == "monthly_fixed":
            w *= 6.0 if day.day <= 3 else 0.6
        elif sched.weekdays and day.weekday() not in sched.weekdays:
            w *= 0.35
        pairs.append((key, w))
    return cat.vendor(_weighted(r, pairs))


def _choose_location(cat: Catalog, r: random.Random, v: Vendor, day: date) -> Location:
    allowed = {vl.location_code for vl in cat.vendor_locations if vl.vendor_key == v.key and vl.since <= day}
    pairs = [(loc, loc.weight) for loc in cat.locations if loc.code in allowed]
    return _weighted(r, pairs)


def _invoice(cat: Catalog, day: date, i: int, seed: int) -> PlannedDoc:
    r = rng_for(seed, "doc", day.isoformat(), i)
    di = day_index(day)
    channel = _weighted(r, list(CHANNEL_MIX))
    x = r.random()
    condition = "clean"
    acc = 0.0
    for name, rate in RATES.items():
        acc += rate
        if x < acc:
            condition = name
            break
    if condition == "fraud":
        channel = "email"
        v = cat.vendor(r.choice(FRAUD_VENDORS))
    elif condition == "no_po" and r.random() < 0.7:
        v = cat.vendor("equipment")
        channel = channel if channel in ("email", "portal") else "email"
    else:
        v = _choose_vendor(cat, r, day, channel)
    if condition == "qty_short" and v.match_mode == "two_way":
        condition = "price_variance"
    loc = _choose_location(cat, r, v, day)

    lo, hi = LINE_COUNT[v.key]
    if channel == "photo":
        hi = min(hi, 9)
    pool = cat.items_for(v.key)
    if v.key == "janitorial":
        pool = pool[:5] if r.random() < 0.7 else pool
    n_lines = min(len(pool), r.randint(lo, hi))
    items = r.sample(pool, n_lines)
    inv_date = day - timedelta(days=0 if channel == "photo" else r.choice([0, 0, 0, 1, 1, 2]))

    po_qty = [_qty_for(r, it) for it in items]
    expected_unit = []
    for it in items:
        cp = cat.contract_price(it.key, inv_date)
        expected_unit.append(cp[1].unit_price if cp else it.unit_price)
    inv_unit = list(expected_unit)
    received = list(po_qty)
    expected: dict[str, Any] = {"verdict": "clean", "exceptions": []}

    if condition == "price_variance":
        contract_idx = [k for k, it in enumerate(items) if cat.contract_price(it.key, inv_date)]
        k = r.choice(contract_idx) if contract_idx and r.random() < 0.8 else r.randrange(n_lines)
        bumped = _q(expected_unit[k] * (1 + Decimal(str(round(r.uniform(0.04, 0.15), 4)))))
        if bumped <= expected_unit[k]:
            bumped = expected_unit[k] + CENT
        inv_unit[k] = bumped
        expected = {"verdict": "price_variance", "exceptions": ["price_variance"], "line": k}
    elif condition == "qty_short":
        cand = [k for k, q in enumerate(po_qty) if q >= 2] or [0]
        k = r.choice(cand)
        if po_qty[k] < 2:
            po_qty[k] = Decimal(2)
            received[k] = Decimal(2)
        step = Decimal(10) if items[k].uom == "lb" else Decimal(1)
        short = min(po_qty[k] - step, step * r.randint(1, 3))
        received[k] = po_qty[k] - short
        expected = {"verdict": "qty_mismatch", "exceptions": ["qty_mismatch"], "line": k}
    elif condition == "no_po":
        expected = {"verdict": "no_po", "exceptions": ["no_po"]}
    elif condition == "fraud":
        expected = {
            "verdict": "no_po",
            "exceptions": ["new_vendor_screen"],
            "signals": ["bank_mismatch_w9", "no_po", "remit_address_new"],
        }

    lines = [
        {
            "description": it.description,
            "qty": _qty_s(q),
            "uom": it.uom,
            "unit_price": f"{u:.2f}",
            "amount": _s(q * u),
        }
        for it, q, u in zip(items, po_qty, inv_unit, strict=True)
    ]
    line_items = [{"item_key": it.key, "item_id": it.id, "sku": it.sku, "gl": it.default_gl} for it in items]

    po = grn = None
    po_ref = None
    seq = 10000 + di * 450 + i
    if condition not in ("no_po", "fraud"):
        po_ref = f"PO-{loc.code}-{seq}"
        ordered = _at(inv_date - timedelta(days=r.randint(1, 3)), r.uniform(10, 17))
        po = _po_dict(
            po_ref,
            v,
            loc,
            ordered,
            [
                (it, it.description, q, it.uom, u)
                for it, q, u in zip(items, po_qty, expected_unit, strict=True)
            ],
        )
        if v.match_mode == "three_way":
            grn = _grn_dict(
                f"GRN-{loc.code}-{seq}",
                po,
                _at(inv_date, r.uniform(5.6, 11.0)),
                received,
                f"Dock · {loc.name}",
            )
    freight = (
        _q(Decimal(str(round(r.uniform(18.5, 64.9), 2))))
        if v.key == "equipment" and r.random() < 0.4
        else None
    )
    remit = bank = None
    if condition == "fraud":
        remit = {"name": v.display_name, "address": f"PO Box {r.randint(1000, 9899)}, Dover, DE 19901"}
        routing = f"0{r.randint(11000000, 39999999)}"
        bank = {"routing": routing, "account": str(r.randint(10**9, 10**11))}
    number = f"{v.invoice_prefix}{INVOICE_BASE[v.key] + di * 500 + i}"
    truth = _truth(v, number, inv_date, po_ref, lines, v.taxable, freight, remit, bank)

    smudged: tuple[str, ...] = ()
    if channel == "photo" and r.random() < PHOTO_SMUDGE_RATE:
        k = r.randrange(n_lines)
        smudged = (
            _weighted(
                r,
                [
                    (f"lines[{k}].qty", 0.55),
                    (f"lines[{k}].unit_price", 0.2),
                    (f"lines[{k}].amount", 0.15),
                    ("total", 0.1),
                ],
            ),
        )
        expected = {**expected, "exceptions": ["extraction_review", *expected["exceptions"]]}

    key = f"{day.isoformat()}:{i:03d}"
    if channel == "photo":
        fname = f"IMG_{1000 + derive_seed(seed, 'img', key) % 8999}.jpg"
    elif channel == "edi":
        fname = f"EDI810_{number}.pdf"
    elif channel == "portal":
        fname = f"{v.display_name.replace(' ', '')}_{number}.pdf"
    else:
        fname = f"Invoice_{number}.pdf"
    release = _at(day, _release_hours(r, channel))
    return _make_doc(
        cat,
        key=key,
        day=day,
        release_at=release,
        channel=channel,
        v=v,
        loc=loc,
        truth=truth,
        po=po,
        grn=grn,
        line_items=line_items,
        condition=condition,
        smudged=smudged,
        hero=None,
        expected=expected,
        file_name=fname,
        r=r,
        seed=seed,
    )


def _duplicate(cat: Catalog, orig: PlannedDoc, seed: int) -> PlannedDoc:
    r = rng_for(seed, "dup", orig.key)
    options = {"email": ("photo", "portal"), "photo": ("email",), "portal": ("email",), "edi": ("email",)}
    channel = r.choice(options[orig.channel])
    if channel == "photo" and len(orig.truth["lines"]) > 9:
        channel = "portal"
    v, loc = cat.vendor(orig.vendor_key), cat.location(orig.location_code)
    hours = orig.release_at.hour + orig.release_at.minute / 60 + r.uniform(1.5, 8.0)
    release = _at(orig.day, min(20.98, hours))
    key = f"{orig.key}:dup"
    number = orig.truth["invoice_number"]
    fname = (
        f"IMG_{1000 + derive_seed(seed, 'img', key) % 8999}.jpg"
        if channel == "photo"
        else f"{v.display_name.replace(' ', '')}_{number}.pdf"
        if channel == "portal"
        else f"Invoice_{number}.pdf"
    )
    return _make_doc(
        cat,
        key=key,
        day=orig.day,
        release_at=release,
        channel=channel,
        v=v,
        loc=loc,
        truth=orig.truth,
        po=None,
        grn=None,
        line_items=orig.line_items,
        condition="duplicate",
        smudged=(),
        hero=None,
        expected={**orig.expected, "exceptions": ["duplicate"]},
        file_name=fname,
        r=r,
        seed=seed,
        duplicate_of=orig.key,
    )


def plan_day(
    catalog: Catalog, day: date, n: int = 180, seed: int = SEED, include_heroes: bool = True
) -> list[PlannedDoc]:
    """All documents for ``day`` (``n`` total including heroes and duplicate copies), sorted by release."""
    n = max(0, min(n, 400))
    docs = hero_docs(catalog, day, seed) if include_heroes else []
    m = max(0, n - len(docs))
    r = rng_for(seed, "day", day.isoformat())
    n_dup = sum(1 for _ in range(m) if r.random() < DUPLICATE_RATE)
    base = [_invoice(catalog, day, i, seed) for i in range(m - n_dup)]
    eligible = [d for d in base if d.condition != "fraud" and d.release_at.hour < 17]
    for orig in r.sample(eligible, min(n_dup, len(eligible))):
        base.append(_duplicate(catalog, orig, seed))
    docs.extend(base)
    docs.sort(key=lambda d: (d.release_at, d.key))
    return docs


__all__ = ["PlannedDoc", "RenderedDoc", "hero_docs", "plan_day", "simulate_extraction"]
