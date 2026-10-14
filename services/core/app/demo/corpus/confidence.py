"""Spec weighted geometric mean (01 §4.3), used only to author simulated confidences.

The domain package owns the real gate; this is a local copy so the corpus can hit authored
document confidences (heroes) without importing app.domain. Null fields are skipped.
"""

from __future__ import annotations

import math
from typing import Any

HEADER_WEIGHTS = {
    "vendor_name": 3,
    "invoice_number": 3,
    "invoice_date": 2,
    "total": 3,
    "po_reference": 2,
    "terms": 1,
}
LINE_WEIGHTS = {"qty": 1, "unit_price": 1, "amount": 1}


def weighted_fields(sim: dict[str, Any]) -> list[tuple[str, float, float]]:
    """(path, weight, confidence) for every weighted, non-null field."""
    out = []
    for k, w in HEADER_WEIGHTS.items():
        f = sim.get(k)
        if f and f.get("value") is not None:
            out.append((k, float(w), float(f["confidence"])))
    for i, ln in enumerate(sim.get("lines", [])):
        for k, w in LINE_WEIGHTS.items():
            f = ln.get(k)
            if f and f.get("value") is not None:
                out.append((f"lines[{i}].{k}", float(w), float(f["confidence"])))
    return out


def doc_confidence(sim: dict[str, Any]) -> float:
    fields = weighted_fields(sim)
    tw = sum(w for _, w, _ in fields)
    return math.exp(sum(w * math.log(c) for _, w, c in fields) / tw) if tw else 0.0


def _get(sim: dict[str, Any], path: str) -> dict[str, Any]:
    if path.startswith("lines["):
        i = int(path[6 : path.index("]")])
        return sim["lines"][i][path.split(".", 1)[1]]
    return sim[path]


def fit_doc_confidence(sim: dict[str, Any], target: float, keep: frozenset[str] = frozenset()) -> None:
    """Scale (in log space) the weighted confidences, except ``keep``, so the doc confidence rounds to
    ``target`` at 3 decimals. Mutates ``sim``."""
    fields = [f for f in weighted_fields(sim) if f[0] not in keep]
    tw_all = sum(w for _, w, _ in weighted_fields(sim))
    fixed = sum(w * math.log(c) for p, w, c in weighted_fields(sim) if p in keep)
    cur = sum(w * math.log(c) for _, w, c in fields)
    k = (math.log(target) * tw_all - fixed) / cur
    for p, _, c in fields:
        _get(sim, p)["confidence"] = round(min(0.999, c**k), 3)
    adjust = [p for p, _, _ in fields]
    for step in range(400):
        d = doc_confidence(sim)
        if round(d, 3) == round(target, 3):
            return
        f = _get(sim, adjust[step % len(adjust)])
        f["confidence"] = round(min(0.999, max(0.5, f["confidence"] + (0.001 if d < target else -0.001))), 3)
    raise ValueError(f"could not fit doc confidence {target}")
