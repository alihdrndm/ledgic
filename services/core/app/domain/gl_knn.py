"""GL prediction (06 §6): majority vote over the k nearest historical coded lines (caller supplies them,
e.g. from pgvector). confidence = vote share × mean similarity of the winning votes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from .money import conf, quantize

DEFAULT_K = 7
# Fallback confidences are fixed, documented constants (no model behind them).
ITEM_DEFAULT_CONFIDENCE = Decimal("0.500")
VENDOR_DEFAULT_CONFIDENCE = Decimal("0.300")

Source = Literal["knn", "item_default", "vendor_default", "none"]


@dataclass(frozen=True)
class Neighbour:
    gl_code: str
    similarity: Decimal | float


@dataclass(frozen=True)
class GlPrediction:
    gl_code: str | None
    confidence: Decimal
    source: Source
    votes: dict[str, int] = field(default_factory=dict, hash=False)


def predict_gl(
    neighbours: Sequence[Neighbour],
    *,
    item_default_gl: str | None = None,
    vendor_default_gl: str | None = None,
    k: int = DEFAULT_K,
) -> GlPrediction:
    top = sorted((n for n in neighbours if n.gl_code), key=lambda n: conf(n.similarity), reverse=True)[:k]
    if top:
        votes: dict[str, int] = {}
        sims: dict[str, Decimal] = {}
        for n in top:
            votes[n.gl_code] = votes.get(n.gl_code, 0) + 1
            sims[n.gl_code] = sims.get(n.gl_code, Decimal(0)) + conf(n.similarity)
        # majority; ties → higher summed similarity → lexical order for determinism
        winner = sorted(votes, key=lambda g: (-votes[g], -sims[g], g))[0]
        share = Decimal(votes[winner]) / Decimal(len(top))
        mean_sim = sims[winner] / votes[winner]
        return GlPrediction(winner, quantize(share * mean_sim, 3), "knn", votes)
    if item_default_gl:
        return GlPrediction(item_default_gl, ITEM_DEFAULT_CONFIDENCE, "item_default")
    if vendor_default_gl:
        return GlPrediction(vendor_default_gl, VENDOR_DEFAULT_CONFIDENCE, "vendor_default")
    return GlPrediction(None, Decimal("0.000"), "none")
