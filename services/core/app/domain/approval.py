"""Approval authority (01 §1, §4.7). Mirrors the DB RPC checks for UI gating and MCP tool responses;
the database remains the enforcement point."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal

from .money import D, Numberish

DEFAULT_MANAGER_LIMIT = Decimal("5000.00")
ROLE_RANK = {"viewer": 0, "ap_clerk": 1, "ap_manager": 2, "controller": 3, "admin": 4}

READ_ONLY = "Read-only access"
NEEDS_MANAGER = "Needs AP manager"
NEEDS_CONTROLLER = "Needs controller"
SOD_EDITED = "You edited this invoice's amounts — another approver must decide"
SOD_VENDOR = "You created this vendor record — another controller must release it"

# Actions an AP clerk may take (no money decision involved).
CLERK_ACTIONS = frozenset({"confirm_fields", "link_po"})
# Actions that never move money and so are exempt from the segregation-of-duties check.
SOD_EXEMPT = frozenset({"confirm_fields", "link_po"})
CONTROLLER_ACTIONS = frozenset({"not_duplicate", "release_hold"})
CONTROLLER_TYPES = frozenset({"new_vendor_screen"})


@dataclass(frozen=True)
class ApprovalCheck:
    allowed: bool
    required_role: str
    reason: str | None  # tooltip when not allowed


def required_role(
    action: str,
    exception_type: str | None,
    impact: Numberish,
    *,
    manager_limit: Numberish = DEFAULT_MANAGER_LIMIT,
) -> str:
    """Minimum role for a decision. Fraud screens and not-duplicate → controller; impact above the manager
    limit → controller; clerk-level actions → ap_clerk; everything else → ap_manager."""
    if action in CONTROLLER_ACTIONS or exception_type in CONTROLLER_TYPES:
        return "controller"
    if action in CLERK_ACTIONS:
        return "ap_clerk"
    if D(impact) > D(manager_limit):
        return "controller"
    return "ap_manager"


def can_decide(
    role: str,
    action: str,
    *,
    exception_type: str | None = None,
    impact: Numberish = 0,
    actor_id: str | None = None,
    monetary_editor_ids: Collection[str] = (),
    vendor_creator_id: str | None = None,
    manager_limit: Numberish = DEFAULT_MANAGER_LIMIT,
) -> ApprovalCheck:
    need = required_role(action, exception_type, impact, manager_limit=manager_limit)
    rank = ROLE_RANK.get(role, 0)
    if rank == 0:
        return ApprovalCheck(False, need, READ_ONLY)
    if rank < ROLE_RANK[need]:
        return ApprovalCheck(False, need, NEEDS_CONTROLLER if need == "controller" else NEEDS_MANAGER)
    if actor_id is not None and action not in SOD_EXEMPT and actor_id in monetary_editor_ids:
        return ApprovalCheck(False, need, SOD_EDITED)
    if action == "release_hold" and actor_id is not None and actor_id == vendor_creator_id:
        return ApprovalCheck(False, need, SOD_VENDOR)
    return ApprovalCheck(True, need, None)
