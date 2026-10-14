"""Duplicate similarity (01 §4.4) with the evidence JSON consumed by the Exceptions screen."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .money import D, Numberish, cents, fmt_money, fmt_qty, quantize

HOLD_THRESHOLD = Decimal("0.90")
SUGGEST_THRESHOLD = Decimal("0.75")
W_AMOUNT, W_DATE, W_LINES, W_NUMBER, W_IMAGE = (
    Decimal("0.30"),
    Decimal("0.20"),
    Decimal("0.30"),
    Decimal("0.10"),
    Decimal("0.10"),
)

_NON_ALNUM = re.compile(r"[^A-Z0-9]")
_PREFIX = re.compile(r"^(INVOICE|INV)(?=\d)")
_WS = re.compile(r"\s+")
_DESC_JUNK = re.compile(r"[^\w\s/.\-]")


def normalize_invoice_number(number: str | None) -> str:
    """Uppercase, alphanumerics only, drop an 'INV'/'INVOICE' prefix before digits, drop leading zeros of
    an all-digit number. 'pr-2201' == 'PR 2201' == 'PR2201'; 'INV-000123' == '123'."""
    if not number:
        return ""
    s = _NON_ALNUM.sub("", number.upper())
    s = _PREFIX.sub("", s)
    if s.isdigit():
        s = s.lstrip("0") or "0"
    return s


def _trigrams(s: str) -> set[str]:
    """pg_trgm style trigrams: each word padded with two leading spaces and one trailing space."""
    grams: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", s.lower()):
        padded = f"  {word} "
        grams.update(padded[i : i + 3] for i in range(len(padded) - 2))
    return grams


def trigram_similarity(a: str, b: str) -> Decimal:
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta and not tb:
        return Decimal(0)
    return Decimal(len(ta & tb)) / Decimal(len(ta | tb))


def phash_similarity(a: str | int | None, b: str | int | None) -> Decimal | None:
    """1 − Hamming(pHash a, pHash b) / 64. Accepts 64-bit hashes as hex strings or ints."""
    if a is None or b is None:
        return None
    ia = int(a, 16) if isinstance(a, str) else a
    ib = int(b, 16) if isinstance(b, str) else b
    dist = bin(ia ^ ib).count("1")
    return 1 - Decimal(dist) / Decimal(64)


def normalize_description(desc: str) -> str:
    return _WS.sub(" ", _DESC_JUNK.sub("", desc.casefold())).strip()


@dataclass(frozen=True)
class DupLine:
    description: str
    qty: Decimal
    amount: Decimal

    @classmethod
    def of(cls, description: str, qty: Numberish, amount: Numberish) -> DupLine:
        return cls(description, D(qty), D(amount))

    def key(self) -> tuple[str, str, Decimal]:
        return (normalize_description(self.description), fmt_qty(self.qty), cents(self.amount))


@dataclass(frozen=True)
class DupInvoice:
    vendor_id: str
    invoice_number: str
    total: Decimal
    invoice_date: date
    lines: tuple[DupLine, ...] = ()
    sha256: str | None = None
    phash: str | int | None = None


@dataclass(frozen=True)
class DuplicateScore:
    similarity: Decimal  # 3 dp; 1.000 for a hard duplicate
    weighted_score: Decimal  # the soft formula, always computed (3 dp)
    hard: bool
    components: dict[str, Decimal] = field(hash=False)
    evidence: dict[str, str] = field(hash=False)
    lines_overlap: int = 0
    lines_compared: int = 0

    @property
    def hold(self) -> bool:
        return self.similarity >= HOLD_THRESHOLD

    @property
    def suggest(self) -> bool:
        return SUGGEST_THRESHOLD <= self.similarity < HOLD_THRESHOLD


def _line_jaccard(a: Sequence[DupLine], b: Sequence[DupLine]) -> tuple[Decimal, int, int]:
    ka, kb = {ln.key() for ln in a}, {ln.key() for ln in b}
    union = ka | kb
    overlap = len(ka & kb)
    if not union:
        return Decimal(0), 0, 0
    return Decimal(overlap) / Decimal(len(union)), overlap, max(len(ka), len(kb))


def score(invoice: DupInvoice, candidate: DupInvoice) -> DuplicateScore:
    na, nb = (
        normalize_invoice_number(invoice.invoice_number),
        normalize_invoice_number(candidate.invoice_number),
    )
    hard = invoice.vendor_id == candidate.vendor_id and bool(na) and na == nb

    total_delta = cents(D(invoice.total) - D(candidate.total))
    amount_eq = Decimal(1) if abs(total_delta) <= Decimal("0.01") else Decimal(0)
    days = abs((invoice.invoice_date - candidate.invoice_date).days)
    date_close = max(Decimal(0), 1 - Decimal(days) / Decimal(7))
    jac, overlap, compared = _line_jaccard(invoice.lines, candidate.lines)
    number_sim = Decimal(1) if (na and na == nb) else trigram_similarity(na, nb)
    img = phash_similarity(invoice.phash, candidate.phash)
    image_sim = img if img is not None else Decimal(0)

    weighted = quantize(
        W_AMOUNT * amount_eq
        + W_DATE * date_close
        + W_LINES * jac
        + W_NUMBER * number_sim
        + W_IMAGE * image_sim,
        3,
    )
    similarity = Decimal("1.000") if hard else weighted

    if na and na == nb:
        ev_number = "Exact match"
    elif number_sim >= Decimal("0.5"):
        ev_number = f"Similar · {quantize(number_sim, 2)}"
    else:
        ev_number = "Differs"
    ev_amount = "Exact match" if amount_eq else f"Differs by {fmt_money(abs(total_delta))}"
    ev_date = "Exact match" if days == 0 else f"{days} day{'s' if days != 1 else ''} apart"
    if invoice.sha256 and invoice.sha256 == candidate.sha256:
        ev_file = "Identical file"
    elif img is not None:
        ev_file = f"Differs · image sim {quantize(img, 2)}"
    else:
        ev_file = "Differs"

    return DuplicateScore(
        similarity=similarity,
        weighted_score=weighted,
        hard=hard,
        components={
            "amount_eq": amount_eq,
            "date_close": quantize(date_close, 3),
            "line_jaccard": quantize(jac, 3),
            "number_sim": quantize(number_sim, 3),
            "image_sim": quantize(image_sim, 3),
        },
        evidence={
            "invoice_number": ev_number,
            "amount": ev_amount,
            "invoice_date": ev_date,
            "line_items": f"{overlap} of {compared} overlap",
            "file": ev_file,
        },
        lines_overlap=overlap,
        lines_compared=compared,
    )


def best_match(
    invoice: DupInvoice, candidates: Sequence[DupInvoice]
) -> tuple[DupInvoice, DuplicateScore] | None:
    """Highest-scoring candidate (ties keep the earliest), or None when there are no candidates."""
    best: tuple[DupInvoice, DuplicateScore] | None = None
    for c in candidates:
        s = score(invoice, c)
        if best is None or s.similarity > best[1].similarity:
            best = (c, s)
    return best
