from decimal import Decimal

import pytest

from app.domain.approval import (
    NEEDS_CONTROLLER,
    NEEDS_MANAGER,
    READ_ONLY,
    SOD_EDITED,
    SOD_VENDOR,
    can_decide,
    required_role,
)
from app.domain.gl_knn import Neighbour, predict_gl
from app.domain.vendor_resolve import VendorRecord, hash_tax_id, normalize_vendor_name, resolve_vendor

VENDORS = [
    VendorRecord(
        "v-protein", "Protein Supplier", ("Protein Supplier Co.", "PSC Seafood"), hash_tax_id("12-3456789")
    ),
    VendorRecord("v-produce", "Produce Supplier", ("Produce Supplier LLC",)),
    VendorRecord("v-broadline", "Broadline Distributor"),
]


def test_normalize_vendor_name() -> None:
    assert normalize_vendor_name("Protein Supplier, Inc.") == "protein supplier"
    assert normalize_vendor_name("Smith & Sons LLC") == "smith and sons"


def test_alias_then_tax_then_fuzzy_then_new() -> None:
    a = resolve_vendor("PSC SEAFOOD", VENDORS)
    assert a.vendor_id == "v-protein" and a.method == "alias" and a.confidence == Decimal("1.000")
    t = resolve_vendor("Totally Different Name", VENDORS, tax_id_hash=hash_tax_id("123456789"))
    assert t.vendor_id == "v-protein" and t.method == "tax_id"
    f = resolve_vendor("Broadline Distributors", VENDORS)
    assert f.vendor_id == "v-broadline" and f.method == "fuzzy" and f.score is not None and f.score >= 90
    n = resolve_vendor("Unlisted Supplier", VENDORS)
    assert n.is_new and n.vendor_id is None and n.confidence == 0
    assert resolve_vendor(None, VENDORS).is_new
    assert hash_tax_id("n/a") is None
    assert hash_tax_id("123", salt="org") != hash_tax_id("123")


def test_gl_majority_vote() -> None:
    nbrs = [Neighbour("5000 COGS-Food", Decimal("0.92"))] * 5 + [Neighbour("5100 COGS-Bev", 0.95)] * 2
    nbrs += [Neighbour("6000 Supplies", 0.10)]  # 8th neighbour is beyond k=7
    p = predict_gl(nbrs)
    assert p.gl_code == "5000 COGS-Food" and p.source == "knn"
    # share 5/7 × mean 0.92 = 0.657
    assert p.confidence == Decimal("0.657")
    assert p.votes == {"5100 COGS-Bev": 2, "5000 COGS-Food": 5}


def test_gl_tie_break_and_fallbacks() -> None:
    tie = predict_gl([Neighbour("A", 0.9), Neighbour("B", 0.8)])
    assert tie.gl_code == "A"
    assert predict_gl([], item_default_gl="5000").source == "item_default"
    assert predict_gl([], vendor_default_gl="6000").confidence == Decimal("0.300")
    none = predict_gl([Neighbour("", 0.9)])
    assert none.gl_code is None and none.source == "none"


@pytest.mark.parametrize(
    ("role", "action", "etype", "impact", "allowed", "reason"),
    [
        ("viewer", "short_pay", "price_variance", "88.00", False, READ_ONLY),
        ("viewer", "confirm_fields", "extraction_review", "0", False, READ_ONLY),
        ("ap_clerk", "confirm_fields", "extraction_review", "0", True, None),
        ("ap_clerk", "link_po", "no_po", "2214.85", True, None),
        ("ap_clerk", "short_pay", "price_variance", "88.00", False, NEEDS_MANAGER),
        ("ap_clerk", "approve_without_po", "no_po", "100.00", False, NEEDS_MANAGER),
        ("ap_manager", "short_pay", "price_variance", "88.00", True, None),
        ("ap_manager", "approve_as_is", "price_variance", "5000.00", True, None),
        ("ap_manager", "approve_as_is", "price_variance", "5000.01", False, NEEDS_CONTROLLER),
        ("ap_manager", "merge", "duplicate", "612.40", True, None),
        ("ap_manager", "not_duplicate", "duplicate", "612.40", False, NEEDS_CONTROLLER),
        ("ap_manager", "release_hold", "new_vendor_screen", "2214.85", False, NEEDS_CONTROLLER),
        ("ap_manager", "request_w9", "new_vendor_screen", "2214.85", False, NEEDS_CONTROLLER),
        ("controller", "release_hold", "new_vendor_screen", "2214.85", True, None),
        ("controller", "approve_as_is", "price_variance", "99999.00", True, None),
        ("admin", "not_duplicate", "duplicate", "10.00", True, None),
        ("stranger", "short_pay", "price_variance", "1", False, READ_ONLY),
    ],
)
def test_authority(
    role: str, action: str, etype: str, impact: str, allowed: bool, reason: str | None
) -> None:
    c = can_decide(role, action, exception_type=etype, impact=impact)
    assert c.allowed is allowed and c.reason == reason


def test_segregation_of_duties() -> None:
    sod = can_decide(
        "ap_manager",
        "short_pay",
        exception_type="price_variance",
        impact="88.00",
        actor_id="elena",
        monetary_editor_ids={"elena"},
    )
    assert not sod.allowed and sod.reason == SOD_EDITED
    # Confirming fields is the edit itself, not an approval.
    assert can_decide("ap_clerk", "confirm_fields", actor_id="elena", monetary_editor_ids={"elena"}).allowed
    vendor = can_decide(
        "controller",
        "release_hold",
        exception_type="new_vendor_screen",
        impact="2214.85",
        actor_id="tom",
        vendor_creator_id="tom",
    )
    assert not vendor.allowed and vendor.reason == SOD_VENDOR
    other = can_decide(
        "controller",
        "release_hold",
        exception_type="new_vendor_screen",
        impact="2214.85",
        actor_id="tom",
        vendor_creator_id="someone",
        monetary_editor_ids={"elena"},
    )
    assert other.allowed


def test_required_role_custom_limit() -> None:
    assert required_role("short_pay", "price_variance", "1500", manager_limit="1000") == "controller"
    assert required_role("dispute", "price_variance", "100") == "ap_manager"
