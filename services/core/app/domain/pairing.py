"""Invoice-line → PO-line pairing (06 §6): SKU, description similarity (+ optional embedding cosine),
UoM compatibility, Hungarian assignment on cost 1 − sim; pairs below the threshold stay unmatched.
Similarities are floats (they are scores, not money)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz, utils
from scipy.optimize import linear_sum_assignment

PAIR_THRESHOLD = 0.6

_UOM_ALIASES: dict[str, str] = {
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "#": "lb",
    "kg": "kg",
    "kgs": "kg",
    "kilo": "kg",
    "kilogram": "kg",
    "oz": "oz",
    "ounce": "oz",
    "cs": "cs",
    "case": "cs",
    "cases": "cs",
    "ca": "cs",
    "ea": "ea",
    "each": "ea",
    "unit": "ea",
    "units": "ea",
    "pc": "ea",
    "pcs": "ea",
    "piece": "ea",
    "bag": "bag",
    "bg": "bag",
    "bags": "bag",
    "bx": "box",
    "box": "box",
    "boxes": "box",
    "dz": "dz",
    "doz": "dz",
    "dozen": "dz",
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "l": "l",
    "lt": "l",
    "liter": "l",
    "litre": "l",
    "hr": "hr",
    "hour": "hr",
    "hours": "hr",
    "hrs": "hr",
    "mo": "mo",
    "month": "mo",
}
# Units that may legitimately be invoiced against one another (weight ↔ weight).
_COMPATIBLE_GROUPS = ({"lb", "kg", "oz"},)


def normalize_uom(uom: str | None) -> str | None:
    if not uom:
        return None
    u = uom.strip().lower().rstrip(".")
    return _UOM_ALIASES.get(u, u)


def uom_compatible(a: str | None, b: str | None) -> bool:
    """Unknown UoM on either side is compatible; otherwise equal after normalization or same group."""
    na, nb = normalize_uom(a), normalize_uom(b)
    if na is None or nb is None or na == nb:
        return True
    return any(na in g and nb in g for g in _COMPATIBLE_GROUPS)


@dataclass(frozen=True)
class PairLine:
    description: str
    uom: str | None = None
    sku: str | None = None


@dataclass(frozen=True)
class LinePair:
    invoice_index: int
    po_index: int
    similarity: float
    method: str  # 'sku' | 'description'


@dataclass(frozen=True)
class PairingResult:
    pairs: tuple[LinePair, ...]
    unmatched_invoice: tuple[int, ...]
    unmatched_po: tuple[int, ...]

    def po_for(self, invoice_index: int) -> int | None:
        for p in self.pairs:
            if p.invoice_index == invoice_index:
                return p.po_index
        return None


def description_similarity(a: str, b: str) -> float:
    return fuzz.token_set_ratio(a, b, processor=utils.default_process) / 100.0


def similarity_matrix(
    invoice_lines: Sequence[PairLine],
    po_lines: Sequence[PairLine],
    embedding_sim: Sequence[Sequence[float]] | None = None,
    embedding_weight: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (sim, is_sku) matrices of shape (n_invoice, n_po)."""
    n, m = len(invoice_lines), len(po_lines)
    sim = np.zeros((n, m))
    is_sku = np.zeros((n, m), dtype=bool)
    emb = np.asarray(embedding_sim, dtype=float) if embedding_sim is not None else None
    if emb is not None and emb.shape != (n, m):
        raise ValueError(f"embedding_sim must be {n}x{m}, got {emb.shape}")
    for i, il in enumerate(invoice_lines):
        for j, pl in enumerate(po_lines):
            if not uom_compatible(il.uom, pl.uom):
                continue
            if il.sku and pl.sku and il.sku.strip().upper() == pl.sku.strip().upper():
                sim[i, j] = 1.0
                is_sku[i, j] = True
                continue
            s = description_similarity(il.description, pl.description)
            if emb is not None:
                s = (1 - embedding_weight) * s + embedding_weight * float(np.clip(emb[i, j], 0.0, 1.0))
            sim[i, j] = s
    return sim, is_sku


def pair_lines(
    invoice_lines: Sequence[PairLine],
    po_lines: Sequence[PairLine],
    *,
    embedding_sim: Sequence[Sequence[float]] | None = None,
    embedding_weight: float = 0.5,
    threshold: float = PAIR_THRESHOLD,
) -> PairingResult:
    n, m = len(invoice_lines), len(po_lines)
    if n == 0 or m == 0:
        return PairingResult((), tuple(range(n)), tuple(range(m)))
    sim, is_sku = similarity_matrix(invoice_lines, po_lines, embedding_sim, embedding_weight)
    rows, cols = linear_sum_assignment(1.0 - sim)
    pairs: list[LinePair] = []
    for i, j in zip(rows.tolist(), cols.tolist(), strict=True):
        if sim[i, j] >= threshold:
            pairs.append(LinePair(i, j, round(float(sim[i, j]), 4), "sku" if is_sku[i, j] else "description"))
    paired_inv = {p.invoice_index for p in pairs}
    paired_po = {p.po_index for p in pairs}
    return PairingResult(
        pairs=tuple(sorted(pairs, key=lambda p: p.invoice_index)),
        unmatched_invoice=tuple(i for i in range(n) if i not in paired_inv),
        unmatched_po=tuple(j for j in range(m) if j not in paired_po),
    )
