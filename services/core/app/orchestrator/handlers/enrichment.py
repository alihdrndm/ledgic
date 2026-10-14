"""03 Enrichment (06 §6): vendor, PO, entity/location, line ↔ PO-line pairing, item, GL coding.

GL coding is kNN over the org's own coded history (same vendor + same item, k = 7, majority vote,
`predict_gl`), falling back to the item's default GL — no LLM involved.
Pairing uses description similarity + UoM compatibility + Hungarian assignment (`pair_lines`); item
embeddings are not used at runtime because invoice-line text would need a live embedding call.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from rapidfuzz import fuzz, utils

from app.domain import Neighbour, PairLine, pair_lines, predict_gl, resolve_vendor, uom_compatible
from app.repo import invoices as inv_repo
from app.repo import journal, master
from app.repo import runs as runs_repo

from ..context import RunRow, StageContext
from ..stages import Stage
from ..transitions import FatalStageError, Transition
from .common import plural

ITEM_MATCH_THRESHOLD = 85
_items_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


async def org_items_cached(ctx: StageContext, org_id: str) -> list[dict[str, Any]]:
    hit = _items_cache.get(org_id)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    items = await master.org_items(ctx.conn, org_id)
    _items_cache[org_id] = (time.monotonic() + 300, items)
    return items


def best_item(description: str, uom: str | None, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for it in items:
        if not uom_compatible(uom, it["uom"]):
            continue
        s = fuzz.token_set_ratio(description, it["description"], processor=utils.default_process)
        if best is None or s > best[0]:
            best = (s, it)
    return best[1] if best and best[0] >= ITEM_MATCH_THRESHOLD else None


async def pair_with_po(ctx: StageContext, invoice_id: str, po_id: str | None) -> tuple[int, int]:
    """(Re)pair invoice lines to the PO's lines; sets po_line_id + item_id. Returns (paired, total)."""
    lines = await inv_repo.lines(ctx.conn, invoice_id)
    if not po_id:
        await inv_repo.update_lines(
            ctx.conn, [(ln["sid"], {"po_line_id": None}) for ln in lines if ln["po_line_id"] is not None]
        )
        return 0, len(lines)
    pls = await master.po_lines(ctx.conn, po_id)
    res = pair_lines(
        [PairLine(ln["description"], ln["uom"]) for ln in lines],
        [PairLine(pl["description"], pl["uom"]) for pl in pls],
    )
    updates: list[tuple[str, dict]] = []
    for i, ln in enumerate(lines):
        j = res.po_for(i)
        if j is None:
            updates.append((ln["sid"], {"po_line_id": None}))
        else:
            pl = pls[j]
            updates.append((ln["sid"], {"po_line_id": pl["id"], "item_id": pl["item_id"] or ln["item_id"]}))
    await inv_repo.update_lines(ctx.conn, updates)
    return len(res.pairs), len(lines)


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    conn = ctx.conn
    if not run.invoice_id:
        raise FatalStageError("enrichment without invoice")
    inv = await inv_repo.get_invoice(conn, run.invoice_id)
    if inv is None:
        raise FatalStageError("invoice missing")
    fields = await inv_repo.latest_fields(conn, run.invoice_id)
    doc = await runs_repo.get_document(conn, run.document_id)
    meta = (doc or {}).get("source_meta") or {}
    now = ctx.now()

    # ---- vendor
    name = (fields.get("vendor_name") or {}).get("value")
    records = await master.vendor_records(conn, run.org_id)
    res = resolve_vendor(name, records)
    vendor_id = res.vendor_id
    method = res.method
    if vendor_id is None and name:
        remit = {
            "name": (fields.get("remit_to_name") or {}).get("value") or name,
            "address": (fields.get("remit_to_address") or {}).get("value"),
        }
        v = await master.create_unverified_vendor(conn, org_id=run.org_id, name=name, remit=remit, at=now)
        vendor_id = str(v["id"])
        await journal.write_audit(
            conn,
            org_id=run.org_id,
            actor_type="core",
            actor_id="enrichment",
            action="vendor.created_unverified",
            entity_type="vendor",
            entity_id=vendor_id,
            after={"display_name": name, "source_invoice": run.invoice_id},
            at=now,
        )
    vendor = await master.get_vendor(conn, vendor_id) if vendor_id else None

    # ---- PO (exact reference only; candidates feed the no-PO recommendation in match)
    po = None
    po_ref = (fields.get("po_reference") or {}).get("value")
    if po_ref:
        po = await master.po_by_number(conn, run.org_id, po_ref)
        if po is not None and vendor_id and str(po["vendor_id"]) != vendor_id:
            po = None
    po_id = str(po["id"]) if po else None

    # ---- entity / location
    location_id = (
        str(po["location_id"])
        if po
        else (meta.get("location_id") or (str(inv["location_id"]) if inv["location_id"] else None))
    )
    loc = await master.location(conn, location_id) if location_id else None
    entity_id = str(loc["entity_id"]) if loc else (str(po["entity_id"]) if po else None)

    # ---- pairing + items
    paired, n_lines = await pair_with_po(ctx, run.invoice_id, po_id)
    lines = await inv_repo.lines(conn, run.invoice_id)
    items = None
    for ln in lines:
        if ln["item_id"] is None:
            items = items if items is not None else await org_items_cached(ctx, run.org_id)
            it = best_item(ln["description"], ln["uom"], items)
            if it:
                await inv_repo.update_line(conn, ln["sid"], item_id=it["id"])
                ln["item_id"] = it["id"]

    # ---- GL coding
    item_ids = [str(ln["item_id"]) for ln in lines if ln["item_id"]]
    item_rows = await master.items_by_ids(conn, item_ids)
    neighbours = await master.gl_neighbours(conn, run.org_id, vendor_id, item_ids, now) if vendor_id else {}
    coded = 0
    gl_labels: dict[str, int] = {}
    gl_cache: dict[str, dict | None] = {}
    gl_updates: list[tuple[str, dict]] = []
    for ln in lines:
        iid = str(ln["item_id"]) if ln["item_id"] else None
        nb = [Neighbour(r["gl_code"], Decimal(str(r["similarity"]))) for r in neighbours.get(iid or "", [])]
        pred = predict_gl(nb, item_default_gl=(item_rows.get(iid) or {}).get("default_gl") if iid else None)
        if pred.gl_code is None:
            continue
        if pred.gl_code not in gl_cache:
            gl_cache[pred.gl_code] = await master.gl_by_number(conn, run.org_id, entity_id, pred.gl_code)
        gl = gl_cache[pred.gl_code]
        if gl is None:
            continue
        gl_updates.append((ln["sid"], {"gl_account_id": gl["id"], "gl_confidence": pred.confidence}))
        coded += 1
        label = f"{gl['number']} {gl['name']}"
        gl_labels[label] = gl_labels.get(label, 0) + 1

    await inv_repo.update_lines(conn, gl_updates)
    await inv_repo.update_invoice(
        conn,
        run.invoice_id,
        vendor_id=vendor_id,
        po_id=po_id,
        location_id=location_id,
        entity_id=entity_id,
        status="enriched",
    )
    vendor_name = vendor["display_name"] if vendor else (name or "unknown vendor")
    await journal.write_audit(
        conn,
        org_id=run.org_id,
        actor_type="core",
        actor_id="enrichment",
        action="invoice.enriched",
        entity_type="invoice",
        entity_id=run.invoice_id,
        after={
            "vendor_id": vendor_id,
            "vendor_method": method,
            "po_id": po_id,
            "location_id": location_id,
            "entity_id": entity_id,
            "lines_paired": paired,
            "lines_coded": coded,
        },
        at=now,
    )
    po_text = po["po_number"] if po else "no PO"
    sub = (
        f"{paired} of {n_lines} lines paired" if po else "no PO referenced"
    ) + f" · GL predicted on {coded}"
    if loc:
        sub = f"{loc['entity_name']} · loc {loc['code']} · " + sub
    return Transition.advance(
        Stage.SCREENING,
        f"Enriched — {vendor_name}, {po_text}",
        sub,
        detail={
            "vendor_id": vendor_id,
            "vendor_method": method,
            "vendor_confidence": res.confidence,
            "po_id": po_id,
            "po_linked": po_id is not None,
            "lines_paired": paired,
            "lines_total": n_lines,
            "gl_coded": coded,
            "gl": max(gl_labels, key=gl_labels.get) if gl_labels else None,
            "new_vendor": method == "new",
            "summary_lines": plural(n_lines, "line"),
        },
    )
