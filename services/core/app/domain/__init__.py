"""Ledgic deterministic domain logic: pure functions over Decimal, no I/O, no database access."""

from .approval import ApprovalCheck, can_decide, required_role
from .duplicates import DupInvoice, DuplicateScore, DupLine, best_match, normalize_invoice_number
from .duplicates import score as duplicate_score
from .fraud import FraudInputs, FraudResult, FraudSignal, bank_fingerprint
from .fraud import screen as fraud_screen
from .gate import (
    CrossCheck,
    GateResult,
    LineAmounts,
    calibrate_fallback,
    check_arithmetic,
    cross_check_line,
    cross_check_total,
    doc_confidence,
    evaluate_gate,
    review_callout_body,
    review_callout_title,
)
from .gl_knn import GlPrediction, Neighbour, predict_gl
from .match_engine import (
    ContractPrice,
    LineMatch,
    MatchLineInput,
    MatchResult,
    active_contract,
    item_short,
    match_invoice,
    match_line,
)
from .money import D, cents, fmt_money, fmt_pct, fmt_qty, fmt_unit_price
from .pairing import LinePair, PairingResult, PairLine, pair_lines, uom_compatible
from .qty import QtyResult, qty_check
from .recommend import PoCandidate, Recommendation, recommend, short_pay_confidence
from .templates import NO_RECOMMENDATION, ReasonBullet
from .tolerance import ToleranceResult, line_tolerance, tolerance_sentence
from .vendor_resolve import VendorRecord, VendorResolution, hash_tax_id, normalize_vendor_name, resolve_vendor

__all__ = [
    "NO_RECOMMENDATION",
    "ApprovalCheck",
    "ContractPrice",
    "CrossCheck",
    "D",
    "DupInvoice",
    "DupLine",
    "DuplicateScore",
    "FraudInputs",
    "FraudResult",
    "FraudSignal",
    "GateResult",
    "GlPrediction",
    "LineAmounts",
    "LineMatch",
    "LinePair",
    "MatchLineInput",
    "MatchResult",
    "Neighbour",
    "PairLine",
    "PairingResult",
    "PoCandidate",
    "QtyResult",
    "ReasonBullet",
    "Recommendation",
    "ToleranceResult",
    "VendorRecord",
    "VendorResolution",
    "active_contract",
    "bank_fingerprint",
    "best_match",
    "calibrate_fallback",
    "can_decide",
    "cents",
    "check_arithmetic",
    "cross_check_line",
    "cross_check_total",
    "doc_confidence",
    "duplicate_score",
    "evaluate_gate",
    "fmt_money",
    "fmt_pct",
    "fmt_qty",
    "fmt_unit_price",
    "fraud_screen",
    "hash_tax_id",
    "item_short",
    "line_tolerance",
    "match_invoice",
    "match_line",
    "normalize_invoice_number",
    "normalize_vendor_name",
    "pair_lines",
    "predict_gl",
    "qty_check",
    "recommend",
    "required_role",
    "resolve_vendor",
    "review_callout_body",
    "review_callout_title",
    "short_pay_confidence",
    "tolerance_sentence",
    "uom_compatible",
]
