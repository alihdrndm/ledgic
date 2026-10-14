"""02 Extraction: fields + per-field confidence → invoice, invoice_fields, invoice_lines → confidence gate.

Sources (invoices.extraction_mode):
* `simulated` — replay/backfill documents: the corpus' `PlannedDoc.simulated_extraction`, carried in
  `pipeline_runs.context.fixture` and dropped from the context once persisted ($0, no LLM call).
* `recorded`  — hero documents: the recorded hero output (the planner's copy, rebased to the demo day
  so dates and photo bounding boxes match the rendered file).
* `live`      — uploads: `app.ai.extract_document` (gpt-4.1-mini, metered, BYOK or daily budget). When
  no live call is possible the run parks in extraction review with empty fields
  ("AI budget reached — enter fields manually").

Calibration: Ledgic has no second reading (Textract was dropped, DECISIONS D2), so the model's
confidence is treated as calibrated (`calibrate_fallback(c, 'agree')` = c). The 0.8 "missing" factor
would cap every field at 0.8 and no document could ever pass the 0.90 gate.
"""

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import Any

from app.domain import LineAmounts, bank_fingerprint, calibrate_fallback, evaluate_gate
from app.domain.money import fmt_conf
from app.repo import invoices as inv_repo
from app.repo import journal
from app.repo import runs as runs_repo

from ..context import RunRow, StageContext
from ..stages import Stage
from ..transitions import FatalStageError, StageError, Transition
from .common import dec, invoice_id_for, plural, to_date

log = logging.getLogger("ledgic.orchestrator.extraction")

HEADER = (
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
    "remit_to_name",
    "remit_to_address",
)
OPTIONAL_GATE = ("po_reference", "terms")
GATE_HEADER = ("vendor_name", "invoice_number", "invoice_date", "total", "po_reference", "terms")
BUDGET_REASON = "AI budget reached — enter fields manually"


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    from app.ai.schemas import normalize_extraction

    return normalize_extraction(data).model_dump(mode="json")


def modeled_extraction_ms(document_id: str, channel: str, pages: int) -> int:
    """Latency model for simulated/recorded extraction (what a gpt-4.1-mini vision call takes)."""
    h = int(hashlib.sha256(f"x:{document_id}".encode()).hexdigest()[:8], 16)
    base = 2600 if channel != "photo" else 3600
    return base + 900 * max(0, pages - 1) + h % 2400


async def _live(
    ctx: StageContext, run: RunRow, doc: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Live extraction for uploads. Returns (None, meta) when the budget/key does not allow a call."""
    from app.ai import ExtractionUnavailable, extract_document
    from app.repo.storage import download_object

    try:
        blob = await download_object(doc["storage_path"])
    except Exception as e:  # storage hiccup → retry
        raise StageError(f"could not download {doc['storage_path']}: {e}") from e
    try:
        out = await extract_document(
            [blob], mime=doc["mime"], api_key=ctx.byok_key, org_id=run.org_id, run_id=run.id
        )
    except ExtractionUnavailable as e:
        return None, {"fallback_reason": str(e)}
    meta = {
        "model": out.model,
        "prompt_version": out.prompt_version,
        "cost_usd": out.cost_usd,
        "mode": out.mode,
        "fallback_reason": out.fallback_reason,
        "billing": "byok" if ctx.byok_key else "owner",
    }
    if out.mode != "live":
        return None, meta
    return out.result.model_dump(mode="json"), meta


def _fv(data: dict[str, Any], key: str) -> dict[str, Any]:
    return data.get(key) or {"value": None, "confidence": 0.0, "bbox": None}


def gate_inputs(data: dict[str, Any]) -> tuple[dict[str, float], list[LineAmounts], bool]:
    """Field confidences for the gate (null optional fields skipped; null required fields count as 0)
    and the line amounts for the arithmetic check. Returns (fields, lines, all_lines_complete)."""
    fields: dict[str, float] = {}
    for k in GATE_HEADER:
        fv = _fv(data, k)
        if fv["value"] is None and k in OPTIONAL_GATE:
            continue
        fields[k] = float(calibrate_fallback(fv["confidence"] if fv["value"] is not None else 0, "agree"))
    amounts: list[LineAmounts] = []
    complete = True
    for i, ln in enumerate(data.get("lines") or []):
        vals = {}
        for part in ("qty", "unit_price", "amount"):
            fv = ln.get(part) or {"value": None, "confidence": 0}
            v = dec(fv.get("value"))
            vals[part] = v
            fields[f"lines[{i}].{part}"] = float(
                calibrate_fallback(fv["confidence"] if v is not None else 0, "agree")
            )
        if None in vals.values():
            complete = False
        else:
            amounts.append(LineAmounts(vals["qty"], vals["unit_price"], vals["amount"]))
    return fields, amounts, complete


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    conn = ctx.conn
    doc = await runs_repo.get_document(conn, run.document_id)
    if doc is None:
        raise FatalStageError("document missing")
    meta = doc.get("source_meta") or {}
    mode = run.context.get("extraction_mode") or meta.get("extraction_mode") or "live"
    fixture = run.context.get("fixture")
    pages = int(doc.get("page_count") or 1)
    info: dict[str, Any] = {"model": None, "prompt_version": "p-1"}
    duration: int | None = None
    budget_blocked = False

    if fixture is not None and mode in ("simulated", "recorded"):
        data = _normalize(fixture)
        info["model"] = "gpt-4.1-mini" if mode == "recorded" else None
        duration = modeled_extraction_ms(run.document_id, doc["channel"], pages)
    else:
        mode = "live"
        live, info2 = await _live(ctx, run, doc)
        info.update(info2)
        if live is None:
            budget_blocked = True
            data = _normalize({"lines": []})
        else:
            data = live

    invoice_id = run.invoice_id or invoice_id_for(run.document_id)
    now = ctx.now()
    fields, amounts, complete = gate_inputs(data)
    tax, freight, total = (dec(_fv(data, k)["value"]) for k in ("tax", "freight", "total"))
    pol = ctx.policy
    gate = evaluate_gate(
        fields,
        lines=amounts,
        tax=tax,
        freight=freight,
        total=total,
        gate=pol["confidence_gate"],
        floor=pol["field_floor"],
    )
    lines = data.get("lines") or []
    passed = gate.passes and complete and bool(lines) and not budget_blocked and total is not None

    # bank details are never stored in clear: fingerprint + last 4 only
    routing, account = _fv(data, "bank_routing")["value"], _fv(data, "bank_account")["value"]
    bank_fp = bank_fingerprint(routing, account)

    await inv_repo.upsert_extracted_invoice(
        conn,
        invoice_id,
        run.org_id,
        run.document_id,
        invoice_number=_fv(data, "invoice_number")["value"],
        invoice_date=to_date(_fv(data, "invoice_date")["value"]),
        due_date=to_date(_fv(data, "due_date")["value"]),
        terms=_fv(data, "terms")["value"],
        currency=(_fv(data, "currency")["value"] or "USD")[:3].upper(),
        subtotal=dec(_fv(data, "subtotal")["value"]),
        tax=tax if tax is not None else Decimal(0),
        freight=freight if freight is not None else Decimal(0),
        total=total,
        status="extracted" if passed else "in_review",
        doc_confidence=gate.doc_confidence,
        gate_passed=passed,
        extraction_mode=mode,
        received_at=doc["received_at"],
        human_touches=0,
    )
    field_rows: list[dict[str, Any]] = []
    for key in HEADER:
        fv = _fv(data, key)
        c = Decimal(str(round(float(fv["confidence"]), 3))) if fv["value"] is not None else Decimal("0")
        field_rows.append(
            {
                "invoice_id": invoice_id,
                "field": key,
                "value": fv["value"],
                "confidence": calibrate_fallback(c, "agree"),
                "raw_confidence": c,
                "bbox": fv.get("bbox"),
                "source": "llm",
                "at": now,
            }
        )
    if bank_fp:
        field_rows.append(
            {
                "invoice_id": invoice_id,
                "field": "bank_details",
                "value": f"routing ••{str(routing)[-4:]} · account ••{str(account)[-4:]}",
                "confidence": Decimal(str(round(float(_fv(data, "bank_account")["confidence"]), 3))),
                "raw_confidence": None,
                "bbox": _fv(data, "bank_account").get("bbox"),
                "source": "llm",
                "at": now,
            }
        )
    await inv_repo.insert_fields(conn, field_rows)
    line_rows: list[dict[str, Any]] = []
    for i, ln in enumerate(lines, start=1):
        confs = {
            k: round(float((ln.get(k) or {}).get("confidence") or 0), 3)
            for k in ("description", "qty", "uom", "unit_price", "amount")
        }
        bboxes = {k: (ln.get(k) or {}).get("bbox") for k in confs if (ln.get(k) or {}).get("bbox")}
        line_rows.append(
            {
                "invoice_id": invoice_id,
                "line_no": i,
                "description": (ln.get("description") or {}).get("value") or f"Line {i}",
                "qty": dec((ln.get("qty") or {}).get("value")),
                "uom": (ln.get("uom") or {}).get("value"),
                "unit_price": dec((ln.get("unit_price") or {}).get("value")),
                "amount": dec((ln.get("amount") or {}).get("value")),
                "confidences": confs,
                "bboxes": bboxes or None,
            }
        )
    await inv_repo.insert_lines(conn, line_rows)
    if meta.get("skew_deg") is not None and doc.get("preprocessing") is None:
        from app.repo.sql import J

        await conn.execute(
            "update documents set preprocessing = %s where id = %s",
            (J({"skew_deg": meta["skew_deg"], "pages": pages}), run.document_id),
        )

    dc = gate.doc_confidence
    flagged = list(gate.flagged_fields)
    detail = {
        "gate_passed": passed,
        "doc_confidence": dc,
        "flagged_fields": flagged,
        "extraction_mode": mode,
        "model": info.get("model"),
        "prompt_version": info.get("prompt_version"),
        "line_count": len(lines),
        "cross_checks": [c.text for c in gate.cross_checks],
        "arithmetic_ok": gate.arithmetic.passes if gate.arithmetic else None,
    }
    if info.get("fallback_reason"):
        detail["fallback_reason"] = info["fallback_reason"]
    await journal.write_audit(
        conn,
        org_id=run.org_id,
        actor_type="agent",
        actor_id=f"extraction:{mode}",
        action="invoice.extracted",
        entity_type="invoice",
        entity_id=invoice_id,
        after={
            "doc_confidence": dc,
            "gate_passed": passed,
            "lines": len(lines),
            "mode": mode,
            "model": info.get("model"),
        },
        at=ctx.now(),
    )
    if mode == "live" and info.get("cost_usd") and not budget_blocked:
        detail["cost_usd"] = info["cost_usd"]

    ctx_patch: dict[str, Any] = {"extraction_mode": mode, "flagged": flagged}
    if bank_fp:
        ctx_patch["bank_fp"] = bank_fp
    summary = f"Extracted — {plural(len(lines), 'line item')}, conf {fmt_conf(dc)}"
    if passed:
        return Transition.advance(
            Stage.ENRICHMENT,
            summary,
            f"every field above the {fmt_conf(pol['confidence_gate'])} gate",
            detail=detail,
            context=ctx_patch,
            drop_context=("fixture",),
            duration_ms=duration,
            invoice_id=invoice_id,
        )
    if budget_blocked:
        ctx_patch["review_reason"] = BUDGET_REASON
        summary = "Extraction skipped — AI budget reached"
        sub = "fields to be entered manually"
    elif flagged:
        sub = (
            f"{plural(len(flagged), 'field')} below the {fmt_conf(pol['field_floor'])} floor — sent to review"
        )
    elif not gate.doc_passes:
        sub = f"document confidence below the {fmt_conf(pol['confidence_gate'])} gate — sent to review"
    else:
        sub = "arithmetic check failed — sent to review"
    return Transition.advance(
        Stage.REVIEW,
        summary,
        sub,
        detail=detail,
        context=ctx_patch,
        drop_context=("fixture",),
        duration_ms=duration,
        invoice_id=invoice_id,
    )
