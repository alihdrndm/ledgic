"""Invoice page layout: one pure function per supplier template.

A ``Layout`` is a list of drawing ops per page (top-left origin, PDF points) plus the box of every
extracted field. The renderer draws exactly these ops, and the planner reads the field boxes to
produce bboxes for ``simulated_extraction`` -- so the overlays line up with what is printed.

Templates:
  A  modern band (Helvetica)      -- produce/dairy/bakery; matches the Extraction screen mock
  B  classic boxed grid (Times)   -- broadline/protein/equipment; QTY first column order; paginates at 10
  C  delivery ticket (Courier)    -- table-less: each line is a two-row text block
  D  portal / EDI clean (Helvetica, header band, zebra rows, SKU column)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Any

from reportlab.pdfbase.pdfmetrics import stringWidth

PAGE_W, PAGE_H = 612.0, 792.0
LEFT, RIGHT = 54.0, 558.0

Op = tuple[Any, ...]


@lru_cache(maxsize=8192)
def text_width(s: str, font: str, size: float) -> float:
    return stringWidth(s, font, size)


@dataclass
class Layout:
    template: str
    pages: list[list[Op]] = field(default_factory=list)
    fields: dict[str, tuple[int, float, float, float, float]] = field(default_factory=dict)
    anchors: dict[str, tuple[int, float, float, float]] = field(default_factory=dict)

    def page(self, n: int) -> list[Op]:
        while len(self.pages) < n:
            self.pages.append([])
        return self.pages[n - 1]

    def text(
        self,
        page: int,
        x: float,
        y: float,
        s: str,
        font: str = "Helvetica",
        size: float = 9.0,
        align: str = "left",
        gray: float = 0.0,
        fld: str | None = None,
    ) -> float:
        """Draw ``s`` with baseline at y. Returns the left x actually used."""
        w = text_width(s, font, size)
        x0 = x - w if align == "right" else x - w / 2 if align == "center" else x
        self.page(page).append(("text", x0, y, s, font, size, gray))
        if fld:
            self.register(fld, page, x0 - 1.5, y - size * 0.80 - 1.0, w + 3.0, size * 1.05 + 2.0)
        return x0

    def register(self, fld: str, page: int, x: float, y: float, w: float, h: float) -> None:
        if fld in self.fields and self.fields[fld][0] == page:
            p, x1, y1, w1, h1 = self.fields[fld]
            nx, ny = min(x, x1), min(y, y1)
            self.fields[fld] = (p, nx, ny, max(x + w, x1 + w1) - nx, max(y + h, y1 + h1) - ny)
        elif fld not in self.fields:
            self.fields[fld] = (page, x, y, w, h)

    def line(
        self,
        page: int,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width: float = 0.6,
        gray: float = 0.0,
        dash: tuple[float, ...] | None = None,
    ) -> None:
        self.page(page).append(("line", x1, y1, x2, y2, width, gray, dash))

    def rect(
        self,
        page: int,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: float | None = None,
        stroke: float | None = 0.0,
        width: float = 0.6,
    ) -> None:
        self.page(page).append(("rect", x, y, w, h, fill, stroke, width))

    def norm_bbox(self, fld: str) -> dict[str, float | int] | None:
        if fld not in self.fields:
            return None
        p, x, y, w, h = self.fields[fld]
        x0, y0 = max(0.0, x / PAGE_W), max(0.0, y / PAGE_H)
        x1, y1 = min(1.0, (x + w) / PAGE_W), min(1.0, (y + h) / PAGE_H)
        return {
            "page": p,
            "x": round(x0, 4),
            "y": round(y0, 4),
            "w": round(x1 - x0, 4),
            "h": round(y1 - y0, 4),
        }


# --------------------------------------------------------------------------------------------- format


def money(v: str | Decimal | None, sep: bool = True) -> str:
    if v is None:
        return ""
    d = Decimal(str(v)).quantize(Decimal("0.01"))
    return f"{d:,.2f}" if sep else f"{d:.2f}"


def qty(v: str | Decimal) -> str:
    d = Decimal(str(v))
    return f"{d.normalize():f}" if d == d.to_integral() else f"{d:f}".rstrip("0")


def d_us(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%m/%d/%Y")


def d_ticket(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d-%b-%Y").upper()


def d_long(iso: str) -> str:
    dt = date.fromisoformat(iso)
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _totals_rows(t: dict[str, Any]) -> list[tuple[str, str, str]]:
    rows = [("Subtotal", "subtotal", t["subtotal"])]
    if t.get("tax") is not None:
        rows.append(("Tax", "tax", t["tax"]))
    if t.get("freight") is not None:
        rows.append(("Freight", "freight", t["freight"]))
    return rows


def _paginate(n: int, per_page: int) -> list[range]:
    return [range(i, min(n, i + per_page)) for i in range(0, max(n, 1), per_page)]


LINES_PER_PAGE = {"A": 18, "B": 10, "C": 12, "D": 22}


def page_count(template: str, n_lines: int) -> int:
    return len(_paginate(n_lines, LINES_PER_PAGE[template]))


# --------------------------------------------------------------------------------------------- footer


def _footer(
    lay: Layout,
    page: int,
    t: dict[str, Any],
    ctx: dict[str, Any],
    font: str,
    y: float,
    labels: tuple[str, str, str],
) -> None:
    remit_label, bank_label, cur_label = labels
    rt = t.get("remit_to")
    if rt:
        x = lay.text(page, LEFT, y, remit_label, font, 7.5, gray=0.35)
        x += text_width(remit_label, font, 7.5) + 3
        lay.text(page, x, y, f"{rt['name']}, {rt['address']}", font, 7.5, gray=0.1, fld="remit_to")
    bd = t.get("bank_details")
    if bd:
        x = lay.text(page, LEFT, y + 11, bank_label, font, 7.5, gray=0.35)
        x += text_width(bank_label, font, 7.5) + 3
        lay.text(
            page,
            x,
            y + 11,
            f"routing {bd['routing']} · account {bd['account']}",
            font,
            7.5,
            gray=0.1,
            fld="bank_details",
        )
    x = lay.text(page, LEFT, y + 22, cur_label, font, 7.5, gray=0.35)
    lay.text(
        page,
        x + text_width(cur_label, font, 7.5) + 3,
        y + 22,
        t["currency"],
        font,
        7.5,
        gray=0.1,
        fld="currency",
    )


# --------------------------------------------------------------------------------------------- A


def _template_a(t: dict[str, Any], ctx: dict[str, Any]) -> Layout:
    lay = Layout("A")
    v = ctx["vendor"]
    lines = t["lines"]
    pages = _paginate(len(lines), LINES_PER_PAGE["A"])
    for pi, rows in enumerate(pages, start=1):
        last = pi == len(pages)
        lay.text(pi, LEFT, 80, t["vendor_name"].upper(), "Helvetica-Bold", 19, fld="vendor_name")
        lay.text(pi, LEFT, 95, v["tagline"].upper(), "Helvetica", 7.5, gray=0.4)
        lay.text(pi, LEFT, 106, v["address"], "Helvetica", 7.5, gray=0.4)
        num = t["invoice_number"]
        wn = text_width(num, "Helvetica-Bold", 10.5)
        lay.text(pi, RIGHT - wn, 78, "INVOICE ", "Helvetica", 10.5, align="right")
        lay.text(pi, RIGHT, 78, num, "Helvetica-Bold", 10.5, align="right", fld="invoice_number")
        ds, ts = d_us(t["invoice_date"]), t.get("terms") or ""
        sep = " · "
        full = ds + sep + ts
        x0 = RIGHT - text_width(full, "Helvetica", 9.5)
        lay.text(pi, x0, 93, ds, "Helvetica", 9.5, fld="invoice_date")
        if ts:
            lay.text(pi, x0 + text_width(ds + sep, "Helvetica", 9.5), 93, ts, "Helvetica", 9.5, fld="terms")
            lay.text(pi, x0 + text_width(ds, "Helvetica", 9.5), 93, sep, "Helvetica", 9.5)
        if t.get("due_date"):
            due = d_us(t["due_date"])
            lay.text(pi, RIGHT, 106, due, "Helvetica", 7.5, align="right", gray=0.3, fld="due_date")
            lay.text(
                pi,
                RIGHT - text_width(due, "Helvetica", 7.5) - 3,
                106,
                "DUE",
                "Helvetica",
                7.5,
                align="right",
                gray=0.45,
            )
        if pi > 1:
            lay.text(
                pi, LEFT, 118, f"continued · page {pi} of {len(pages)}", "Helvetica-Oblique", 7.5, gray=0.4
            )
        lay.line(pi, LEFT, 126, RIGHT, 126, 0.8, gray=0.2)
        lay.text(pi, LEFT, 146, f"SOLD TO: {ctx['sold_to']}", "Helvetica", 9)
        lay.text(pi, LEFT, 159, ctx["sold_to_line2"], "Helvetica", 9)
        po = t.get("po_reference")
        if po:
            lay.text(pi, RIGHT, 146, po, "Helvetica", 9, align="right", fld="po_reference")
            lay.text(
                pi, RIGHT - text_width(po, "Helvetica", 9), 146, "PO REF: ", "Helvetica", 9, align="right"
            )
        else:
            lay.text(pi, RIGHT, 146, "PO REF: —", "Helvetica", 9, align="right", gray=0.4)
        lay.text(pi, RIGHT, 159, f"DELIVERED BY: {ctx['route']}", "Helvetica", 9, align="right")
        y = 190
        for label, x, al in (
            ("ITEM", LEFT, "left"),
            ("QTY", 316, "left"),
            ("UOM", 352, "left"),
            ("UNIT", 396, "left"),
            ("AMOUNT", RIGHT, "right"),
        ):
            lay.text(pi, x, y, label, "Helvetica-Bold", 8.5, align=al)
        lay.line(pi, LEFT, y + 6, RIGHT, y + 6, 0.5, gray=0.3)
        y += 24
        for i in rows:
            ln = lines[i]
            lay.text(pi, LEFT, y, ln["description"], "Helvetica", 9, fld=f"lines[{i}].description")
            lay.text(pi, 316, y, qty(ln["qty"]), "Helvetica", 9, fld=f"lines[{i}].qty")
            lay.text(pi, 352, y, ln["uom"], "Helvetica", 9, fld=f"lines[{i}].uom")
            lay.text(
                pi, 396, y, money(ln["unit_price"], sep=False), "Helvetica", 9, fld=f"lines[{i}].unit_price"
            )
            lay.text(
                pi, RIGHT, y, money(ln["amount"]), "Helvetica", 9, align="right", fld=f"lines[{i}].amount"
            )
            lay.line(pi, LEFT, y + 9, RIGHT, y + 9, 0.25, gray=0.82)
            y += 22
        if last:
            lay.line(pi, LEFT, y - 4, RIGHT, y - 4, 0.6, gray=0.3)
            y += 12
            for label, key, val in _totals_rows(t):
                lay.text(pi, 396, y, label, "Helvetica", 8.5, gray=0.35)
                lay.text(pi, RIGHT, y, money(val), "Helvetica", 8.5, align="right", fld=key)
                y += 14
            lay.text(pi, LEFT, y + 4, "TOTAL", "Helvetica-Bold", 10)
            lay.text(pi, RIGHT, y + 4, money(t["total"]), "Helvetica-Bold", 10, align="right", fld="total")
            y += 44
            lay.text(pi, LEFT, y, "Received in good order:", "Helvetica", 8, gray=0.3)
            lay.line(pi, 360, y + 2, RIGHT, y + 2, 0.4, gray=0.6)
            lay.anchors["signature"] = (pi, 372.0, y - 12, 170.0)
            _footer(lay, pi, t, ctx, "Helvetica", 728, ("Remit to:", "ACH:", "All amounts in"))
    return lay


# --------------------------------------------------------------------------------------------- B


def _template_b(t: dict[str, Any], ctx: dict[str, Any]) -> Layout:
    lay = Layout("B")
    v = ctx["vendor"]
    lines = t["lines"]
    pages = _paginate(len(lines), LINES_PER_PAGE["B"])
    f, fb = "Times-Roman", "Times-Bold"
    cols = [
        ("QTY", 54, 92),
        ("UNIT", 92, 132),
        ("DESCRIPTION", 132, 384),
        ("UNIT PRICE", 384, 468),
        ("EXTENSION", 468, 558),
    ]
    for pi, rows in enumerate(pages, start=1):
        last = pi == len(pages)
        if pi == 1:
            lay.text(pi, PAGE_W / 2, 68, t["vendor_name"].upper(), fb, 18, align="center", fld="vendor_name")
            lay.text(pi, PAGE_W / 2, 84, v["address"], f, 9, align="center", gray=0.25)
            lay.text(pi, PAGE_W / 2, 96, f"{v['phone']} · {v['email']}", f, 9, align="center", gray=0.25)
            lay.line(pi, LEFT, 108, RIGHT, 108, 1.2)
            lay.line(pi, LEFT, 111, RIGHT, 111, 0.4)
            # bill-to / ship-to boxes
            lay.rect(pi, LEFT, 128, 250, 62, stroke=0.0)
            lay.text(pi, LEFT + 6, 140, "BILL TO", fb, 8)
            lay.text(pi, LEFT + 6, 154, "Northside Group — Accounts Payable", f, 10)
            lay.text(pi, LEFT + 6, 167, "ap@northside.example", f, 10)
            lay.rect(pi, LEFT, 198, 250, 62, stroke=0.0)
            lay.text(pi, LEFT + 6, 210, "SHIP TO", fb, 8)
            lay.text(pi, LEFT + 6, 224, ctx["sold_to"], f, 10)
            lay.text(pi, LEFT + 6, 237, ctx["sold_to_line2"], f, 10)
            # invoice box
            lay.rect(pi, 330, 128, 228, 132, stroke=0.0)
            lay.rect(pi, 330, 128, 228, 24, fill=0.88, stroke=0.0)
            lay.text(pi, 444, 145, "INVOICE", fb, 14, align="center")
            meta = [
                ("Invoice No.", "invoice_number", t["invoice_number"]),
                ("Invoice Date", "invoice_date", d_us(t["invoice_date"])),
                ("Due Date", "due_date", d_us(t["due_date"]) if t.get("due_date") else None),
                ("Terms", "terms", t.get("terms")),
                ("Customer PO", "po_reference", t.get("po_reference")),
            ]
            y = 170
            for label, key, val in meta:
                lay.text(pi, 338, y, label, f, 9.5, gray=0.3)
                if val:
                    lay.text(
                        pi, 550, y, val, fb if key == "invoice_number" else f, 10, align="right", fld=key
                    )
                else:
                    lay.text(pi, 550, y, "—", f, 10, align="right", gray=0.5)
                lay.line(pi, 334, y + 5, 554, y + 5, 0.2, gray=0.75)
                y += 18
            top = 282
        else:
            lay.text(pi, LEFT, 64, t["vendor_name"].upper(), fb, 11)
            lay.text(pi, RIGHT, 64, f"Invoice No. {t['invoice_number']} — continued", f, 10, align="right")
            lay.line(pi, LEFT, 72, RIGHT, 72, 0.8)
            top = 96
        # table grid
        n_rows = len(rows)
        row_h = 24
        table_h = 22 + n_rows * row_h
        lay.rect(pi, LEFT, top, RIGHT - LEFT, 22, fill=0.88, stroke=0.0)
        lay.rect(pi, LEFT, top, RIGHT - LEFT, table_h, stroke=0.0, width=0.8)
        for _, x0, _x1 in cols[1:]:
            lay.line(pi, x0, top, x0, top + table_h, 0.4)
        for label, x0, x1 in cols:
            al = (
                "left"
                if label == "DESCRIPTION"
                else "right"
                if label in ("UNIT PRICE", "EXTENSION", "QTY")
                else "left"
            )
            xx = x0 + 6 if al == "left" else x1 - 6
            lay.text(pi, xx, top + 15, label, fb, 8.5, align=al)
        y = top + 22 + 16
        for i in rows:
            ln = lines[i]
            lay.text(pi, 86, y, qty(ln["qty"]), f, 10.5, align="right", fld=f"lines[{i}].qty")
            lay.text(pi, 98, y, ln["uom"], f, 10.5, fld=f"lines[{i}].uom")
            lay.text(pi, 138, y, ln["description"], f, 10.5, fld=f"lines[{i}].description")
            lay.text(
                pi, 462, y, money(ln["unit_price"]), f, 10.5, align="right", fld=f"lines[{i}].unit_price"
            )
            lay.text(pi, 552, y, money(ln["amount"]), f, 10.5, align="right", fld=f"lines[{i}].amount")
            if i != rows[-1]:
                lay.line(pi, LEFT, y + 8, RIGHT, y + 8, 0.2, gray=0.75)
            y += row_h
        y = top + table_h
        if last:
            y += 20
            for label, key, val in _totals_rows(t):
                lay.text(pi, 462, y, label, f, 10, align="right", gray=0.25)
                lay.text(pi, 552, y, money(val), f, 10, align="right", fld=key)
                y += 15
            lay.rect(pi, 384, y - 6, RIGHT - 384, 22, stroke=0.0, width=1.0)
            lay.text(pi, 462, y + 10, "TOTAL DUE", fb, 11, align="right")
            lay.text(pi, 552, y + 10, f"${money(t['total'])}", fb, 11, align="right", fld="total")
            lay.text(pi, LEFT, y + 10, "Received by:", f, 9, gray=0.3)
            lay.line(pi, 112, y + 12, 300, y + 12, 0.4, gray=0.5)
            lay.anchors["signature"] = (pi, 118.0, y - 2, 170.0)
        else:
            lay.text(pi, RIGHT, y + 18, "Continued on next page", "Times-Italic", 9, align="right", gray=0.35)
        lay.text(pi, PAGE_W / 2, 770, f"Page {pi} of {len(pages)}", f, 8, align="center", gray=0.4)
        if last:
            _footer(lay, pi, t, ctx, f, 722, ("Please remit to:", "Wire/ACH:", "Amounts in"))
    return lay


# --------------------------------------------------------------------------------------------- C


def _template_c(t: dict[str, Any], ctx: dict[str, Any]) -> Layout:
    lay = Layout("C")
    v = ctx["vendor"]
    lines = t["lines"]
    pages = _paginate(len(lines), LINES_PER_PAGE["C"])
    f, fb = "Courier", "Courier-Bold"
    for pi, rows in enumerate(pages, start=1):
        last = pi == len(pages)
        lay.text(pi, LEFT, 62, t["vendor_name"].upper(), fb, 14, fld="vendor_name")
        lay.text(pi, LEFT, 76, v["address"].upper(), f, 8.5, gray=0.2)
        lay.text(pi, LEFT, 87, f"TEL {v['phone']}", f, 8.5, gray=0.2)
        lay.text(pi, RIGHT, 62, "DELIVERY TICKET / INVOICE", fb, 10, align="right")
        lay.text(pi, RIGHT, 76, f"SHEET {pi} OF {len(pages)}", f, 8.5, align="right", gray=0.2)
        meta = [
            ("INVOICE NO.  :", "invoice_number", t["invoice_number"]),
            ("INVOICE DATE :", "invoice_date", d_ticket(t["invoice_date"])),
            ("TERMS        :", "terms", t.get("terms")),
            ("DUE DATE     :", "due_date", d_ticket(t["due_date"]) if t.get("due_date") else None),
            ("CUST PO      :", "po_reference", t.get("po_reference")),
        ]
        y = 116
        for label, key, val in meta:
            lay.text(pi, LEFT, y, label, f, 9.5)
            x = LEFT + text_width(label + " ", f, 9.5)
            if val:
                lay.text(pi, x, y, val, fb if key == "invoice_number" else f, 9.5, fld=key)
            else:
                lay.text(pi, x, y, "NONE", f, 9.5, gray=0.4)
            y += 13
        lay.text(pi, 340, 116, "DELIVER TO:", fb, 9.5)
        lay.text(pi, 340, 129, ctx["sold_to"].upper(), f, 9)
        lay.text(pi, 340, 142, ctx["sold_to_line2"].upper(), f, 9)
        lay.text(pi, 340, 155, ctx["route"].upper(), f, 9)
        lay.line(pi, LEFT, 192, RIGHT, 192, 0.7, dash=(3, 2))
        y = 212
        for i in rows:
            ln = lines[i]
            tag = f"{i + 1:02d}  "
            lay.text(pi, LEFT, y, tag, fb, 9.5)
            lay.text(
                pi,
                LEFT + text_width(tag, fb, 9.5),
                y,
                ln["description"],
                fb,
                9.5,
                fld=f"lines[{i}].description",
            )
            y2 = y + 13
            x = LEFT + text_width("    ", f, 9.5)
            x = lay.text(pi, x, y2, "QTY ", f, 9.5, gray=0.3) + text_width("QTY ", f, 9.5)
            q = qty(ln["qty"])
            lay.text(pi, x, y2, q, f, 9.5, fld=f"lines[{i}].qty")
            x += text_width(q + " ", f, 9.5)
            lay.text(pi, x, y2, ln["uom"], f, 9.5, fld=f"lines[{i}].uom")
            x += text_width(ln["uom"] + "  ", f, 9.5)
            lay.text(pi, x, y2, "@ ", f, 9.5, gray=0.3)
            x += text_width("@ ", f, 9.5)
            lay.text(pi, x, y2, money(ln["unit_price"]), f, 9.5, fld=f"lines[{i}].unit_price")
            lay.text(pi, 470, y2, "EXT", f, 9.5, gray=0.3)
            lay.text(pi, RIGHT, y2, money(ln["amount"]), f, 9.5, align="right", fld=f"lines[{i}].amount")
            y += 36
        lay.line(pi, LEFT, y - 8, RIGHT, y - 8, 0.7, dash=(3, 2))
        if last:
            y += 12
            for label, key, val in _totals_rows(t):
                lay.text(pi, 330, y, label.upper(), f, 9.5)
                lay.text(pi, RIGHT, y, money(val), f, 9.5, align="right", fld=key)
                y += 13
            lay.text(pi, 330, y + 4, "TOTAL DUE", fb, 10.5)
            lay.text(pi, RIGHT, y + 4, money(t["total"]), fb, 10.5, align="right", fld="total")
            lay.text(pi, LEFT, y + 4, "RECEIVED BY: ____________", f, 9)
            lay.anchors["signature"] = (pi, LEFT + 86.0, y - 8, 120.0)
            _footer(lay, pi, t, ctx, f, 726, ("REMIT:", "BANK:", "CURRENCY"))
    return lay


# --------------------------------------------------------------------------------------------- D


def _template_d(t: dict[str, Any], ctx: dict[str, Any]) -> Layout:
    lay = Layout("D")
    lines = t["lines"]
    skus = ctx.get("skus") or [""] * len(lines)
    pages = _paginate(len(lines), LINES_PER_PAGE["D"])
    f, fb = "Helvetica", "Helvetica-Bold"
    sub = ctx.get("portal_note", "Issued via supplier portal")
    for pi, rows in enumerate(pages, start=1):
        last = pi == len(pages)
        lay.page(pi).append(("rect", 0, 36, PAGE_W, 60, 0.15, None, 0))
        lay.page(pi).append(("text", LEFT, 64, t["vendor_name"], fb, 16, 1.0))
        lay.register(
            "vendor_name",
            pi,
            LEFT - 1.5,
            64 - 16 * 0.8 - 1,
            text_width(t["vendor_name"], fb, 16) + 3,
            16 * 1.05 + 2,
        )
        lay.page(pi).append(("text", LEFT, 80, sub, f, 8, 0.8))
        inv = "INVOICE"
        lay.page(pi).append(("text", RIGHT - text_width(inv, f, 18), 72, inv, f, 18, 1.0))
        meta = [
            [
                ("Invoice number", "invoice_number", t["invoice_number"]),
                ("Invoice date", "invoice_date", d_long(t["invoice_date"])),
            ],
            [
                ("Due date", "due_date", d_long(t["due_date"]) if t.get("due_date") else None),
                ("Terms", "terms", t.get("terms")),
            ],
            [
                ("Purchase order", "po_reference", t.get("po_reference")),
                ("Ship to", None, ctx["sold_to_short"]),
            ],
        ]
        for ci, col in enumerate(meta):
            x = LEFT + ci * 176
            y = 122
            for label, key, val in col:
                lay.text(pi, x, y, label.upper(), f, 7, gray=0.45)
                lay.text(
                    pi,
                    x,
                    y + 13,
                    val or "—",
                    fb,
                    10,
                    gray=0.0 if val else 0.5,
                    fld=key if (key and val) else None,
                )
                y += 32
        top = 200
        lay.line(pi, LEFT, top, RIGHT, top, 1.0)
        heads = [
            ("#", LEFT, "left"),
            ("SKU", 72, "left"),
            ("DESCRIPTION", 126, "left"),
            ("UOM", 352, "left"),
            ("QTY", 410, "right"),
            ("PRICE", 478, "right"),
            ("AMOUNT", RIGHT, "right"),
        ]
        for label, x, al in heads:
            lay.text(pi, x, top + 13, label, fb, 7.5, align=al, gray=0.3)
        lay.line(pi, LEFT, top + 19, RIGHT, top + 19, 0.4, gray=0.5)
        y = top + 19
        for k, i in enumerate(rows):
            ln = lines[i]
            if k % 2 == 1:
                lay.rect(pi, LEFT, y, RIGHT - LEFT, 18, fill=0.95, stroke=None)
            by = y + 12.5
            lay.text(pi, LEFT, by, str(i + 1), f, 8.5, gray=0.4)
            lay.text(pi, 72, by, skus[i] if i < len(skus) else "", f, 8.5, gray=0.35)
            lay.text(pi, 126, by, ln["description"], f, 8.5, fld=f"lines[{i}].description")
            lay.text(pi, 352, by, ln["uom"], f, 8.5, fld=f"lines[{i}].uom")
            lay.text(pi, 410, by, qty(ln["qty"]), f, 8.5, align="right", fld=f"lines[{i}].qty")
            lay.text(
                pi, 478, by, money(ln["unit_price"]), f, 8.5, align="right", fld=f"lines[{i}].unit_price"
            )
            lay.text(pi, RIGHT, by, money(ln["amount"]), f, 8.5, align="right", fld=f"lines[{i}].amount")
            y += 18
        lay.line(pi, LEFT, y, RIGHT, y, 0.4, gray=0.5)
        if last:
            y += 22
            for label, key, val in _totals_rows(t):
                lay.text(pi, 478, y, label, f, 9, align="right", gray=0.4)
                lay.text(pi, RIGHT, y, money(val), f, 9, align="right", fld=key)
                y += 15
            lay.rect(pi, 380, y - 4, RIGHT - 380, 26, fill=0.92, stroke=None)
            lay.text(pi, 478, y + 13, "Amount due (USD)", fb, 9.5, align="right")
            lay.text(pi, RIGHT - 6, y + 13, money(t["total"]), fb, 11, align="right", fld="total")
            _footer(lay, pi, t, ctx, f, 722, ("Remit to", "Bank", "Currency"))
        lay.text(pi, RIGHT, 772, f"{pi} / {len(pages)}", f, 7.5, align="right", gray=0.45)
    return lay


TEMPLATES = {"A": _template_a, "B": _template_b, "C": _template_c, "D": _template_d}


def build_layout(truth: dict[str, Any], ctx: dict[str, Any]) -> Layout:
    return TEMPLATES[ctx["template"]](truth, ctx)
