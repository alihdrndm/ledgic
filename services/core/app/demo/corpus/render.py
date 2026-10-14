"""Draw a ``Layout`` to PDF bytes with reportlab (deterministic: invariant mode, built-in fonts)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .layout import PAGE_H, Layout, build_layout


@dataclass(frozen=True)
class PdfResult:
    content: bytes
    pages: int
    bboxes: dict[str, dict[str, float | int]]  # field path -> normalized bbox on the PDF page
    layout: Layout


def draw_layout(lay: Layout, title: str = "Invoice") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, invariant=1, pageCompression=1)
    c.setTitle(title)
    c.setAuthor("Ledgic synthetic corpus")
    c.setCreator("ledgic-corpus")
    for ops in lay.pages:
        for op in ops:
            kind = op[0]
            if kind == "text":
                _, x, y, s, font, size, gray = op
                c.setFillGray(gray)
                c.setFont(font, size)
                c.drawString(x, PAGE_H - y, s)
            elif kind == "line":
                _, x1, y1, x2, y2, width, gray, dash = op
                c.setStrokeGray(gray)
                c.setLineWidth(width)
                c.setDash(*dash) if dash else c.setDash()
                c.line(x1, PAGE_H - y1, x2, PAGE_H - y2)
                c.setDash()
            elif kind == "rect":
                _, x, y, w, h, fill, stroke, width = op
                if fill is not None:
                    c.setFillGray(fill)
                if stroke is not None:
                    c.setStrokeGray(stroke)
                    c.setLineWidth(width)
                c.rect(x, PAGE_H - y - h, w, h, stroke=int(stroke is not None), fill=int(fill is not None))
        c.showPage()
    c.save()
    return buf.getvalue()


def render_pdf(truth: dict[str, Any], ctx: dict[str, Any]) -> PdfResult:
    lay = build_layout(truth, ctx)
    content = draw_layout(lay, title=f"Invoice {truth.get('invoice_number') or ''}".strip())
    boxes = {k: b for k in lay.fields if (b := lay.norm_bbox(k)) is not None}
    return PdfResult(content, len(lay.pages), boxes, lay)
