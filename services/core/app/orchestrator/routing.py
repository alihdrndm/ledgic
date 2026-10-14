"""Where a parked run goes when a human decision resumes it (06 §2.1 steps 4, 6, 8; rpc.md).

Pure function so the branching is unit-tested without a database. The RPCs also set `next_stage`;
the orchestrator treats this table as the source of truth (e.g. confirm_fields first re-scores in
the review stage, then continues to enrichment).
"""

from __future__ import annotations

from .stages import Stage

PARK = "park"  # stay waiting on the same exception (dispute / request_w9)

_ROUTES: dict[str, Stage | str] = {
    "confirm_fields": Stage.REVIEW,  # rescore, then enrichment
    "short_pay": Stage.POSTING,
    "approve_as_is": Stage.POSTING,
    "approve_without_po": Stage.POSTING,
    "retry_posting": Stage.POSTING,
    "link_po": Stage.MATCH,  # re-pair lines against the linked PO and re-match
    "release_hold": Stage.SCREENING,  # next blocking hold, else match
    "not_duplicate": Stage.SCREENING,
    "merge": Stage.CLOSE,
    "reject_copy": Stage.CLOSE,
    "reject_invoice": Stage.CLOSE,
    "dispute": PARK,
    "request_w9": PARK,
}

DECISION_ACTIONS = frozenset(_ROUTES)


def route_resume(action: str, *, invoice_status: str | None = None) -> Stage | str:
    """Next stage for a decision, or PARK. `merge` keeps one invoice as the source of truth: when the
    copy marked duplicate is the *other* invoice, this run continues through screening."""
    if action not in _ROUTES:
        raise ValueError(f"unknown decision action {action!r}")
    target = _ROUTES[action]
    if action == "merge" and invoice_status not in ("duplicate", "rejected"):
        return Stage.SCREENING
    return target


def payment_terms(decisions: list[dict]) -> tuple[str | None, str | None]:
    """(pay_amount, hold_amount) from the latest short-pay decision, if any. Other approvals pay in full."""
    for d in reversed(decisions):
        if d.get("action") == "short_pay" and d.get("pay_amount") is not None:
            return str(d["pay_amount"]), str(d.get("hold_amount") or "0")
        if d.get("action") in ("approve_as_is", "approve_without_po", "release_hold", "not_duplicate"):
            return None, None
    return None, None
