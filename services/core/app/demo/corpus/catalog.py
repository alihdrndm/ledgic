"""Northside Group master data: the single source of truth for the demo seed, corpus and replay.

``build_catalog(today)`` is pure and deterministic (seed 20260713): every id is a uuid5, every
number is authored or drawn from a seeded RNG. Only dates move with ``today`` (vendor age of the
Unlisted Supplier, the rolling contract end date per DECISIONS D8, Riverside's onboarding dates).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .items_data import ITEMS
from .rng import SEED, rng_for, sha256_hex, stable_uuid

ORG_ID = "992e72b7-9d9b-5104-9051-f5ef581c99e0"
ORG_SLUG = "northside"
ORG_NAME = "Northside Group"
TIMEZONE = "America/New_York"


@dataclass(frozen=True)
class Entity:
    n: int
    id: str
    name: str
    short_code: str
    erp: str  # quickbooks | netsuite


@dataclass(frozen=True)
class Location:
    id: str
    code: str
    name: str
    entity_n: int
    site_no: int
    address: str  # "120 Water St, Riverside"
    weight: float  # relative invoice volume


@dataclass(frozen=True)
class GLAccount:
    number: str
    name: str
    kind: str  # expense | liability

    @property
    def label(self) -> str:
        return f"{self.number} {self.name}"


@dataclass(frozen=True)
class Vendor:
    key: str
    id: str
    display_name: str
    legal_name: str
    category: str
    match_mode: str  # three_way | two_way
    terms_days: int
    invoice_prefix: str
    template: str  # A | B | C (email/photo layout); portal/edi always render with D
    default_gl: str
    tax_id: str  # EIN "NN-NNNNNNN"
    tax_id_last4: str
    tax_id_hash: str
    remit_name: str
    remit_address: str
    remit_address_json: dict[str, str]
    bank_routing: str  # printed on the vendor's invoices
    bank_account: str
    bank_fingerprint: str
    bank_last4: str
    w9_on_file: bool
    w9_routing: str
    w9_account: str
    w9_bank_fingerprint: str
    contact_email: str
    phone: str
    tagline: str
    aliases: tuple[str, ...]
    created_on: date
    taxable: bool
    prints_bank: bool

    @property
    def terms(self) -> str:
        return f"Net {self.terms_days}"


@dataclass(frozen=True)
class Item:
    key: str  # unique item_key, e.g. "PR-0002"
    id: str
    vendor_key: str
    sku: str  # vendor SKU printed on portal/EDI documents
    description: str
    uom: str
    unit_price: Decimal
    default_gl: str


@dataclass(frozen=True)
class ContractPrice:
    item_key: str
    item_id: str
    uom: str
    unit_price: Decimal
    clause_ref: str


@dataclass(frozen=True)
class Contract:
    id: str
    vendor_key: str
    vendor_id: str
    title: str
    effective_from: date
    effective_to: date
    countersigned_at: date
    prices: tuple[ContractPrice, ...]


@dataclass(frozen=True)
class DeliverySchedule:
    vendor_key: str
    cadence: str  # daily | 3x_week | 2x_week | weekly | monthly_fixed | ad_hoc
    weekdays: tuple[int, ...]  # 0=Mon; empty for monthly/ad hoc
    note: str


@dataclass(frozen=True)
class VendorLocation:
    vendor_key: str
    location_code: str
    since: date


@dataclass
class Catalog:
    today: date
    seed: int
    org: dict[str, object]
    entities: list[Entity]
    locations: list[Location]
    gl_accounts: list[GLAccount]
    vendors: list[Vendor]
    items: list[Item]
    contracts: list[Contract]
    schedules: list[DeliverySchedule]
    vendor_locations: list[VendorLocation]
    riverside_new_suppliers: tuple[str, ...]
    _vendor_by_key: dict[str, Vendor] = field(default_factory=dict, repr=False)
    _location_by_code: dict[str, Location] = field(default_factory=dict, repr=False)
    _items_by_vendor: dict[str, list[Item]] = field(default_factory=dict, repr=False)
    _item_by_desc: dict[tuple[str, str], Item] = field(default_factory=dict, repr=False)
    _contract_price: dict[str, tuple[Contract, ContractPrice]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._vendor_by_key = {v.key: v for v in self.vendors}
        self._location_by_code = {loc.code: loc for loc in self.locations}
        for it in self.items:
            self._items_by_vendor.setdefault(it.vendor_key, []).append(it)
            self._item_by_desc[(it.vendor_key, it.description)] = it
        for c in self.contracts:
            for p in c.prices:
                self._contract_price[p.item_key] = (c, p)

    def vendor(self, key: str) -> Vendor:
        return self._vendor_by_key[key]

    def vendor_by_name(self, display_name: str) -> Vendor:
        return next(v for v in self.vendors if v.display_name == display_name)

    def location(self, code: str) -> Location:
        return self._location_by_code[code]

    def entity(self, n: int) -> Entity:
        return next(e for e in self.entities if e.n == n)

    def items_for(self, vendor_key: str) -> list[Item]:
        return self._items_by_vendor.get(vendor_key, [])

    def item(self, vendor_key: str, description: str) -> Item:
        return self._item_by_desc[(vendor_key, description)]

    def contract_price(self, item_key: str, on: date) -> tuple[Contract, ContractPrice] | None:
        hit = self._contract_price.get(item_key)
        if hit and hit[0].effective_from <= on <= hit[0].effective_to:
            return hit
        return None

    def schedule(self, vendor_key: str) -> DeliverySchedule:
        return next(s for s in self.schedules if s.vendor_key == vendor_key)


# ---------------------------------------------------------------------------------------------
# Static master data
# ---------------------------------------------------------------------------------------------

ENTITIES = [
    (1, "Entity 1", "E1", "quickbooks"),
    (2, "Entity 2", "E2", "quickbooks"),
    (3, "Entity 3", "E3", "netsuite"),
]

NAMED_LOCATIONS = [  # (code, name, entity) from contracts/fixtures.json
    ("RS", "Riverside", 1),
    ("BS", "Bayside", 2),
    ("CM", "Commissary", 3),
    ("LS", "Lakeshore", 1),
    ("OM", "Old Mill", 1),
    ("PH", "Pierhead", 2),
    ("SB", "Saltbox", 2),
    ("CS", "Canal Street", 1),
]
GENERATED_LOCATIONS = [
    ("HV", "Harbor View"),
    ("EP", "Elm Park"),
    ("NG", "Northgate"),
    ("WF", "Westfield"),
    ("IW", "Ironworks"),
    ("BY", "Brickyard"),
    ("FR", "Foundry Row"),
    ("MC", "Mill Creek"),
    ("CH", "Cedar Hill"),
    ("FM", "Fairmount"),
    ("GP", "Greenpoint"),
    ("HL", "Highland"),
    ("KB", "Kingsbridge"),
    ("LD", "Linden"),
    ("MA", "Marina"),
    ("NM", "Newmarket"),
    ("OR", "Orchard"),
    ("PK", "Parkside"),
    ("QY", "Quarry"),
    ("RW", "Ridgeway"),
    ("SP", "Southport"),
    ("TN", "Tannery"),
    ("US", "Union Square"),
    ("VH", "Vinegar Hill"),
    ("WT", "Waterford"),
    ("YD", "Yardley"),
]
STREETS = [
    "Water St",
    "Front St",
    "Mill Rd",
    "Harbor Ave",
    "Market St",
    "Chestnut St",
    "Elm St",
    "Ferry Rd",
    "Union Ave",
    "Canal St",
    "Bridge St",
    "Dock Rd",
    "Pearl St",
    "Hudson Ave",
]

GL_ACCOUNTS = [
    ("5000", "COGS-Food", "expense"),
    ("5010", "COGS-Beverage", "expense"),
    ("6100", "Janitorial & Supplies", "expense"),
    ("6200", "Smallwares & Equipment", "expense"),
    ("6300", "Freight In", "expense"),
    ("9999", "Rounding", "expense"),
    ("2000", "Accounts Payable", "liability"),
    ("2200", "Sales Tax Payable", "liability"),
]

# key, display, category, match_mode, terms, prefix, template, gl, taxable, prints_bank, tagline, city
VENDORS = [
    (
        "broadline",
        "Broadline Distributor",
        "Broadline",
        "three_way",
        30,
        "BD-",
        "B",
        "5000",
        False,
        True,
        "Foodservice · Full line",
        "Secaucus, NJ 07094",
    ),
    (
        "protein",
        "Protein Supplier",
        "Protein",
        "three_way",
        14,
        "PS-",
        "B",
        "5000",
        False,
        True,
        "Seafood & meats · Since 1987",
        "New Bedford, MA 02740",
    ),
    (
        "produce",
        "Produce Supplier",
        "Produce",
        "three_way",
        14,
        "PR-",
        "A",
        "5000",
        False,
        False,
        "Regional · Direct delivery",
        "Bronx, NY 10474",
    ),
    (
        "janitorial",
        "Janitorial Services",
        "Janitorial",
        "two_way",
        30,
        "JS-",
        "C",
        "6100",
        True,
        True,
        "Commercial kitchen hygiene",
        "Yonkers, NY 10701",
    ),
    (
        "equipment",
        "Equipment Supplier",
        "Equipment",
        "three_way",
        30,
        "EQ-",
        "B",
        "6200",
        True,
        True,
        "Smallwares · Repairs · Parts",
        "Paterson, NJ 07501",
    ),
    (
        "beverage",
        "Beverage Distributor",
        "Beverage",
        "three_way",
        21,
        "BV-",
        "C",
        "5010",
        False,
        False,
        "Beverage · Coffee · Fountain",
        "Long Island City, NY 11101",
    ),
    (
        "dairy",
        "Dairy Supplier",
        "Dairy",
        "three_way",
        14,
        "DY-",
        "A",
        "5000",
        False,
        False,
        "Farm dairy · Cold chain",
        "Kingston, NY 12401",
    ),
    (
        "bakery",
        "Bakery Supplier",
        "Bakery",
        "three_way",
        7,
        "BK-",
        "A",
        "5000",
        False,
        False,
        "Baked fresh nightly",
        "Hoboken, NJ 07030",
    ),
    (
        "paper",
        "Paper Goods Supplier",
        "Paper goods",
        "three_way",
        30,
        "PG-",
        "C",
        "6100",
        True,
        False,
        "Disposables & packaging",
        "Edison, NJ 08817",
    ),
    (
        "unlisted",
        "Unlisted Supplier",
        "Specialty provisions",
        "three_way",
        15,
        "NV-",
        "C",
        "5000",
        False,
        True,
        "Specialty provisions",
        "Wilmington, DE 19801",
    ),
]

SCHEDULES = [
    ("broadline", "2x_week", (0, 3), "Mon/Thu truck"),
    ("protein", "3x_week", (0, 2, 4), "Mon/Wed/Fri"),
    ("produce", "daily", (0, 1, 2, 3, 4, 5), "Daily except Sunday"),
    ("janitorial", "monthly_fixed", (), "Billed on the 1st, fixed monthly services"),
    ("equipment", "ad_hoc", (), "Ad-hoc purchases"),
    ("beverage", "weekly", (1,), "Tuesday"),
    ("dairy", "3x_week", (1, 3, 5), "Tue/Thu/Sat"),
    ("bakery", "daily", (0, 1, 2, 3, 4, 5, 6), "Nightly bake, early drop"),
    ("paper", "weekly", (2,), "Wednesday"),
    ("unlisted", "ad_hoc", (), "No schedule — unverified vendor"),
]

ROADS = ["Industrial Pkwy", "Terminal Way", "Commerce Dr", "Port Rd", "Wharf St", "Depot Ave"]
RIVERSIDE_NEW_SUPPLIERS = ("bakery", "dairy")  # onboarded recently at Riverside, no contract


def _aba_check_digit(first8: str) -> str:
    w = [3, 7, 1, 3, 7, 1, 3, 7]
    s = sum(int(d) * k for d, k in zip(first8, w, strict=True))
    return str((10 - s % 10) % 10)


def _routing(rng) -> str:
    first8 = f"0{rng.randint(1, 3)}{rng.randint(100000, 999999)}"
    return first8 + _aba_check_digit(first8)


def bank_fingerprint(routing: str, account: str) -> str:
    """sha256 of 'routing:account' (digits only). Compare invoice bank details to the W-9 with this."""
    digits = lambda s: "".join(ch for ch in s if ch.isdigit())  # noqa: E731
    return sha256_hex(f"{digits(routing)}:{digits(account)}")


def last_day_of_month_after(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def build_catalog(today: date, seed: int = SEED) -> Catalog:
    rng = rng_for(seed, "catalog")

    entities = [Entity(n, stable_uuid("entity", code), name, code, erp) for n, name, code, erp in ENTITIES]

    locations: list[Location] = []
    gen_entities = [1, 2]
    for i, (code, name, ent) in enumerate(
        NAMED_LOCATIONS + [(c, nm, gen_entities[j % 2]) for j, (c, nm) in enumerate(GENERATED_LOCATIONS)]
    ):
        weight = {"RS": 3.0, "BS": 2.5, "CM": 2.2}.get(code, 1.4 if i < 8 else 1.0)
        address = f"{rng.randint(12, 980)} {rng.choice(STREETS)}, {name}"
        locations.append(Location(stable_uuid("location", code), code, name, ent, i + 1, address, weight))

    gl_accounts = [GLAccount(n, name, kind) for n, name, kind in GL_ACCOUNTS]

    vendors: list[Vendor] = []
    for key, display, cat, mode, terms, prefix, tpl, gl, taxable, prints_bank, tagline, city in VENDORS:
        vr = rng_for(seed, "vendor", key)
        ein = f"{vr.randint(10, 98)}-{vr.randint(1000000, 9999999)}"
        routing, account = _routing(vr), str(vr.randint(10**9, 10**11))
        w9_routing, w9_account = routing, account
        if key == "unlisted":  # the fraud case: invoice bank details differ from the W-9 on file
            w9_routing, w9_account = _routing(vr), str(vr.randint(10**9, 10**11))
        road = vr.choice(ROADS)
        street = f"{vr.randint(10, 2400)} {road}"
        slug = display.lower().replace(" ", "-")
        created = (
            (today - timedelta(days=4))
            if key == "unlisted"
            else date(2024, 1, 8) + timedelta(days=vr.randint(0, 300))
        )
        vendors.append(
            Vendor(
                key=key,
                id=stable_uuid("vendor", key),
                display_name=display,
                legal_name=f"{display} {'LLC' if vr.random() < 0.5 else 'Inc.'}",
                category=cat,
                match_mode=mode,
                terms_days=terms,
                invoice_prefix=prefix,
                template=tpl,
                default_gl=gl,
                tax_id=ein,
                tax_id_last4=ein[-4:],
                tax_id_hash=sha256_hex(ein.replace("-", "")),
                remit_name=display,
                remit_address=f"{street}, {city}",
                remit_address_json={"name": display, "line1": street, "city_state_zip": city},
                bank_routing=routing,
                bank_account=account,
                bank_fingerprint=bank_fingerprint(routing, account),
                bank_last4=account[-4:],
                w9_on_file=True,
                w9_routing=w9_routing,
                w9_account=w9_account,
                w9_bank_fingerprint=bank_fingerprint(w9_routing, w9_account),
                contact_email=f"ar@{slug}.example",
                phone=f"({vr.randint(201, 989)}) 555-{vr.randint(1000, 9999)}",
                tagline=tagline,
                aliases=(
                    display.upper(),
                    f"{display} Co.",
                    f"{display} {'LLC' if vr.random() < 0.5 else 'Inc'}",
                ),
                created_on=created,
                taxable=taxable,
                prints_bank=prints_bank,
            )
        )

    items: list[Item] = []
    for v in vendors:
        for i, (desc, uom, price, gl) in enumerate(ITEMS[v.key], start=1):
            key = f"{v.invoice_prefix.rstrip('-')}-{i:04d}"
            sku = f"{rng_for(seed, 'sku', key).randint(100000, 999999)}"
            items.append(Item(key, stable_uuid("item", key), v.key, sku, desc, uom, Decimal(price), gl))

    by_vendor: dict[str, list[Item]] = {}
    for it in items:
        by_vendor.setdefault(it.vendor_key, []).append(it)
    vmap = {v.key: v for v in vendors}

    rolling_to = last_day_of_month_after(today, 5)  # DECISIONS D8
    contracts: list[Contract] = []
    protein_clauses = {
        "Shrimp 16/20 IQF 2lb × 10": "4.2",
        "Cod loin 10lb case": "4.3",
        "Scallops U-10 dry 2lb": "4.4",
        "Atlantic salmon fillet 10lb": "4.5",
    }
    contracts.append(
        Contract(
            id=stable_uuid("contract", "protein-2026"),
            vendor_key="protein",
            vendor_id=vmap["protein"].id,
            title="Vendor agreement 2026",
            effective_from=date(2026, 3, 1),
            effective_to=rolling_to,
            countersigned_at=date(2026, 3, 3),
            prices=tuple(
                ContractPrice(it.key, it.id, it.uom, it.unit_price, protein_clauses[it.description])
                for it in by_vendor["protein"]
                if it.description in protein_clauses
            ),
        )
    )
    hist_start = today - timedelta(days=200)
    for vkey, title in (("broadline", "Distribution agreement"), ("produce", "Supply agreement")):
        cr = rng_for(seed, "contract", vkey)
        vitems = by_vendor[vkey]
        # cover ~60% of SKUs; produce hero items are always covered
        always = {"Romaine hearts 24ct", "Heirloom tomato 10lb", "Lemons 115ct case"}
        covered = [it for it in vitems if cr.random() < 0.6 or it.description in always]
        prices = tuple(
            ContractPrice(it.key, it.id, it.uom, it.unit_price, f"Sched. A-{n}")
            for n, it in enumerate(covered, start=1)
        )
        frm = date(hist_start.year, 1, 1)
        contracts.append(
            Contract(
                id=stable_uuid("contract", f"{vkey}-{frm.year}"),
                vendor_key=vkey,
                vendor_id=vmap[vkey].id,
                title=f"{title} {frm.year}",
                effective_from=frm,
                effective_to=last_day_of_month_after(today, 7),
                countersigned_at=frm + timedelta(days=4),
                prices=prices,
            )
        )

    schedules = [DeliverySchedule(*row) for row in SCHEDULES]

    vendor_locations: list[VendorLocation] = []
    for v in vendors:
        for loc in locations:
            if v.key == "unlisted":
                if loc.code == "CM":
                    vendor_locations.append(VendorLocation(v.key, loc.code, v.created_on))
                continue
            since = v.created_on
            if loc.code == "RS" and v.key in RIVERSIDE_NEW_SUPPLIERS:
                since = today - timedelta(days=38 if v.key == "dairy" else 24)
            vendor_locations.append(VendorLocation(v.key, loc.code, since))

    org = {"id": ORG_ID, "slug": ORG_SLUG, "name": ORG_NAME, "timezone": TIMEZONE, "is_demo": True}
    return Catalog(
        today=today,
        seed=seed,
        org=org,
        entities=entities,
        locations=locations,
        gl_accounts=gl_accounts,
        vendors=vendors,
        items=items,
        contracts=contracts,
        schedules=schedules,
        vendor_locations=vendor_locations,
        riverside_new_suppliers=RIVERSIDE_NEW_SUPPLIERS,
    )
