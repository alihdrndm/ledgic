"""Vendor resolution (06 §6): alias exact → tax-id hash → fuzzy (token_set_ratio ≥ 90) → new unverified."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from rapidfuzz import fuzz

from .money import quantize

FUZZY_THRESHOLD = 90
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")
_SUFFIXES = re.compile(r"\b(inc|llc|ltd|co|corp|corporation|company|incorporated|lp|llp)\b\.?$")

Method = Literal["alias", "tax_id", "fuzzy", "new"]


def normalize_vendor_name(name: str) -> str:
    """casefold, '&'→'and', strip punctuation and a trailing legal suffix (Inc, LLC, ...)."""
    s = name.casefold().replace("&", " and ")
    s = _WS.sub(" ", _PUNCT.sub(" ", s)).strip()
    s = _SUFFIXES.sub("", s).strip()
    return s


def hash_tax_id(tax_id: str | None, salt: str = "") -> str | None:
    """sha256 of the digits of a tax id (EIN/SSN), optionally salted per org; None if no digits."""
    digits = re.sub(r"\D", "", tax_id or "")
    if not digits:
        return None
    return hashlib.sha256(f"{salt}{digits}".encode()).hexdigest()


@dataclass(frozen=True)
class VendorRecord:
    id: str
    display_name: str
    aliases: tuple[str, ...] = ()
    tax_id_hash: str | None = None


@dataclass(frozen=True)
class VendorResolution:
    vendor_id: str | None
    method: Method
    confidence: Decimal
    score: float | None = None  # fuzzy score 0-100

    @property
    def is_new(self) -> bool:
        return self.method == "new"


def resolve_vendor(
    name: str | None,
    vendors: Sequence[VendorRecord],
    *,
    tax_id_hash: str | None = None,
    threshold: int = FUZZY_THRESHOLD,
) -> VendorResolution:
    norm = normalize_vendor_name(name or "")
    if norm:
        for v in vendors:
            if any(normalize_vendor_name(n) == norm for n in (v.display_name, *v.aliases)):
                return VendorResolution(v.id, "alias", Decimal("1.000"))
    if tax_id_hash:
        for v in vendors:
            if v.tax_id_hash and v.tax_id_hash == tax_id_hash:
                return VendorResolution(v.id, "tax_id", Decimal("0.990"))
    if norm:
        best: tuple[float, VendorRecord] | None = None
        for v in vendors:
            for n in (v.display_name, *v.aliases):
                s = fuzz.token_set_ratio(norm, normalize_vendor_name(n))
                if best is None or s > best[0]:
                    best = (s, v)
        if best and best[0] >= threshold:
            return VendorResolution(best[1].id, "fuzzy", quantize(str(best[0] / 100), 3), score=best[0])
    return VendorResolution(None, "new", Decimal("0.000"))
