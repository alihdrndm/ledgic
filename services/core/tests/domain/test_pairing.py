import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.pairing import PairLine, normalize_uom, pair_lines, uom_compatible

PO = [
    PairLine("Shrimp 16/20 IQF 2lb × 10", "lb"),
    PairLine("Cod loin 10lb case", "cs"),
    PairLine("Scallops U-10 dry 2lb", "ea"),
    PairLine("Crab claw meat 5lb", "ea"),
    PairLine("Oysters select 1gal", "ea"),
]
NOISY_INVOICE = {
    0: PairLine("SHRIMP 16/20 IQF 2LB x10", "LBS"),
    1: PairLine("cod loin, 10 lb case", "case"),
    2: PairLine("Scallops U10 dry 2 lb", "each"),
    3: PairLine("crab claw meat (5lb)", "EA"),
    4: PairLine("Select oysters 1 gal", "ea"),
}


def test_hungarian_picks_correct_lines_with_shuffle_and_noise() -> None:
    order = [3, 0, 4, 1, 2]
    inv = [NOISY_INVOICE[k] for k in order]
    r = pair_lines(inv, PO)
    assert {p.invoice_index: p.po_index for p in r.pairs} == dict(enumerate(order))
    assert r.unmatched_invoice == () and r.unmatched_po == ()
    assert all(p.method == "description" and p.similarity >= 0.6 for p in r.pairs)
    assert r.po_for(0) == 3 and r.po_for(99) is None


def test_unmatched_below_threshold_and_extra_lines() -> None:
    inv = [NOISY_INVOICE[0], PairLine("Fuel surcharge", None)]
    r = pair_lines(inv, PO)
    assert r.po_for(0) == 0
    assert r.unmatched_invoice == (1,)
    assert set(r.unmatched_po) == {1, 2, 3, 4}


def test_uom_incompatibility_blocks_pair() -> None:
    r = pair_lines([PairLine("Cod loin 10lb case", "gal")], PO)
    assert r.pairs == () and r.unmatched_invoice == (0,)


def test_sku_wins() -> None:
    po = [PairLine("Item A", "ea", "SKU-1"), PairLine("Item B", "ea", "SKU-2")]
    r = pair_lines([PairLine("totally different words", "ea", "sku-2")], po)
    assert r.pairs[0].po_index == 1 and r.pairs[0].method == "sku" and r.pairs[0].similarity == 1.0


def test_embedding_blend_can_rescue_a_pair() -> None:
    inv = [PairLine("prawns jumbo frozen", "lb")]
    without = pair_lines(inv, PO[:2])
    assert without.pairs == ()
    with_emb = pair_lines(inv, PO[:2], embedding_sim=[[0.95, 0.1]], embedding_weight=0.8)
    assert with_emb.po_for(0) == 0
    with pytest.raises(ValueError):
        pair_lines(inv, PO[:2], embedding_sim=[[0.9]])


def test_empty_inputs() -> None:
    assert pair_lines([], PO).unmatched_po == (0, 1, 2, 3, 4)
    assert pair_lines([PairLine("x")], []).unmatched_invoice == (0,)


def test_uom_helpers() -> None:
    assert (
        normalize_uom(" Lbs. ") == "lb" and normalize_uom(None) is None and normalize_uom("crate") == "crate"
    )
    assert uom_compatible("lb", "kg") and uom_compatible(None, "cs") and not uom_compatible("cs", "ea")


@settings(max_examples=30, deadline=None)
@given(st.permutations(list(range(5))))
def test_property_assignment_invariant_under_shuffle(perm: list[int]) -> None:
    po = [PO[i] for i in perm]
    inv = [NOISY_INVOICE[i] for i in range(5)]
    random.Random(0).shuffle(inv)
    r = pair_lines(inv, po)
    for p in r.pairs:
        assert po[p.po_index] is PO[[k for k, v in NOISY_INVOICE.items() if v is inv[p.invoice_index]][0]]
