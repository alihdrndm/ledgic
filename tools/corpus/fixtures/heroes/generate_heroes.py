"""Regenerate the recorded hero extraction fixtures in this folder.

    uv run --project services/core python tools/corpus/fixtures/heroes/generate_heroes.py

Each `<invoice>.json` is the extraction-agent output (contracts/extraction.schema.json) for a hero
document rendered by the corpus generator on the reference day. Values and bboxes come from the
corpus layout; confidences are the authored hero confidences (contracts/fixtures.json and the domain
gate tests). They stand in for a recorded gpt-4.1-mini response so the demo replays at $0.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.ai.schemas import normalize_extraction
from app.demo.corpus.catalog import build_catalog
from app.demo.corpus.confidence import fit_doc_confidence
from app.demo.corpus.invoices import hero_docs
from app.domain.gate import doc_confidence

REFERENCE_DAY = date(2026, 10, 14)
OUT = Path(__file__).resolve().parent

# Exact PR-2214 field set used by services/core/tests/domain/test_gate.py (doc confidence 0.880).
PR2214_HEADER = {
    "vendor_name": 0.95,
    "invoice_number": 0.92,
    "invoice_date": 0.93,
    "total": 0.93,
    "po_reference": 0.86,
    "terms": 0.83,
}
PR2214_LINES = [
    (0.88, 0.86, 0.87),
    (0.71, 0.86, 0.87),
    (0.87, 0.85, 0.86),
    (0.86, 0.85, 0.86),
    (0.87, 0.84, 0.85),
]
TARGETS = {"PS-88214": 0.98, "BD-104882": 0.97, "PR-2201": 0.98, "PR-2201-photo": 0.91}


def main() -> None:
    cat = build_catalog(REFERENCE_DAY)
    for doc in hero_docs(cat, REFERENCE_DAY):
        sim = json.loads(json.dumps(doc.simulated_extraction))
        name = doc.hero + ("-photo" if doc.hero == "PR-2201" and doc.channel == "photo" else "")
        if name == "PR-2214":
            for k, c in PR2214_HEADER.items():
                sim[k]["confidence"] = c
            for ln, (q, u, a) in zip(sim["lines"], PR2214_LINES, strict=True):
                ln["qty"]["confidence"], ln["unit_price"]["confidence"], ln["amount"]["confidence"] = q, u, a
        elif name in TARGETS:
            fit_doc_confidence(sim, TARGETS[name])
        result = normalize_extraction(sim)
        dc = doc_confidence(result.gate_fields())
        payload = {
            "$comment": (
                "Recorded extraction-agent output for a hero document (reference day "
                f"{REFERENCE_DAY}). Authored from the corpus ground truth with the hero confidences; "
                "stands in for a recorded gpt-4.1-mini response. Regenerate with generate_heroes.py."
            ),
            "hero": doc.hero,
            "channel": doc.channel,
            "model": "gpt-4.1-mini",
            "prompt_version": "p-1",
            "reference_day": REFERENCE_DAY.isoformat(),
            "doc_confidence": str(dc),
            "extraction": result.model_dump(mode="json"),
        }
        (OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(name, doc.channel, "doc_confidence", dc, "lines", len(result.lines))


if __name__ == "__main__":
    main()
