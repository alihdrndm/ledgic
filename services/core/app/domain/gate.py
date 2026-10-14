"""Extraction confidence gate (01 §4.3) and calibration fallback (06 §5.3).

Field keys: header fields `vendor`, `invoice_number`, `invoice_date`, `total`, `po_ref`, `terms`
(aliases `vendor_name`, `po_reference` accepted) and line fields `lines[<i>].qty|unit_price|amount`
with a 0-based index (`lines[1].qty` is line 2). Other keys (due_date, tax, uom, ...) carry weight 0 and
are ignored by the document confidence. Omit absent optional fields (e.g. no PO printed).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal

from .money import D, Numberish, conf, fmt_conf, fmt_money, fmt_qty, fmt_unit_price, quantize

DEFAULT_GATE = Decimal("0.90")
DEFAULT_FLOOR = Decimal("0.75")
LINE_TOLERANCE = Decimal("0.01")
TOTAL_TOLERANCE = Decimal("0.02")
_MIN_CONF = Decimal("0.000001")

HEADER_WEIGHTS: dict[str, int] = {
    "vendor": 3,
    "invoice_number": 3,
    "invoice_date": 2,
    "total": 3,
    "po_ref": 2,
    "terms": 1,
}
LINE_WEIGHTS: dict[str, int] = {"qty": 1, "unit_price": 1, "amount": 1}
REQUIRED_HEADER = frozenset({"vendor", "invoice_number", "invoice_date", "total"})
ALIASES = {"vendor_name": "vendor", "po_reference": "po_ref"}
_LINE_KEY = re.compile(r"^lines\[(\d+)\]\.(\w+)$")

FIELD_LABELS = {
    "vendor": "vendor",
    "invoice_number": "invoice number",
    "invoice_date": "invoice date",
    "total": "total",
    "po_ref": "PO reference",
    "terms": "terms",
    "qty": "quantity",
    "unit_price": "unit price",
    "amount": "amount",
}

Agreement = Literal["agree", "missing", "disagree"]
_AGREE_FACTOR = {"agree": Decimal("1.0"), "missing": Decimal("0.8"), "disagree": Decimal("0.6")}


def canonical_key(key: str) -> str:
    return ALIASES.get(key, key)


def field_weight(key: str) -> int:
    key = canonical_key(key)
    m = _LINE_KEY.match(key)
    if m:
        return LINE_WEIGHTS.get(m.group(2), 0)
    return HEADER_WEIGHTS.get(key, 0)


def is_required(key: str) -> bool:
    key = canonical_key(key)
    m = _LINE_KEY.match(key)
    if m:
        return m.group(2) in LINE_WEIGHTS
    return key in REQUIRED_HEADER


def field_label(key: str) -> str:
    """'lines[1].qty' -> 'quantity, line 2'; 'invoice_number' -> 'invoice number'."""
    key = canonical_key(key)
    m = _LINE_KEY.match(key)
    if m:
        return f"{FIELD_LABELS.get(m.group(2), m.group(2))}, line {int(m.group(1)) + 1}"
    return FIELD_LABELS.get(key, key.replace("_", " "))


def calibrate_fallback(model_conf: Numberish | float, agree: Agreement) -> Decimal:
    """Pre-isotonic fallback: c = model_conf × (1.0 agree | 0.8 missing | 0.6 disagree), 3 dp."""
    return quantize(conf(model_conf) * _AGREE_FACTOR[agree], 3)


def doc_confidence(fields: Mapping[str, Numberish | float]) -> Decimal:
    """Weighted geometric mean exp(Σ wᵢ·ln cᵢ / Σ wᵢ) over weighted fields, rounded to 3 dp."""
    num = Decimal(0)
    den = 0
    with localcontext() as ctx:
        ctx.prec = 28
        for key, c in fields.items():
            w = field_weight(key)
            if w == 0:
                continue
            cv = min(max(conf(c), _MIN_CONF), Decimal(1))
            num += w * cv.ln()
            den += w
        if den == 0:
            return Decimal("0.000")
        return quantize((num / den).exp(), 3)


@dataclass(frozen=True)
class LineAmounts:
    qty: Decimal
    unit_price: Decimal
    amount: Decimal

    @classmethod
    def of(cls, qty: Numberish, unit_price: Numberish, amount: Numberish) -> LineAmounts:
        return cls(D(qty), D(unit_price), D(amount))


@dataclass(frozen=True)
class ArithmeticResult:
    failing_lines: tuple[int, ...]  # 0-based indexes with |qty×unit − amount| > 0.01
    lines_sum: Decimal
    total_delta: Decimal | None  # Σ amounts + tax + freight − total (None when total unknown)
    total_ok: bool

    @property
    def passes(self) -> bool:
        return not self.failing_lines and self.total_ok


def check_arithmetic(
    lines: Sequence[LineAmounts],
    *,
    tax: Numberish | None = None,
    freight: Numberish | None = None,
    total: Numberish | None = None,
) -> ArithmeticResult:
    failing = tuple(
        i for i, ln in enumerate(lines) if abs(ln.qty * ln.unit_price - ln.amount) > LINE_TOLERANCE
    )
    lines_sum = sum((ln.amount for ln in lines), Decimal(0))
    if total is None:
        return ArithmeticResult(failing, lines_sum, None, True)
    delta = lines_sum + D(tax or 0) + D(freight or 0) - D(total)
    return ArithmeticResult(failing, lines_sum, delta, abs(delta) <= TOTAL_TOLERANCE)


@dataclass(frozen=True)
class CrossCheck:
    field: str
    implied_value: Decimal
    agrees: bool
    text: str  # '$125.00 ÷ $31.25 unit = 4.0'


def cross_check_line(line: LineAmounts, part: str, *, index: int = 0) -> CrossCheck | None:
    """Recompute one line field from the other two. `agrees` = the read value satisfies the arithmetic."""
    agrees = abs(line.qty * line.unit_price - line.amount) <= LINE_TOLERANCE
    key = f"lines[{index}].{part}"
    if part == "qty":
        if line.unit_price == 0:
            return None
        implied = line.amount / line.unit_price
        text = f"{fmt_money(line.amount)} ÷ {fmt_unit_price(line.unit_price)} unit = {quantize(implied, 1)}"
        return CrossCheck(key, quantize(implied, 3), agrees, text)
    if part == "unit_price":
        if line.qty == 0:
            return None
        implied = line.amount / line.qty
        text = f"{fmt_money(line.amount)} ÷ {fmt_qty(line.qty)} qty = {fmt_unit_price(implied)}"
        return CrossCheck(key, quantize(implied, 4), agrees, text)
    if part == "amount":
        implied = line.qty * line.unit_price
        text = f"{fmt_qty(line.qty)} × {fmt_unit_price(line.unit_price)} = {fmt_money(implied)}"
        return CrossCheck(key, quantize(implied, 2), agrees, text)
    return None


def cross_check_total(
    lines: Sequence[LineAmounts],
    *,
    total: Numberish,
    tax: Numberish | None = None,
    freight: Numberish | None = None,
) -> CrossCheck:
    res = check_arithmetic(lines, tax=tax, freight=freight, total=total)
    implied = res.lines_sum + D(tax or 0) + D(freight or 0)
    text = (
        f"lines {fmt_money(res.lines_sum)} + tax {fmt_money(D(tax or 0))} + freight "
        f"{fmt_money(D(freight or 0))} = {fmt_money(implied)}"
    )
    return CrossCheck("total", implied, res.total_ok, text)


@dataclass(frozen=True)
class GateResult:
    doc_confidence: Decimal
    passes: bool
    doc_passes: bool
    floor_passes: bool
    arithmetic: ArithmeticResult | None
    flagged_fields: tuple[str, ...]  # required fields below the floor, lowest first
    cross_checks: tuple[CrossCheck, ...]  # arithmetic explanations for flagged fields

    @property
    def needs_review(self) -> bool:
        return not self.passes


def evaluate_gate(
    fields: Mapping[str, Numberish | float],
    *,
    lines: Sequence[LineAmounts] = (),
    tax: Numberish | None = None,
    freight: Numberish | None = None,
    total: Numberish | None = None,
    gate: Numberish = DEFAULT_GATE,
    floor: Numberish = DEFAULT_FLOOR,
) -> GateResult:
    """gate passes ⇔ doc_conf ≥ gate ∧ min(required cᵢ) ≥ floor ∧ arithmetic checks pass.
    A confirming cross-check never overrides the gate — it is only shown to the reviewer."""
    canon = {canonical_key(k): conf(v) for k, v in fields.items()}
    dc = doc_confidence(canon)
    floor_d = D(floor)
    flagged = tuple(
        k
        for k, _ in sorted(
            ((k, v) for k, v in canon.items() if is_required(k) and v < floor_d), key=lambda kv: kv[1]
        )
    )
    arithmetic = (
        check_arithmetic(lines, tax=tax, freight=freight, total=total)
        if (lines or total is not None)
        else None
    )
    checks: list[CrossCheck] = []
    for key in flagged:
        m = _LINE_KEY.match(key)
        if m and int(m.group(1)) < len(lines):
            cc = cross_check_line(lines[int(m.group(1))], m.group(2), index=int(m.group(1)))
            if cc:
                checks.append(cc)
        elif key == "total" and total is not None:
            checks.append(cross_check_total(lines, total=total, tax=tax, freight=freight))
    doc_ok = dc >= D(gate)
    floor_ok = not flagged
    arith_ok = arithmetic.passes if arithmetic else True
    return GateResult(
        doc_confidence=dc,
        passes=doc_ok and floor_ok and arith_ok,
        doc_passes=doc_ok,
        floor_passes=floor_ok,
        arithmetic=arithmetic,
        flagged_fields=flagged,
        cross_checks=tuple(checks),
    )


def review_callout_title(flagged: Sequence[str]) -> str:
    """'One field needs confirmation — quantity, line 2' / '3 fields need confirmation'."""
    if len(flagged) == 1:
        return f"One field needs confirmation — {field_label(flagged[0])}"
    return f"{len(flagged)} fields need confirmation"


def review_callout_body(read_value: str, confidence: Numberish | float, check: CrossCheck | None) -> str:
    """'Model read 4 at confidence 0.71. Cross-check: $125.00 ÷ $31.25 unit = 4.0, so the arithmetic
    agrees with the smudged digit.'"""
    head = f"Model read {read_value} at confidence {fmt_conf(confidence)}."
    if check is None:
        return head
    tail = (
        "so the arithmetic agrees with the smudged digit."
        if check.agrees
        else "so the arithmetic does not agree — check the value."
    )
    return f"{head} Cross-check: {check.text}, {tail}"
