from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.domain.fraud import FraudInputs, amount_z, bank_fingerprint, screen

W9 = bank_fingerprint("021000021", "111222333")
NEW_BANK = bank_fingerprint("026009593", "999888777")


def test_bank_fingerprint() -> None:
    assert bank_fingerprint("021-000-021", "111 222 333") == W9
    assert bank_fingerprint(None, "1") is None and bank_fingerprint("1", "") is None


def test_nv0001_hold_at_090(heroes: dict) -> None:
    hero = heroes["NV-0001"]
    r = screen(
        FraudInputs(
            amount=Decimal(hero["total"]),
            vendor_age_days=hero["vendor_age_days"],
            has_po=False,
            invoice_bank_fingerprint=NEW_BANK,
            w9_bank_fingerprint=W9,
            remit_address_new=True,
        )
    )
    assert r.score == Decimal(hero["expected"]["fraud_score"])
    assert r.hold
    assert [s.signal for s in r.signals] == hero["expected"]["signals"]
    assert r.label == "Signal score 0.90"
    labels = [s.label for s in r.signals]
    assert "Bank details differ from the W-9 on file" in labels
    assert "Vendor record 4 days old" in labels
    assert "No purchase order" in labels


def test_established_vendor_with_bank_match_scores_zero() -> None:
    history = tuple(Decimal(v) for v in ("1800.00", "1950.25", "2100.00", "1875.40", "2010.10", "1990.00"))
    r = screen(FraudInputs(Decimal("1982.47"), 900, True, W9, W9, False, history))
    assert r.score == 0 and not r.hold and r.signals == ()


def test_amount_anomaly_needs_five_points_and_z_over_3() -> None:
    history = tuple(Decimal(v) for v in ("100", "110", "90", "105", "95"))
    r = screen(FraudInputs(Decimal("1000"), 400, True, history=history))
    assert [s.signal for s in r.signals] == ["amount_anomaly"] and r.score == Decimal("0.10")
    assert r.signals[0].label.startswith("Amount is ") and not r.hold
    assert amount_z("1000", history[:4]) is None
    assert screen(FraudInputs(Decimal("1000"), 400, True, history=history[:4])).score == 0


def test_flat_history_std_zero() -> None:
    flat = tuple(Decimal("100") for _ in range(5))
    assert amount_z("100", flat) == 0
    r = screen(FraudInputs(Decimal("101"), 400, True, history=flat))
    assert r.signals[0].detail["z"] == "∞"


def test_one_day_old_label_and_cap() -> None:
    hist = tuple(Decimal(v) for v in ("10", "11", "9", "10", "10"))
    r = screen(FraudInputs(Decimal("5000"), 1, False, NEW_BANK, W9, True, hist))
    assert r.score == Decimal("1.00")  # 1.00 total, capped at 1
    assert "Vendor record 1 day old" in [s.label for s in r.signals]


def test_missing_w9_does_not_flag_bank() -> None:
    assert screen(FraudInputs(Decimal("10"), 400, True, NEW_BANK, None)).score == 0


@given(st.integers(0, 60), st.booleans(), st.booleans(), st.booleans())
def test_property_score_bounded(age: int, has_po: bool, bank_bad: bool, remit: bool) -> None:
    r = screen(FraudInputs(Decimal("100"), age, has_po, NEW_BANK if bank_bad else W9, W9, remit))
    assert Decimal(0) <= r.score <= Decimal(1)
    assert r.hold == (r.score >= Decimal("0.70"))
