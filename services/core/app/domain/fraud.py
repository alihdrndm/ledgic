"""New-vendor / bank-change fraud screen (01 §4.5)."""

from __future__ import annotations

import hashlib
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from .money import D, Numberish, quantize

HOLD_THRESHOLD = Decimal("0.70")
WEIGHTS: dict[str, Decimal] = {
    "bank_mismatch_w9": Decimal("0.50"),
    "vendor_age_lt_14d": Decimal("0.20"),
    "no_po": Decimal("0.10"),
    "remit_address_new": Decimal("0.10"),
    "amount_anomaly": Decimal("0.10"),
}
NEW_VENDOR_DAYS = 14
ANOMALY_Z = Decimal(3)
ANOMALY_MIN_HISTORY = 5


def bank_fingerprint(routing: str | None, account: str | None) -> str | None:
    """sha256 of 'routing:account' digits only; None when either is missing."""
    r = re.sub(r"\D", "", routing or "")
    a = re.sub(r"\D", "", account or "")
    if not r or not a:
        return None
    return hashlib.sha256(f"{r}:{a}".encode()).hexdigest()


@dataclass(frozen=True)
class FraudInputs:
    amount: Decimal
    vendor_age_days: int
    has_po: bool
    invoice_bank_fingerprint: str | None = None  # from extracted bank_details
    w9_bank_fingerprint: str | None = None  # vendors.w9_bank_fingerprint
    remit_address_new: bool = False  # remit-to created/changed recently
    history: tuple[Decimal, ...] = ()  # vendor invoice totals, last 90 days


@dataclass(frozen=True)
class FraudSignal:
    signal: str
    weight: Decimal
    label: str
    detail: dict[str, str] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class FraudResult:
    score: Decimal  # 2 dp, capped at 1
    signals: tuple[FraudSignal, ...]

    @property
    def hold(self) -> bool:
        return self.score >= HOLD_THRESHOLD

    @property
    def label(self) -> str:
        return f"Signal score {self.score:.2f}"


def amount_z(amount: Numberish, history: Sequence[Numberish]) -> Decimal | None:
    """z-score of amount vs history (sample std); None with < 5 history points."""
    if len(history) < ANOMALY_MIN_HISTORY:
        return None
    hist = [D(h) for h in history]
    mean = sum(hist, Decimal(0)) / len(hist)
    std = statistics.stdev(hist)
    if std == 0:
        return Decimal("Infinity") if D(amount) > mean else Decimal(0)
    return (D(amount) - mean) / std


def screen(inp: FraudInputs) -> FraudResult:
    signals: list[FraudSignal] = []
    inv_fp, w9_fp = inp.invoice_bank_fingerprint, inp.w9_bank_fingerprint
    if inv_fp and w9_fp and inv_fp != w9_fp:
        signals.append(
            FraudSignal(
                "bank_mismatch_w9", WEIGHTS["bank_mismatch_w9"], "Bank details differ from the W-9 on file"
            )
        )
    if inp.vendor_age_days < NEW_VENDOR_DAYS:
        days = inp.vendor_age_days
        signals.append(
            FraudSignal(
                "vendor_age_lt_14d",
                WEIGHTS["vendor_age_lt_14d"],
                f"Vendor record {days} day{'s' if days != 1 else ''} old",
                {"age_days": str(days)},
            )
        )
    if not inp.has_po:
        signals.append(FraudSignal("no_po", WEIGHTS["no_po"], "No purchase order"))
    if inp.remit_address_new:
        signals.append(
            FraudSignal(
                "remit_address_new",
                WEIGHTS["remit_address_new"],
                "Remit-to address recently added or changed",
            )
        )
    z = amount_z(inp.amount, inp.history)
    if z is not None and z > ANOMALY_Z:
        z_txt = "∞" if z.is_infinite() else f"{quantize(z, 1)}"
        signals.append(
            FraudSignal(
                "amount_anomaly",
                WEIGHTS["amount_anomaly"],
                f"Amount is {z_txt}σ above this vendor's 90-day mean",
                {"z": z_txt},
            )
        )
    total = sum((s.weight for s in signals), Decimal(0))
    return FraudResult(score=quantize(min(Decimal(1), total), 2), signals=tuple(signals))
