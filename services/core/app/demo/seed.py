# ruff: noqa: E501  (long SQL strings and fixture literals)
"""Northside demo tenant seed (13-demo-data §2): idempotent upserts of everything that is not produced by
the live pipeline.

    cd services/core && uv run python -m app.demo.seed            # upsert (safe to re-run)
    cd services/core && uv run python -m app.demo.seed --reset    # demo_purge_org() first, then seed

Seeds: org + settings + tolerance policy, Auth users (GoTrue admin API) + profiles + memberships, entities,
34 locations, GL accounts (per entity), vendors + aliases, items (embeddings left NULL for the AI seed),
contracts + contract prices (clause 4.2 shrimp $3.68, rolling end date per DECISIONS D8), mock ERP
integrations, hero POs/GRNs for today, ~5 months of coded back-history invoices for GL kNN (no pipeline
runs, so they never inflate KPIs), the two accepted Protein Supplier short-pays ($61.60, $47.20) with
their runs/approvals/audit rows, prompt version ``p-1`` and 12 weeks of ``eval_runs``.

Master data comes from ``app.demo.corpus.build_catalog`` (single source of truth shared with the replay).
Env: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DEMO_VIEWER_PASSWORD, DEMO_ELENA_PASSWORD.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import secrets
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection

from app.demo.corpus import Catalog, build_catalog, hero_docs, plan_day
from app.demo.corpus.catalog import ORG_ID
from app.demo.corpus.invoices import HEADER_FIELDS, LINE_FIELDS, PlannedDoc
from app.demo.corpus.rng import SEED, rng_for, sha256_hex, stable_uuid
from app.demo.planner import historical_coded_lines, prior_short_pays
from app.repo.sql import J, all_, one, val

log = logging.getLogger("ledgic.demo.seed")

CENT = Decimal("0.01")
PROMPT_VERSION = "p-1"
LLM_MODEL = "gpt-4.1-mini"
HISTORY_MONTHS = 6
HISTORY_PER_DAY = 19  # ≈ 2.9k coded lines over the ~152 history days (DB stays small)
HISTORY_GAP_DAYS = 31  # the most recent 30 days belong to the replay backfill
EVAL_WEEKS = 12
EVAL_SAMPLE = 200
EVAL_DOCS_PER_DAY = 40


# ---------------------------------------------------------------------------------------- users
@dataclass(frozen=True)
class DemoUser:
    key: str
    id: str
    email: str
    full_name: str
    initials: str
    role: str
    password_env: str | None = None


# contracts/fixtures.json "users" (embedded: the Railway image does not ship contracts/; a test checks equality)
USERS: tuple[DemoUser, ...] = (
    DemoUser(
        "elena",
        "c1f2540f-4d0c-5e8b-ba81-a0dd3de7ab39",
        "elena.marsh@demo.ledgic.dev",
        "Elena Marsh",
        "EM",
        "ap_manager",
        "DEMO_ELENA_PASSWORD",
    ),
    DemoUser(
        "tom",
        "063f728d-c685-5ba7-8e87-dac4f869ab91",
        "tom.iwu@demo.ledgic.dev",
        "Tom Iwu",
        "TI",
        "controller",
    ),
    DemoUser(
        "viewer",
        "2ff0bef9-b811-57ae-98a9-3cc42e42de8d",
        "viewer@demo.ledgic.dev",
        "Demo Viewer",
        "DV",
        "viewer",
        "DEMO_VIEWER_PASSWORD",
    ),
    DemoUser(
        "replay",
        "b9801444-eed3-5e24-b95e-c710ce9794a7",
        "replay@demo.ledgic.dev",
        "Demo replay",
        "DR",
        "ap_manager",
    ),
    DemoUser(
        "clerk1",
        "9779a180-97cf-5ce6-86b7-a5eeb87bf626",
        "clerk.one@demo.ledgic.dev",
        "Priya Shah",
        "PS",
        "ap_clerk",
    ),
    DemoUser(
        "clerk2",
        "255bbc34-7a6c-50cf-8568-6405dcf97b41",
        "clerk.two@demo.ledgic.dev",
        "Marco Diaz",
        "MD",
        "ap_clerk",
    ),
    DemoUser(
        "admin",
        "386eaeb3-e4ef-5f37-9a8f-0db42b251b60",
        "admin@demo.ledgic.dev",
        "Ledgic Admin",
        "LA",
        "admin",
    ),
)
USER_BY_KEY = {u.key: u for u in USERS}

POLICY = {
    "confidence_gate": Decimal("0.900"),
    "field_floor": Decimal("0.750"),
    "dup_hold_threshold": Decimal("0.900"),
    "dup_suggest_threshold": Decimal("0.750"),
    "fraud_hold_threshold": Decimal("0.700"),
    "manager_limit": Decimal("5000.00"),
    "controller_notify_threshold": Decimal("500.00"),
    "sla_hours": 24,
    "loaded_hourly_rate_usd": Decimal("35.00"),
    "infra_monthly_usd": Decimal("55.00"),
}
TOLERANCE = {"pct": Decimal("0.02"), "abs_amount": Decimal("25.00")}


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def _local(cat: Catalog, d: date, hh: int = 9, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=ZoneInfo(str(cat.org["timezone"])))


# ---------------------------------------------------------------------------------------- pure builders
def gl_id(entity_code: str, number: str) -> str:
    return stable_uuid("gl_account", f"{entity_code}:{number}")


def master_rows(cat: Catalog) -> dict[str, list[dict[str, Any]]]:
    """Rows for every master-data table (pure; no database)."""
    org = ORG_ID
    admin = USER_BY_KEY["admin"].id
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in cat.entities:
        out["entities"].append(
            {
                "id": e.id,
                "org_id": org,
                "name": e.name,
                "short_code": e.short_code,
                "erp": e.erp,
                "erp_company_ref": f"mock-{e.erp}-{e.short_code.lower()}",
            }
        )
    for loc in cat.locations:
        out["locations"].append(
            {
                "id": loc.id,
                "org_id": org,
                "entity_id": cat.entity(loc.entity_n).id,
                "code": loc.code,
                "name": loc.name,
                "erp_class_ref": f"class-{loc.code}",
            }
        )
    for e in cat.entities:
        for g in cat.gl_accounts:
            out["gl_accounts"].append(
                {
                    "id": gl_id(e.short_code, g.number),
                    "org_id": org,
                    "entity_id": e.id,
                    "number": g.number,
                    "name": g.name,
                    "erp_ref": f"{e.erp}:{e.short_code}:{g.number}",
                }
            )
    for i, v in enumerate(cat.vendors, start=1):
        created = _local(cat, v.created_on, 11, 20)
        out["vendors"].append(
            {
                "id": v.id,
                "org_id": org,
                "display_name": v.display_name,
                "legal_name": v.legal_name,
                "category": v.category,
                "match_mode": v.match_mode,
                "tax_id_last4": v.tax_id_last4,
                "tax_id_hash": v.tax_id_hash,
                "remit_address": J(v.remit_address_json),
                "remit_address_changed_at": created if v.key == "unlisted" else None,
                "bank_fingerprint": v.bank_fingerprint,
                "bank_last4": v.bank_last4,
                "w9_on_file": v.w9_on_file,
                "w9_bank_fingerprint": v.w9_bank_fingerprint,
                "contact_email": v.contact_email,
                "erp_vendor_ref": J({"quickbooks": f"QB-V{i:04d}", "netsuite": f"NS-V{i:04d}"}),
                # The new (fraud-case) vendor was keyed in by the admin, so the controller may release its hold.
                "created_by": admin if v.key == "unlisted" else None,
                "created_at": created,
            }
        )
        for alias in v.aliases:
            out["vendor_aliases"].append({"vendor_id": v.id, "alias": alias})
    for it in cat.items:
        out["items"].append(
            {
                "id": it.id,
                "org_id": org,
                "item_key": it.key,
                "description": it.description,
                "uom": it.uom,
                "default_gl": it.default_gl,
            }
        )
    for c in cat.contracts:
        slug = re.sub(r"[^a-z0-9]+", "-", f"{c.vendor_key} {c.title}".lower()).strip("-")
        out["contracts"].append(
            {
                "id": c.id,
                "org_id": org,
                "vendor_id": c.vendor_id,
                "title": c.title,
                "document_path": f"org/{org}/contracts/{slug}.pdf",
                "effective_from": c.effective_from,
                "effective_to": c.effective_to,
                "countersigned_at": c.countersigned_at,
            }
        )
        for p in c.prices:
            out["contract_prices"].append(
                {
                    "id": stable_uuid("contract_price", f"{c.id}:{p.item_key}"),
                    "contract_id": c.id,
                    "item_id": p.item_id,
                    "uom": p.uom,
                    "unit_price": p.unit_price,
                    "clause_ref": p.clause_ref,
                }
            )
    for e in cat.entities:
        out["integrations"].append(
            {
                "org_id": org,
                "provider": e.erp,
                "entity_id": e.id,
                "status": "connected",
                "config": J({"mock": True, "company_ref": f"mock-{e.erp}-{e.short_code.lower()}"}),
            }
        )
    return dict(out)


@dataclass
class History:
    documents: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    lines: list[dict[str, Any]]
    pos: list[dict[str, Any]]
    po_lines: list[dict[str, Any]]
    grns: list[dict[str, Any]]
    grn_lines: list[dict[str, Any]]


def history_rows(
    cat: Catalog,
    months: int = HISTORY_MONTHS,
    per_day: int = HISTORY_PER_DAY,
    gap_days: int = HISTORY_GAP_DAYS,
    seed: int = SEED,
) -> History:
    """Coded back-history for GL kNN: one invoice per (day, vendor), lines from planner.historical_coded_lines.
    Posted, but with no pipeline run (KPI views count only invoices that went through a run)."""
    cutoff = cat.today - timedelta(days=gap_days)
    groups: dict[tuple[date, str], list[Any]] = defaultdict(list)
    for cl in historical_coded_lines(cat, months=months, per_day=per_day, seed=seed):
        if cl.date < cutoff:
            groups[(cl.date, cl.vendor_key)].append(cl)

    item_by_key = {it.key: it for it in cat.items}
    h = History([], [], [], [], [], [], [])
    org = ORG_ID
    for (day, vkey), cls in sorted(groups.items()):
        v = cat.vendor(vkey)
        loc = cat.location(cls[0].location_code)
        ent = cat.entity(loc.entity_n)
        number = f"{v.invoice_prefix}H{day:%Y%m%d}"
        inv_id = stable_uuid("history_invoice", number)
        doc_id = stable_uuid("history_document", number)
        po_number = f"PO-{loc.code}-H{day:%y%m%d}-{v.invoice_prefix.rstrip('-')}"
        po_id = stable_uuid("po", po_number)
        received = _local(cat, day, 9, 0) + timedelta(minutes=7 * len(h.invoices) % 600)
        subtotal = Decimal(0)
        for n, cl in enumerate(cls, start=1):
            it = item_by_key[cl.item_key]
            cp = cat.contract_price(it.key, day)
            unit = cp[1].unit_price if cp else it.unit_price
            amount = Decimal(cl.amount)
            qty = max(Decimal(1), (amount / it.unit_price).quantize(Decimal(1)))
            amount = _q(qty * unit)
            subtotal += amount
            h.po_lines.append(
                {
                    "po_id": po_id,
                    "line_no": n,
                    "item_id": it.id,
                    "description": it.description,
                    "qty": qty,
                    "uom": it.uom,
                    "unit_price": unit,
                    "amount": amount,
                }
            )
            h.lines.append(
                {
                    "id": stable_uuid("invoice_line", f"{inv_id}:{n}"),
                    "invoice_id": inv_id,
                    "line_no": n,
                    "description": cl.description,
                    "item_id": it.id,
                    "qty": qty,
                    "uom": it.uom,
                    "unit_price": unit,
                    "amount": amount,
                    "confidences": J(
                        {"description": 1.0, "qty": 1.0, "uom": 1.0, "unit_price": 1.0, "amount": 1.0}
                    ),
                    "gl_account_id": gl_id(ent.short_code, cl.gl_account),
                    "gl_confidence": Decimal("1.000"),
                    "po_id": po_id,
                }
            )
        tax = _q(subtotal * Decimal("0.08875")) if v.taxable else Decimal(0)
        total = subtotal + tax
        h.pos.append(
            {
                "id": po_id,
                "org_id": org,
                "entity_id": ent.id,
                "location_id": loc.id,
                "vendor_id": v.id,
                "po_number": po_number,
                "status": "closed",
                "ordered_at": received - timedelta(days=2),
                "source": "netsuite" if ent.erp == "netsuite" else "quickbooks",
                "total": subtotal,
            }
        )
        if v.match_mode == "three_way":
            grn_number = f"GRN-{loc.code}-H{day:%y%m%d}-{v.invoice_prefix.rstrip('-')}"
            grn_id = stable_uuid("grn", grn_number)
            h.grns.append(
                {
                    "id": grn_id,
                    "org_id": org,
                    "po_id": po_id,
                    "grn_number": grn_number,
                    "received_at": received - timedelta(hours=2),
                    "received_by": f"Dock · {loc.name}",
                    "source": "receiving_app",
                }
            )
            for n in range(1, len(cls) + 1):
                pl = h.po_lines[-len(cls) + n - 1]
                h.grn_lines.append(
                    {
                        "grn_id": grn_id,
                        "po_id": po_id,
                        "line_no": n,
                        "qty_received": pl["qty"],
                        "uom": pl["uom"],
                    }
                )
        h.documents.append(
            {
                "id": doc_id,
                "org_id": org,
                "channel": "email",
                "storage_path": f"org/{org}/history/{number}.pdf",
                "sha256": sha256_hex(f"ledgic-history:{number}"),
                "mime": "application/pdf",
                "page_count": 1,
                "original_filename": f"Invoice_{number}.pdf",
                "source_meta": J(
                    {"synthetic": True, "history": True, "purpose": "GL kNN back-history (no pipeline run)"}
                ),
                "received_at": received,
            }
        )
        h.invoices.append(
            {
                "id": inv_id,
                "org_id": org,
                "document_id": doc_id,
                "vendor_id": v.id,
                "entity_id": ent.id,
                "location_id": loc.id,
                "po_id": po_id,
                "invoice_number": number,
                "invoice_date": day,
                "due_date": day + timedelta(days=v.terms_days),
                "terms": v.terms,
                "subtotal": subtotal,
                "tax": tax,
                "freight": Decimal(0),
                "total": total,
                "status": "posted",
                "doc_confidence": None,
                "gate_passed": True,
                "touchless": None,
                "human_touches": 0,
                "extraction_mode": "simulated",
                "received_at": received,
                "posted_at": received + timedelta(hours=26),
            }
        )
    return h


# ---------------------------------------------------------------------------------------- eval
_MONEY_FIELDS = {"subtotal", "tax", "freight", "total", "unit_price", "amount", "qty"}


def _norm(field: str, value: Any) -> Any:
    """06 §10 normalisation: money to cents, dates ISO, invoice numbers alnum-upper, text casefolded."""
    if value is None:
        return None
    key = field.split(".")[-1]
    if key in _MONEY_FIELDS:
        try:
            return Decimal(str(value).replace(",", "").replace("$", "")).quantize(CENT)
        except Exception:  # noqa: BLE001 - garbage reads count as wrong
            return str(value)
    if key == "invoice_number" or key == "po_reference":
        return re.sub(r"[^A-Z0-9]", "", str(value).upper())
    if isinstance(value, dict):
        return {k: _norm(k, v) for k, v in sorted(value.items())}
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def _matches(field: str, pred: Any, label: Any) -> bool:
    if field.endswith("description"):
        from rapidfuzz import fuzz

        return fuzz.ratio(_norm(field, pred), _norm(field, label)) >= 90
    return _norm(field, pred) == _norm(field, label)


def _misread(field: str, value: Any, r: Any) -> Any:
    """A plausible extraction error: a wrong digit / dropped character / shifted date."""
    s = str(value) if not isinstance(value, dict) else repr(value)
    if isinstance(value, dict):
        k = r.choice(sorted(value))
        return {**value, k: _misread(k, value[k], r)}
    digits = [i for i, ch in enumerate(s) if ch.isdigit()]
    if digits:
        i = r.choice(digits)
        return s[:i] + str((int(s[i]) + r.randint(1, 8)) % 10) + s[i + 1 :]
    if len(s) > 3:
        i = r.randrange(len(s))
        return s[:i] + s[i + 1 :]
    return s + "?"


def simulated_read(doc: PlannedDoc, r: Any) -> dict[str, Any]:
    """Pre-human values of the simulated extraction. Each field is misread with probability 1 − confidence,
    i.e. the simulation is calibrated: a field reported at 0.95 is right 95% of the time."""
    sim = doc.simulated_extraction
    out: dict[str, Any] = {}
    for k in HEADER_FIELDS:
        f = sim.get(k)
        if f is None or f.get("value") is None:
            continue
        out[k] = _misread(k, f["value"], r) if r.random() > float(f["confidence"]) else f["value"]
    for i, ln in enumerate(sim["lines"]):
        for k in LINE_FIELDS:
            f = ln.get(k)
            if f is None or f.get("value") is None:
                continue
            out[f"lines[{i}].{k}"] = (
                _misread(k, f["value"], r) if r.random() > float(f["confidence"]) else f["value"]
            )
    return out


def score_doc(doc: PlannedDoc, pred: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """{field_group: (labeled, correct)} comparing predictions to the corpus truth labels."""
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    truth = doc.truth
    for k in HEADER_FIELDS:
        if truth.get(k) is None:
            continue
        out[k][0] += 1
        out[k][1] += int(_matches(k, pred.get(k), truth[k]))
    for i, ln in enumerate(truth["lines"]):
        for k in LINE_FIELDS:
            if ln.get(k) is None:
                continue
            g = f"lines.{k}"
            out[g][0] += 1
            out[g][1] += int(_matches(k, pred.get(f"lines[{i}].{k}"), ln[k]))
    return {k: (v[0], v[1]) for k, v in out.items()}


def _stratified(docs: Sequence[PlannedDoc], n: int, r: Any) -> list[PlannedDoc]:
    by_channel: dict[str, list[PlannedDoc]] = defaultdict(list)
    for d in docs:
        by_channel[d.channel].append(d)
    total = len(docs)
    picked: list[PlannedDoc] = []
    for ch in sorted(by_channel):
        pool = by_channel[ch]
        k = min(len(pool), max(1, round(n * len(pool) / total)))
        picked.extend(r.sample(pool, k))
    return picked[:n]


def week_starts(today: date, weeks: int = EVAL_WEEKS) -> list[date]:
    """Mondays of the ``weeks`` complete weeks before the current one, oldest first."""
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=k) for k in range(weeks, 0, -1)]


def eval_rows(
    cat: Catalog,
    weeks: int = EVAL_WEEKS,
    sample: int = EVAL_SAMPLE,
    docs_per_day: int = EVAL_DOCS_PER_DAY,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """Weekly eval (06 §10): stratified sample of the week's corpus, simulated pre-human reads vs labels."""
    rows = []
    for ws in week_starts(cat.today, weeks):
        docs: list[PlannedDoc] = []
        for d in range(7):
            docs.extend(
                plan_day(cat, ws + timedelta(days=d), n=docs_per_day, seed=seed, include_heroes=False)
            )
        r = rng_for(seed, "eval", ws.isoformat())
        picked = _stratified(docs, sample, r)
        by_field: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for doc in picked:
            for k, (lab, ok) in score_doc(doc, simulated_read(doc, r)).items():
                by_field[k][0] += lab
                by_field[k][1] += ok
        labeled = sum(v[0] for v in by_field.values())
        correct = sum(v[1] for v in by_field.values())
        rows.append(
            {
                "org_id": ORG_ID,
                "week_start": ws,
                "prompt_version": PROMPT_VERSION,
                "sample_size": len(picked),
                "fields_labeled": labeled,
                "fields_correct": correct,
                "by_field": J(
                    {
                        k: {
                            "labeled": v[0],
                            "correct": v[1],
                            "accuracy": round(v[1] / v[0], 4) if v[0] else None,
                        }
                        for k, v in sorted(by_field.items())
                    }
                ),
            }
        )
    return rows


# ---------------------------------------------------------------------------------------- prior short-pays
def short_pay_bundle(cat: Catalog) -> list[dict[str, Any]]:
    """Everything persisted for each accepted prior short-pay (planner.prior_short_pays)."""
    out = []
    elena = USER_BY_KEY["elena"]
    ent = cat.entity(cat.location("RS").entity_n)
    shrimp_cp = cat.contract_price(cat.item("protein", "Shrimp 16/20 IQF 2lb × 10").key, cat.today)
    for prior_count, sp in enumerate(sorted(prior_short_pays(cat), key=lambda x: x["received_at"])):
        received = datetime.fromisoformat(sp["received_at"])
        decided = datetime.fromisoformat(sp["decided_at"])
        opened = received + timedelta(minutes=2)
        posted = decided + timedelta(minutes=4)
        inv_id = sp["invoice_id"]
        number = sp["invoice_number"]
        po_id, grn_id = stable_uuid("po", sp["po_number"]), stable_uuid("grn", sp["grn_number"])
        run_id = stable_uuid("run", f"prior-short-pay:{number}")
        doc_id = stable_uuid("document", f"prior-short-pay:{number}")
        exc_id = stable_uuid("exception", f"prior-short-pay:{number}")
        appr_id = stable_uuid("approval", f"prior-short-pay:{number}")
        mr_id = stable_uuid("match_result", number)
        inv_date = date.fromisoformat(sp["invoice_date"])
        po_total = sum(
            (_q(Decimal(ln["qty"]) * Decimal(ln["po_unit_price"])) for ln in sp["lines"]), Decimal(0)
        )
        hold, pay, total = Decimal(sp["hold_amount"]), Decimal(sp["pay_amount"]), Decimal(sp["total"])
        conf = min(Decimal("0.95"), Decimal("0.80") + Decimal("0.07") * min(2, prior_count))
        shrimp = sp["lines"][0]
        expected_ext = _q(Decimal(shrimp["qty"]) * Decimal(shrimp["po_unit_price"]))
        allowed = min(_q(expected_ext * TOLERANCE["pct"]), TOLERANCE["abs_amount"])
        month = shrimp_cp[0].effective_to.strftime("%b %Y") if shrimp_cp else ""
        reasons = [
            f"Contract clause 4.2 fixes {shrimp['description']} at ${shrimp['po_unit_price']}/lb (in effect through {month})",
            f"Invoice bills ${shrimp['unit_price']}/lb: ${shrimp['amount']} against ${expected_ext} expected",
            f"Goods receipt {sp['grn_number']} confirms all {shrimp['qty']} lb received",
            f"{prior_count} prior short-pay{'s' if prior_count != 1 else ''} accepted by this vendor in 90 days",
        ]
        lines = []
        for n, ln in enumerate(sp["lines"], start=1):
            lines.append(
                {
                    "id": stable_uuid("invoice_line", f"{inv_id}:{n}"),
                    "invoice_id": inv_id,
                    "line_no": n,
                    "description": ln["description"],
                    "item_id": ln["item_id"],
                    "qty": Decimal(ln["qty"]),
                    "uom": ln["uom"],
                    "unit_price": Decimal(ln["unit_price"]),
                    "amount": Decimal(ln["amount"]),
                    "confidences": J(
                        {"description": 0.99, "qty": 0.98, "uom": 0.99, "unit_price": 0.98, "amount": 0.99}
                    ),
                    "gl_account_id": gl_id(ent.short_code, "5000"),
                    "gl_confidence": Decimal("0.960"),
                    "po_id": po_id,
                }
            )
        out.append(
            {
                "po": {
                    "id": po_id,
                    "org_id": ORG_ID,
                    "entity_id": ent.id,
                    "location_id": sp["location_id"],
                    "vendor_id": sp["vendor_id"],
                    "po_number": sp["po_number"],
                    "status": "closed",
                    "ordered_at": received - timedelta(days=2),
                    "source": "quickbooks",
                    "total": po_total,
                },
                "po_lines": [
                    {
                        "po_id": po_id,
                        "line_no": n,
                        "item_id": ln["item_id"],
                        "description": ln["description"],
                        "qty": Decimal(ln["qty"]),
                        "uom": ln["uom"],
                        "unit_price": Decimal(ln["po_unit_price"]),
                        "amount": _q(Decimal(ln["qty"]) * Decimal(ln["po_unit_price"])),
                    }
                    for n, ln in enumerate(sp["lines"], start=1)
                ],
                "grn": {
                    "id": grn_id,
                    "org_id": ORG_ID,
                    "po_id": po_id,
                    "grn_number": sp["grn_number"],
                    "received_at": received - timedelta(hours=3),
                    "received_by": "Dock · Riverside",
                    "source": "receiving_app",
                },
                "grn_lines": [
                    {
                        "grn_id": grn_id,
                        "po_id": po_id,
                        "line_no": n,
                        "qty_received": Decimal(ln["qty"]),
                        "uom": ln["uom"],
                    }
                    for n, ln in enumerate(sp["lines"], start=1)
                ],
                "document": {
                    "id": doc_id,
                    "org_id": ORG_ID,
                    "channel": "email",
                    "storage_path": f"org/{ORG_ID}/inbox/{number}.pdf",
                    "sha256": sha256_hex(f"ledgic-prior-short-pay:{number}"),
                    "mime": "application/pdf",
                    "page_count": 1,
                    "original_filename": f"Invoice_{number}.pdf",
                    "source_meta": J({"synthetic": True, "from": "billing@protein-supplier.example"}),
                    "received_at": received,
                },
                "invoice": {
                    "id": inv_id,
                    "org_id": ORG_ID,
                    "document_id": doc_id,
                    "vendor_id": sp["vendor_id"],
                    "entity_id": ent.id,
                    "location_id": sp["location_id"],
                    "po_id": po_id,
                    "invoice_number": number,
                    "invoice_date": inv_date,
                    "due_date": inv_date + timedelta(days=14),
                    "terms": "Net 14",
                    "subtotal": total,
                    "tax": Decimal(0),
                    "freight": Decimal(0),
                    "total": total,
                    "status": "posted",
                    "doc_confidence": Decimal("0.970"),
                    "gate_passed": True,
                    "touchless": False,
                    "human_touches": 1,
                    "extraction_mode": "simulated",
                    "received_at": received,
                    "posted_at": posted,
                },
                "fields": [
                    {
                        "invoice_id": inv_id,
                        "field": f,
                        "value": v,
                        "confidence": Decimal(c),
                        "source": "llm",
                        "version": 1,
                        "set_at": received + timedelta(seconds=12),
                    }
                    for f, v, c in (
                        ("vendor_name", "Protein Supplier", "0.990"),
                        ("invoice_number", number, "0.980"),
                        ("invoice_date", inv_date.isoformat(), "0.970"),
                        ("terms", "Net 14", "0.960"),
                        ("po_reference", sp["po_number"], "0.970"),
                        ("total", f"{total:f}", "0.990"),
                    )
                ],
                "lines": lines,
                "run": {
                    "id": run_id,
                    "org_id": ORG_ID,
                    "document_id": doc_id,
                    "invoice_id": inv_id,
                    "workflow_version": "v1",
                    "status": "succeeded",
                    "current_stage": "close",
                    "next_attempt_at": None,
                    "started_at": received,
                    "finished_at": posted + timedelta(seconds=3),
                },
                "events": [
                    ("intake", "succeeded", received, 400, "Received — email PDF, 1 page", {}),
                    (
                        "extraction",
                        "succeeded",
                        received + timedelta(seconds=12),
                        11600,
                        f"Extracted — {len(lines)} line items, conf 0.97",
                        {"gate_passed": True, "doc_confidence": 0.97},
                    ),
                    (
                        "enrichment",
                        "succeeded",
                        received + timedelta(seconds=14),
                        900,
                        f"Enriched — {sp['po_number']}",
                        {},
                    ),
                    (
                        "screening",
                        "succeeded",
                        received + timedelta(seconds=15),
                        300,
                        "Screened — no duplicate, no fraud signal",
                        {},
                    ),
                    (
                        "match",
                        "succeeded",
                        received + timedelta(seconds=16),
                        120,
                        f"Matched — price variance on line 1 (+${hold:f})",
                        {"verdict": "price_variance"},
                    ),
                    (
                        "approval",
                        "waiting",
                        opened,
                        None,
                        "Waiting — price variance, routed to AP manager",
                        {"exception_id": exc_id},
                    ),
                    (
                        "approval",
                        "resumed",
                        decided,
                        None,
                        f"Short-pay by {elena.full_name}",
                        {
                            "actor_id": elena.id,
                            "action": "short_pay",
                            "approval_id": appr_id,
                            "exception_id": exc_id,
                        },
                    ),
                    (
                        "posting",
                        "succeeded",
                        posted,
                        1400,
                        f"Posted — QuickBooks, JE {number}",
                        {"system": "quickbooks"},
                    ),
                ],
                "match": {
                    "id": mr_id,
                    "invoice_id": inv_id,
                    "verdict": "price_variance",
                    "tolerance_pct": TOLERANCE["pct"],
                    "tolerance_abs": TOLERANCE["abs_amount"],
                    "expected_total": pay,
                    "total_delta": hold,
                    "lines_verified": len(lines) - 1,
                    "lines_total": len(lines),
                    "duration_ms": 120,
                    "computed_at": received + timedelta(seconds=16),
                },
                "match_lines": [
                    {
                        "id": stable_uuid("match_line", f"{number}:{n}"),
                        "match_result_id": mr_id,
                        "invoice_line_id": stable_uuid("invoice_line", f"{inv_id}:{n}"),
                        "po_id": po_id,
                        "line_no": n,
                        "grn_qty": Decimal(ln["qty"]),
                        "expected_unit_price": Decimal(ln["po_unit_price"]),
                        "expected_source": "contract" if ln.get("clause") else "po",
                        "contract_price_id": (
                            stable_uuid("contract_price", f"{shrimp_cp[0].id}:{shrimp_cp[1].item_key}")
                            if ln.get("clause") and shrimp_cp
                            else None
                        ),
                        "expected_amount": _q(Decimal(ln["qty"]) * Decimal(ln["po_unit_price"])),
                        "delta_amount": Decimal(ln["amount"])
                        - _q(Decimal(ln["qty"]) * Decimal(ln["po_unit_price"])),
                        "delta_pct": (
                            (Decimal(ln["amount"]) / _q(Decimal(ln["qty"]) * Decimal(ln["po_unit_price"])))
                            - 1
                        ).quantize(Decimal("0.00001")),
                        "allowed_amount": allowed
                        if n == 1
                        else min(_q(Decimal(ln["amount"]) * TOLERANCE["pct"]), TOLERANCE["abs_amount"]),
                        "verdict": "price_variance" if n == 1 else "matched",
                        "note": f"Contract clause 4.2 ${ln['po_unit_price']}/lb" if n == 1 else None,
                    }
                    for n, ln in enumerate(sp["lines"], start=1)
                ],
                "exception": {
                    "id": exc_id,
                    "org_id": ORG_ID,
                    "invoice_id": inv_id,
                    "run_id": run_id,
                    "type": "price_variance",
                    "status": "resolved",
                    "amount_at_risk": hold,
                    "reason": f"{shrimp['description']} billed ${shrimp['unit_price']}/lb against "
                    f"${shrimp['po_unit_price']} contract (clause 4.2)",
                    "assigned_role": "ap_manager",
                    "opened_at": opened,
                    "first_viewed_at": decided - timedelta(minutes=6),
                    "sla_due_at": opened + timedelta(hours=24),
                    "resolved_at": decided,
                },
                "recommendation": {
                    "exception_id": exc_id,
                    "action": "short_pay",
                    "pay_amount": pay,
                    "hold_amount": hold,
                    "confidence": conf,
                    "reasons": J(reasons),
                },
                "approval": {
                    "id": appr_id,
                    "org_id": ORG_ID,
                    "exception_id": exc_id,
                    "actor_id": elena.id,
                    "action": "short_pay",
                    "pay_amount": pay,
                    "hold_amount": hold,
                    "comment": "Short-paid to contract clause 4.2; vendor notified",
                    "decided_at": decided,
                    "time_spent_seconds": 6 * 60,
                },
                "posting": {
                    "org_id": ORG_ID,
                    "invoice_id": inv_id,
                    "system": "quickbooks",
                    "status": "posted",
                    "external_id": f"JE-{number}",
                    "request": J({"mock": True, "amount": f"{pay:f}"}),
                    "response": J({"mock": True, "id": f"JE-{number}"}),
                    "attempts": 1,
                    "posted_at": posted,
                },
                "audit": [
                    (
                        "core",
                        "core",
                        "invoice.created",
                        "invoice",
                        inv_id,
                        None,
                        {"invoice_id": inv_id, "invoice_number": number, "total": f"{total:f}"},
                        received + timedelta(seconds=12),
                    ),
                    (
                        "core",
                        "core",
                        "exception.opened",
                        "exception",
                        exc_id,
                        None,
                        {"invoice_id": inv_id, "type": "price_variance", "amount_at_risk": f"{hold:f}"},
                        opened,
                    ),
                    (
                        "user",
                        elena.id,
                        "decision.short_pay",
                        "approval",
                        appr_id,
                        None,
                        {
                            "exception_id": exc_id,
                            "invoice_id": inv_id,
                            "action": "short_pay",
                            "pay_amount": f"{pay:f}",
                            "hold_amount": f"{hold:f}",
                            "role": "ap_manager",
                        },
                        decided,
                    ),
                    (
                        "user",
                        elena.id,
                        "exception.resolved",
                        "exception",
                        exc_id,
                        {"status": "open"},
                        {"status": "resolved", "invoice_id": inv_id, "approval_id": appr_id},
                        decided,
                    ),
                    (
                        "core",
                        "core",
                        "invoice.posted",
                        "invoice",
                        inv_id,
                        {"status": "approved"},
                        {
                            "status": "posted",
                            "invoice_id": inv_id,
                            "system": "quickbooks",
                            "external_id": f"JE-{number}",
                        },
                        posted,
                    ),
                ],
            }
        )
    return out


# ---------------------------------------------------------------------------------------- DB helpers
async def upsert(
    conn: AsyncConnection,
    table: str,
    rows: Sequence[dict[str, Any]],
    conflict: str,
    update: Iterable[str] | None = None,
    skip: Iterable[str] = (),
) -> int:
    """Bulk ``insert ... on conflict (<conflict>) do update`` (or ``do nothing`` when update is empty)."""
    if not rows:
        return 0
    skip = set(skip)
    cols = [c for c in rows[0] if c not in skip]
    upd = [
        c for c in (update if update is not None else cols) if c not in conflict.replace(" ", "").split(",")
    ]
    action = "do update set " + ", ".join(f"{c} = excluded.{c}" for c in upd) if upd else "do nothing"
    sql = (
        f"insert into public.{table} ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
        f"on conflict ({conflict}) {action}"
    )
    async with conn.cursor() as cur:
        await cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)


async def insert_po_bundle(
    conn: AsyncConnection,
    pos: list[dict[str, Any]],
    po_lines: list[dict[str, Any]],
    grns: list[dict[str, Any]],
    grn_lines: list[dict[str, Any]],
) -> None:
    await upsert(
        conn,
        "purchase_orders",
        pos,
        "org_id, po_number",
        ["entity_id", "location_id", "vendor_id", "status", "ordered_at", "source", "total"],
    )
    await upsert(
        conn,
        "po_lines",
        po_lines,
        "po_id, line_no",
        ["item_id", "description", "qty", "uom", "unit_price", "amount"],
    )
    await upsert(
        conn, "goods_receipts", grns, "org_id, grn_number", ["po_id", "received_at", "received_by", "source"]
    )
    if grns:
        await conn.execute(
            "delete from public.grn_lines where grn_id = any(%s::uuid[])", ([g["id"] for g in grns],)
        )
        async with conn.cursor() as cur:
            await cur.executemany(
                "insert into public.grn_lines (grn_id, po_line_id, qty_received, uom) "
                "select g.id, pl.id, %s, %s from public.goods_receipts g join public.po_lines pl on pl.po_id = %s "
                "and pl.line_no = %s where g.org_id = %s and g.id = %s",
                [
                    (gl["qty_received"], gl["uom"], gl["po_id"], gl["line_no"], ORG_ID, gl["grn_id"])
                    for gl in grn_lines
                ],
            )


async def insert_invoice_lines(conn: AsyncConnection, lines: list[dict[str, Any]]) -> None:
    if not lines:
        return
    cols = [
        "id",
        "invoice_id",
        "line_no",
        "description",
        "item_id",
        "qty",
        "uom",
        "unit_price",
        "amount",
        "confidences",
        "gl_account_id",
        "gl_confidence",
    ]
    sql = (
        f"insert into public.invoice_lines ({', '.join(cols)}, po_line_id) "
        f"values ({', '.join(['%s'] * len(cols))}, "
        f"(select id from public.po_lines where po_id = %s and line_no = %s)) "
        f"on conflict (invoice_id, line_no) do update set description = excluded.description, "
        f"item_id = excluded.item_id, qty = excluded.qty, uom = excluded.uom, unit_price = excluded.unit_price, "
        f"amount = excluded.amount, gl_account_id = excluded.gl_account_id, gl_confidence = excluded.gl_confidence, "
        f"po_line_id = excluded.po_line_id"
    )
    async with conn.cursor() as cur:
        await cur.executemany(
            sql, [tuple(ln[c] for c in cols) + (ln.get("po_id"), ln["line_no"]) for ln in lines]
        )


# ---------------------------------------------------------------------------------------- auth users
def _env(name: str) -> str | None:
    """os.environ first, then the same .env files Settings reads (pydantic does not export them)."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        from dotenv import dotenv_values
    except ImportError:  # pragma: no cover
        return None
    for path in ("../../.env", ".env"):
        val = dotenv_values(path).get(name) if os.path.exists(path) else None
        if val:
            return val
    return None


async def ensure_auth_users(conn: AsyncConnection, *, supabase_url: str, service_key: str) -> dict[str, str]:
    """Create/refresh demo Auth users with the fixture UUIDs. Prefers the GoTrue admin API; falls back to direct
    SQL into auth.* (local/CI only) when no service-role key is configured. Returns {key: how}."""
    out: dict[str, str] = {}
    if service_key:
        import httpx

        headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        async with httpx.AsyncClient(base_url=supabase_url.rstrip("/"), headers=headers, timeout=20) as http:
            for u in USERS:
                env_pw = _env(u.password_env) if u.password_env else None
                meta = {"full_name": u.full_name, "initials": u.initials}
                r = await http.get(f"/auth/v1/admin/users/{u.id}")
                if r.status_code == 200:
                    if env_pw:
                        rr = await http.put(
                            f"/auth/v1/admin/users/{u.id}",
                            json={"password": env_pw, "email_confirm": True, "user_metadata": meta},
                        )
                        rr.raise_for_status()
                    out[u.key] = "exists"
                    continue
                body = {
                    "id": u.id,
                    "email": u.email,
                    "password": env_pw or secrets.token_urlsafe(24),
                    "email_confirm": True,
                    "user_metadata": meta,
                    "app_metadata": {"demo": True},
                }
                r = await http.post("/auth/v1/admin/users", json=body)
                if r.status_code in (409, 422) and u.email.endswith("@demo.ledgic.dev"):
                    # Same email under another id (e.g. created by hand): replace it so fixture UUIDs hold.
                    row = await one(
                        conn, "select id::text as id from auth.users where email = %s", (u.email,)
                    )
                    if row and row["id"] != u.id:
                        (await http.delete(f"/auth/v1/admin/users/{row['id']}")).raise_for_status()
                        r = await http.post("/auth/v1/admin/users", json=body)
                if r.status_code >= 400:
                    raise RuntimeError(f"GoTrue admin create {u.email} failed: {r.status_code} {r.text}")
                out[u.key] = "created"
        return out

    log.warning("SUPABASE_SERVICE_ROLE_KEY not set: inserting demo users directly into auth.* (local only)")
    for u in USERS:
        env_pw = _env(u.password_env) if u.password_env else None
        pw = env_pw or secrets.token_urlsafe(24)
        await conn.execute(
            "insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, "
            " raw_app_meta_data, raw_user_meta_data, created_at, updated_at, confirmation_token, recovery_token, "
            " email_change, email_change_token_new) "
            "values ('00000000-0000-0000-0000-000000000000', %s, 'authenticated', 'authenticated', %s, "
            " extensions.crypt(%s, extensions.gen_salt('bf')), now(), %s, %s, now(), now(), '', '', '', '') "
            "on conflict (id) do update set encrypted_password = case when %s then excluded.encrypted_password "
            " else auth.users.encrypted_password end",
            (
                u.id,
                u.email,
                pw,
                J({"provider": "email", "providers": ["email"], "demo": True}),
                J({"full_name": u.full_name, "initials": u.initials}),
                bool(env_pw),
            ),
        )
        await conn.execute(
            "insert into auth.identities (id, user_id, provider_id, provider, identity_data, created_at, updated_at) "
            "values (%s, %s, %s, 'email', %s, now(), now()) on conflict do nothing",
            (u.id, u.id, u.id, J({"sub": u.id, "email": u.email, "email_verified": True})),
        )
        out[u.key] = "sql"
    return out


# ---------------------------------------------------------------------------------------- seed
async def seed(
    today: date | None = None,
    *,
    reset: bool = False,
    with_auth: bool = True,
    with_eval: bool = True,
    history_per_day: int = HISTORY_PER_DAY,
) -> dict[str, Any]:
    from app.config import get_settings
    from app.db.pool import connection

    settings = get_settings()
    tz = ZoneInfo("America/New_York")
    today = today or datetime.now(tz).date()
    cat = build_catalog(today)
    report: dict[str, Any] = {"today": today.isoformat()}

    async with connection() as conn:
        await conn.execute("set local statement_timeout = 0")
        if reset:
            if await one(conn, "select id from public.orgs where id = %s", (ORG_ID,)):
                report["purged"] = await val(conn, "select public.demo_purge_org(%s, false)", (ORG_ID,))
            await conn.commit()

        # org, settings, policy
        org = cat.org
        await upsert(
            conn,
            "orgs",
            [
                {
                    "id": ORG_ID,
                    "slug": org["slug"],
                    "name": org["name"],
                    "is_demo": True,
                    "timezone": org["timezone"],
                }
            ],
            "id",
            ["slug", "name", "is_demo", "timezone"],
        )
        await upsert(
            conn, "org_settings", [{"org_id": ORG_ID, **POLICY, "updated_at": datetime.now(tz)}], "org_id"
        )
        await upsert(
            conn,
            "tolerance_policies",
            [
                {
                    "id": stable_uuid("tolerance_policy", "default"),
                    "org_id": ORG_ID,
                    **TOLERANCE,
                    "effective_from": datetime(2025, 1, 1, tzinfo=tz),
                    "created_by": None,
                }
            ],
            "id",
            ["pct", "abs_amount"],
        )
        await conn.commit()

        # users
        if with_auth:
            report["auth"] = await ensure_auth_users(
                conn, supabase_url=settings.supabase_url, service_key=settings.supabase_service_role_key
            )
            await conn.commit()
        existing = {
            r["id"]
            for r in await all_(
                conn,
                "select id::text as id from auth.users where id = any(%s::uuid[])",
                ([u.id for u in USERS],),
            )
        }
        await upsert(
            conn,
            "profiles",
            [
                {"user_id": u.id, "full_name": u.full_name, "initials": u.initials}
                for u in USERS
                if u.id in existing
            ],
            "user_id",
        )
        await upsert(
            conn,
            "memberships",
            [{"org_id": ORG_ID, "user_id": u.id, "role": u.role} for u in USERS if u.id in existing],
            "org_id, user_id",
            ["role"],
        )
        report["users"] = len(existing)

        # master data
        m = master_rows(cat)
        await upsert(conn, "entities", m["entities"], "id")
        await upsert(conn, "locations", m["locations"], "id")
        await upsert(conn, "gl_accounts", m["gl_accounts"], "id")
        await upsert(conn, "vendors", m["vendors"], "id")
        await upsert(conn, "vendor_aliases", m["vendor_aliases"], "vendor_id, alias", [])
        await upsert(conn, "items", m["items"], "id", ["item_key", "description", "uom", "default_gl"])
        await upsert(conn, "contracts", m["contracts"], "id")
        await upsert(
            conn,
            "contract_prices",
            m["contract_prices"],
            "contract_id, item_id",
            ["uom", "unit_price", "clause_ref"],
        )
        await upsert(
            conn, "integrations", m["integrations"], "org_id, provider, entity_id", ["status", "config"]
        )
        await conn.commit()

        # hero POs / GRNs for today (replay re-upserts them by po_number before release)
        pos, po_lines, grns, grn_lines = [], [], [], []
        for d in hero_docs(cat, today):
            if d.po:
                p = d.po
                pos.append(
                    {
                        "id": p["id"],
                        "org_id": ORG_ID,
                        "entity_id": cat.entity(p["entity_n"]).id,
                        "location_id": p["location_id"],
                        "vendor_id": p["vendor_id"],
                        "po_number": p["po_number"],
                        "status": "open",
                        "ordered_at": datetime.fromisoformat(p["ordered_at"]),
                        "source": p.get("source", "quickbooks"),
                        "total": Decimal(p["total"]),
                    }
                )
                po_lines += [
                    {
                        "po_id": p["id"],
                        "line_no": ln["line_no"],
                        "item_id": ln["item_id"],
                        "description": ln["description"],
                        "qty": Decimal(ln["qty"]),
                        "uom": ln["uom"],
                        "unit_price": Decimal(ln["unit_price"]),
                        "amount": Decimal(ln["amount"]),
                    }
                    for ln in p["lines"]
                ]
            if d.grn:
                g = d.grn
                grns.append(
                    {
                        "id": g["id"],
                        "org_id": ORG_ID,
                        "po_id": g["po_id"],
                        "grn_number": g["grn_number"],
                        "received_at": datetime.fromisoformat(g["received_at"]),
                        "received_by": g["received_by"],
                        "source": "receiving_app",
                    }
                )
                grn_lines += [
                    {
                        "grn_id": g["id"],
                        "po_id": g["po_id"],
                        "line_no": ln["po_line_no"],
                        "qty_received": Decimal(ln["qty_received"]),
                        "uom": ln["uom"],
                    }
                    for ln in g["lines"]
                ]
        await insert_po_bundle(conn, pos, po_lines, grns, grn_lines)
        report["hero_pos"] = len(pos)
        await conn.commit()

        # coded back-history for GL kNN
        h = history_rows(cat, per_day=history_per_day)
        await insert_po_bundle(conn, h.pos, h.po_lines, h.grns, h.grn_lines)
        await upsert(conn, "documents", h.documents, "id")
        await upsert(conn, "invoices", h.invoices, "id")
        await insert_invoice_lines(conn, h.lines)
        report["history"] = {"invoices": len(h.invoices), "lines": len(h.lines), "pos": len(h.pos)}
        await conn.commit()

        # the two accepted prior short-pays
        for b in short_pay_bundle(cat):
            await insert_po_bundle(conn, [b["po"]], b["po_lines"], [b["grn"]], b["grn_lines"])
            await upsert(conn, "documents", [b["document"]], "id")
            await upsert(conn, "invoices", [b["invoice"]], "id")
            await upsert(conn, "invoice_fields", b["fields"], "invoice_id, field, version", [])
            await insert_invoice_lines(conn, b["lines"])
            await upsert(
                conn,
                "pipeline_runs",
                [b["run"]],
                "id",
                ["status", "current_stage", "started_at", "finished_at", "invoice_id"],
            )
            await upsert(
                conn,
                "match_results",
                [b["match"]],
                "invoice_id",
                ["verdict", "expected_total", "total_delta", "lines_verified", "lines_total"],
            )
            for ml in b["match_lines"]:
                await conn.execute(
                    "insert into public.match_line_results (id, match_result_id, invoice_line_id, po_line_id, grn_qty, "
                    " expected_unit_price, expected_source, contract_price_id, expected_amount, delta_amount, delta_pct, "
                    " allowed_amount, verdict, note) values (%s, %s, %s, "
                    " (select id from public.po_lines where po_id = %s and line_no = %s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "on conflict (id) do nothing",
                    (
                        ml["id"],
                        ml["match_result_id"],
                        ml["invoice_line_id"],
                        ml["po_id"],
                        ml["line_no"],
                        ml["grn_qty"],
                        ml["expected_unit_price"],
                        ml["expected_source"],
                        ml["contract_price_id"],
                        ml["expected_amount"],
                        ml["delta_amount"],
                        ml["delta_pct"],
                        ml["allowed_amount"],
                        ml["verdict"],
                        ml["note"],
                    ),
                )
            await upsert(
                conn,
                "exceptions",
                [b["exception"]],
                "id",
                ["status", "resolved_at", "amount_at_risk", "reason"],
            )
            await upsert(
                conn,
                "recommendations",
                [b["recommendation"]],
                "exception_id",
                ["action", "pay_amount", "hold_amount", "confidence", "reasons"],
            )
            await upsert(conn, "approvals", [b["approval"]], "id", [])
            await upsert(
                conn,
                "erp_postings",
                [b["posting"]],
                "invoice_id, system",
                ["status", "external_id", "posted_at"],
            )
            has_events = await (
                await conn.execute(
                    "select 1 from public.pipeline_events where run_id = %s limit 1", (b["run"]["id"],)
                )
            ).fetchone()
            if not has_events:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        "insert into public.pipeline_events (org_id, run_id, stage, status, at, duration_ms, summary, detail) "
                        "values (%s, %s, %s, %s, %s, %s, %s, %s)",
                        [
                            (ORG_ID, b["run"]["id"], st, status, at, dur, summ, J(det))
                            for st, status, at, dur, summ, det in b["events"]
                        ],
                    )
            has_audit = await (
                await conn.execute(
                    "select 1 from public.audit_log where org_id = %s and entity_type = 'approval' and entity_id = %s",
                    (ORG_ID, b["approval"]["id"]),
                )
            ).fetchone()
            if not has_audit:
                for actor_type, actor_id, action, etype, eid, before, after, at in b["audit"]:
                    await conn.execute(
                        "insert into public.audit_log (org_id, at, actor_type, actor_id, action, entity_type, entity_id, "
                        " before, after) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            ORG_ID,
                            at,
                            actor_type,
                            actor_id,
                            action,
                            etype,
                            eid,
                            J(before) if before else None,
                            J(after),
                        ),
                    )
        report["prior_short_pays"] = 2
        await conn.commit()

        # prompt version + eval history
        weeks = week_starts(today)
        await upsert(
            conn,
            "prompt_versions",
            [
                {
                    "id": PROMPT_VERSION,
                    "model": LLM_MODEL,
                    "deployed_at": datetime.combine(weeks[0] + timedelta(days=1), time(15, 0), tzinfo=tz),
                    "notes": "Initial extraction prompt (structured outputs, per-field confidence + bbox)",
                }
            ],
            "id",
            ["model", "notes"],
        )
        if with_eval:
            rows = eval_rows(cat)
            await upsert(
                conn,
                "eval_runs",
                rows,
                "org_id, week_start",
                ["prompt_version", "sample_size", "fields_labeled", "fields_correct", "by_field"],
            )
            report["eval_weeks"] = [
                (r["week_start"].isoformat(), r["fields_correct"], r["fields_labeled"]) for r in rows
            ]
        await conn.commit()

        await conn.execute("select public.refresh_kpis()")
        await conn.commit()

        counts = await (
            await conn.execute(
                "select (select count(*) from public.locations where org_id = %(o)s) as locations, "
                " (select count(*) from public.entities where org_id = %(o)s) as entities, "
                " (select count(*) from public.vendors where org_id = %(o)s) as vendors, "
                " (select count(*) from public.items where org_id = %(o)s) as items, "
                " (select count(*) from public.contract_prices cp join public.contracts c on c.id = cp.contract_id "
                "   where c.org_id = %(o)s) as contract_prices, "
                " (select count(*) from public.invoices where org_id = %(o)s) as invoices, "
                " (select count(*) from public.invoice_lines l join public.invoices i on i.id = l.invoice_id "
                "   where i.org_id = %(o)s) as invoice_lines, "
                " (select count(*) from public.purchase_orders where org_id = %(o)s) as purchase_orders, "
                " (select count(*) from public.memberships where org_id = %(o)s) as memberships, "
                " (select count(*) from public.eval_runs where org_id = %(o)s) as eval_runs, "
                " (select count(*) from public.approvals where org_id = %(o)s and action = 'short_pay') as short_pays",
                {"o": ORG_ID},
            )
        ).fetchone()
        report["counts"] = dict(counts or {})
    return report


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m app.demo.seed", description=__doc__.split("\n\n")[0])
    ap.add_argument("--reset", action="store_true", help="purge the demo org (demo_purge_org) before seeding")
    ap.add_argument(
        "--today", type=date.fromisoformat, default=None, help="seed as of this date (YYYY-MM-DD)"
    )
    ap.add_argument(
        "--no-auth", action="store_true", help="skip creating Auth users (they must already exist)"
    )
    ap.add_argument("--no-eval", action="store_true", help="skip the 12-week eval computation")
    ap.add_argument("--history-per-day", type=int, default=HISTORY_PER_DAY)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    async def run() -> dict[str, Any]:
        from app.db.pool import close_pool, open_pool

        await open_pool()
        try:
            return await seed(
                args.today,
                reset=args.reset,
                with_auth=not args.no_auth,
                with_eval=not args.no_eval,
                history_per_day=args.history_per_day,
            )
        finally:
            await close_pool()

    if sys.platform == "win32":  # psycopg async needs a selector loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    report = asyncio.run(run())
    for k, v in report.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
