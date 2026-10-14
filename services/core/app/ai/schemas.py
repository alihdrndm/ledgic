"""Pydantic mirror of `contracts/extraction.schema.json` (strict structured outputs).

Every property is required, extra keys are forbidden and nullability is expressed with unions, so the
strict JSON schema the Agents SDK sends to OpenAI is equivalent to the contract file
(tests/ai/test_schemas.py asserts this).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HEADER_FIELDS: tuple[str, ...] = (
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
    "bank_routing",
    "bank_account",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBox(_Strict):
    page: int = Field(description="1-based page index")
    x: float = Field(description="normalized 0..1 of rendered page")
    y: float = Field(description="normalized 0..1 of rendered page")
    w: float = Field(description="normalized 0..1 of rendered page")
    h: float = Field(description="normalized 0..1 of rendered page")


class FieldValue(_Strict):
    value: str | None
    confidence: float = Field(description="0..1 legibility/unambiguity; 0 when value is null")
    bbox: BBox | None

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return min(1.0, max(0.0, float(v)))


def _f(desc: str) -> Any:
    return Field(description=desc)


class ExtractedLine(_Strict):
    description: FieldValue = _f("Line description exactly as printed")
    qty: FieldValue = _f("Decimal string")
    uom: FieldValue = _f("Unit of measure copied literally (lb, cs, ea, gal)")
    unit_price: FieldValue = _f("Decimal string (up to 4 dp)")
    amount: FieldValue = _f("Decimal string")


class ExtractionResult(_Strict):
    """InvoiceExtraction (06 §5.1, flattened remit/bank per the contract)."""

    vendor_name: FieldValue = _f("Vendor name as printed")
    invoice_number: FieldValue = _f("Invoice number exactly as printed")
    invoice_date: FieldValue = _f("ISO date YYYY-MM-DD")
    due_date: FieldValue = _f("ISO date YYYY-MM-DD")
    terms: FieldValue = _f("Payment terms, e.g. 'Net 14'")
    po_reference: FieldValue = _f("Purchase order reference as printed, e.g. 'PO-RS-1866'")
    subtotal: FieldValue = _f("Decimal string, e.g. '491.60' (no currency symbol, no thousands separators)")
    tax: FieldValue = _f("Decimal string")
    freight: FieldValue = _f("Decimal string")
    total: FieldValue = _f("Decimal string")
    currency: FieldValue = _f("ISO 4217 code, e.g. 'USD'")
    remit_to_name: FieldValue = _f("Remit-to name")
    remit_to_address: FieldValue = _f("Remit-to address, single line")
    bank_routing: FieldValue = _f("Bank routing number (digits only)")
    bank_account: FieldValue = _f("Bank account number (digits only)")
    lines: list[ExtractedLine] = _f("One entry per printed line, in order; fees are lines too.")
    document_type: Literal["invoice", "credit_memo", "statement", "other"]
    multiple_invoices_detected: bool

    def gate_fields(self) -> dict[str, float]:
        """Field confidences keyed for `app.domain.gate.evaluate_gate` (null values omitted)."""
        out: dict[str, float] = {}
        for key in ("vendor_name", "invoice_number", "invoice_date", "total", "po_reference", "terms"):
            fv: FieldValue = getattr(self, key)
            if fv.value is not None:
                out[key] = fv.confidence
        for i, ln in enumerate(self.lines):
            for part in ("qty", "unit_price", "amount"):
                fv = getattr(ln, part)
                if fv.value is not None:
                    out[f"lines[{i}].{part}"] = fv.confidence
        return out


ExtractionResult.model_rebuild()


def normalize_extraction(data: dict[str, Any]) -> ExtractionResult:
    """Validate an extraction dict, accepting the corpus' `simulated_extraction` shape too
    (06 §5.1 nested `remit_to {name,address}` / `bank_details {routing,account}`, numeric values)."""
    d = dict(data)
    if "remit_to" in d:
        rt = d.pop("remit_to") or {}
        val = rt.get("value") or {}
        conf, bbox = rt.get("confidence", 0.0), rt.get("bbox")
        d.setdefault("remit_to_name", _fv(val.get("name"), conf, bbox))
        d.setdefault("remit_to_address", _fv(val.get("address"), conf, bbox))
    if "bank_details" in d:
        bd = d.pop("bank_details") or {}
        val = bd.get("value") or {}
        conf, bbox = bd.get("confidence", 0.0), bd.get("bbox")
        d.setdefault("bank_routing", _fv(val.get("routing"), conf, bbox))
        d.setdefault("bank_account", _fv(val.get("account"), conf, bbox))
    for key in HEADER_FIELDS:
        d.setdefault(key, {"value": None, "confidence": 0.0, "bbox": None})
        d[key] = _coerce(d[key])
    d["lines"] = [{k: _coerce(v) for k, v in ln.items()} for ln in d.get("lines", [])]
    d.setdefault("document_type", "invoice")
    d.setdefault("multiple_invoices_detected", False)
    for k in [k for k in d if k.startswith("$")]:
        d.pop(k)
    return ExtractionResult.model_validate(d)


def _fv(value: Any, conf: float, bbox: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {"value": None, "confidence": 0.0, "bbox": None}
    return {"value": str(value), "confidence": conf, "bbox": bbox}


def _coerce(fv: Any) -> Any:
    if not isinstance(fv, dict):
        return fv
    fv = dict(fv)
    v = fv.get("value")
    if v is not None and not isinstance(v, str):
        fv["value"] = str(v)
    if fv.get("value") is None:
        fv["confidence"] = 0.0 if fv.get("confidence") is None else fv["confidence"]
    return fv
