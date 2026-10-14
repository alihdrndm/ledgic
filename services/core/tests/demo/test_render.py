from __future__ import annotations

import io
import random

import pypdfium2 as pdfium
import pytest
from PIL import Image

from app.demo.corpus.render import render_pdf


def _check_boxes(boxes):
    assert boxes
    for b in boxes.values():
        assert 0 <= b["x"] <= 1 and 0 <= b["y"] <= 1 and b["w"] > 0 and b["h"] > 0
        assert b["x"] + b["w"] <= 1.0001 and b["y"] + b["h"] <= 1.0001


@pytest.fixture(scope="module")
def rendered_heroes(today_docs):
    return {(d.hero, d.channel): (d, d.render()) for d in today_docs if d.hero}


def test_hero_pdfs_open_with_text_layer(rendered_heroes):
    d, r = rendered_heroes[("PS-88214", "email")]
    assert r.mime == "application/pdf" and len(r.content) < 80_000
    pdf = pdfium.PdfDocument(r.content)
    text = pdf[0].get_textpage().get_text_range()
    assert "PS-88214" in text and "4.12" in text and "2,847.60" in text
    pdf.close()
    d, r = rendered_heroes[("BD-104882", "email")]
    pdf = pdfium.PdfDocument(r.content)
    assert len(pdf) == 2 == r.pages
    pdf.close()


def test_hero_photo(rendered_heroes):
    d, r = rendered_heroes[("PR-2214", "photo")]
    assert r.mime == "image/jpeg" and len(r.content) < 200_000 and r.skew_deg == 2.0
    img = Image.open(io.BytesIO(r.content))
    assert img.format == "JPEG" and img.size[1] > img.size[0]
    _check_boxes(r.bboxes)
    # planner bboxes are the renderer's bboxes
    assert d.simulated_extraction["lines"][1]["qty"]["bbox"] == r.bboxes["lines[1].qty"]
    assert d.simulated_extraction["total"]["bbox"] == r.bboxes["total"]


def test_render_is_byte_deterministic(today_docs):
    hero = next(d for d in today_docs if d.hero == "PR-2214")
    assert hero.render().sha256 == hero.render().sha256
    pdf = next(d for d in today_docs if d.hero == "PS-88214")
    assert pdf.render().sha256 == pdf.render().sha256


def test_duplicate_copies_have_different_bytes(rendered_heroes):
    _, a = rendered_heroes[("PR-2201", "email")]
    _, b = rendered_heroes[("PR-2201", "photo")]
    assert a.sha256 != b.sha256


def test_sample_of_generated_docs_render(today_docs):
    r = random.Random(7)
    by_kind = {}
    for d in today_docs:
        by_kind.setdefault((d.template, d.channel), []).append(d)
    assert {t for t, _ in by_kind} == {"A", "B", "C", "D"}
    for _, docs in sorted(by_kind.items()):
        d = r.choice(docs)
        out = d.render()
        limit = 200_000 if d.channel == "photo" else 80_000
        assert len(out.content) < limit, (d.key, len(out.content))
        assert out.pages == d.pages
        _check_boxes(out.bboxes)
        sim_boxes = {
            k: f["bbox"] for k, f in d.simulated_extraction.items() if isinstance(f, dict) and f.get("bbox")
        }
        for k, b in sim_boxes.items():
            assert out.bboxes[k] == b


def test_every_template_registers_all_printed_fields(today_docs):
    for d in today_docs[:60]:
        res = render_pdf(d.truth, d.render_ctx)
        for k in ("vendor_name", "invoice_number", "invoice_date", "total", "subtotal", "currency"):
            assert k in res.bboxes, (d.template, k)
        if d.truth["po_reference"]:
            assert "po_reference" in res.bboxes
        for i in range(len(d.truth["lines"])):
            for k in ("description", "qty", "uom", "unit_price", "amount"):
                assert f"lines[{i}].{k}" in res.bboxes, (d.template, i, k)


def test_phash(rendered_heroes):
    _, r = rendered_heroes[("PR-2201", "email")]
    h = r.phash()
    assert len(h) == 16 and int(h, 16) >= 0
