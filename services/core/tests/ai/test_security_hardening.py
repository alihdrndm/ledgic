"""Hardening from the 2026-10 security audit: read-only MCP tokens never spend live AI, the draft money
guard sees bare amounts and account numbers, and the cache warm-up never re-buys an answer."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.ai import copilot
from app.ai.resolution import money_figures, money_guard

ORG = "992e72b7-9d9b-5104-9051-f5ef581c99e0"
Q = "What does clause 4.2 of the Protein Supplier agreement say about shrimp?"


async def test_allow_live_false_never_reaches_the_model(live_gateway, monkeypatch: pytest.MonkeyPatch) -> None:
    async def miss(*a: Any, **k: Any) -> None:
        return None

    async def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("live model called")

    async def retrieval(org_id: str, question: str, context: Any = None, reason: str = "fixture") -> Any:
        return copilot.CopilotAnswer("kb", [], "retrieval_only", None, [], Decimal(0), copilot._NOTICES[reason])

    monkeypatch.setattr(copilot, "cache_get", miss)
    monkeypatch.setattr(copilot, "_ask_live", boom)
    monkeypatch.setattr(copilot, "answer_retrieval_only", retrieval)
    ans = await copilot.ask(ORG, Q, allow_live=False)
    assert ans.mode == "retrieval_only" and ans.notice == copilot._NOTICES["read_only"]


@pytest.mark.parametrize(("scopes", "live"), [(("read",), False), (("read", "decide"), True)])
async def test_mcp_only_lets_deciding_tokens_spend(monkeypatch: pytest.MonkeyPatch, scopes, live) -> None:
    from app.mcp import service
    from app.mcp.auth import TokenContext

    seen: dict[str, Any] = {}

    async def fake_ask(org_id: str, question: str, allow_live: bool = True, **k: Any) -> Any:
        seen["allow_live"] = allow_live
        return copilot.CopilotAnswer("a", [], "cached")

    monkeypatch.setattr(copilot, "ask", fake_ask)
    await service.ask_ledgic(TokenContext("t", "u", ORG, scopes), Q)
    assert seen["allow_live"] is live


@pytest.mark.parametrize(
    "text",
    ["Please pay 1,234.56 today.", "We will credit €900.", "Send it to account 123456789.", "Pay 2759.61 now."],
)
def test_money_guard_catches_amounts_without_a_dollar_sign(text: str) -> None:
    assert not money_guard(text, {Decimal("2759.60"), Decimal("88.00")}).passed


@pytest.mark.parametrize(
    "text",
    [
        "Shrimp is 12.0% over contract (clause 4.2); confidence 0.94.",
        "Invoice PS-88214 and BD-104882, dated 2026-10-15, 10 cases of 2lb.",
        "We pay $2,759.60 and hold 88.00 USD.",
    ],
)
def test_money_guard_leaves_non_money_numbers_alone(text: str) -> None:
    assert money_guard(text, {Decimal("2759.60"), Decimal("88.00")}).passed, money_figures(text)


async def test_warm_cache_only_buys_missing_cacheable_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    cached = {copilot.normalize_question("What is our price-variance tolerance?")}
    asked: list[str] = []

    async def get(org_id: str, q: str) -> Any:
        return object() if copilot.normalize_question(q) in cached else None

    async def fake_ask(org_id: str, q: str, **k: Any) -> Any:
        assert k.get("refresh") is True
        asked.append(q)
        cached.add(copilot.normalize_question(q))
        return copilot.CopilotAnswer("a", [], "live")

    monkeypatch.setattr(copilot, "cache_get", get)
    monkeypatch.setattr(copilot, "ask", fake_ask)
    out = await copilot.warm_cache(ORG)

    assert "What is our price-variance tolerance?" not in asked  # already cached: not re-bought
    assert "Why is PS-88214 on hold?" not in asked  # names an invoice: always fresh
    assert "Which exceptions are blocking payments right now?" not in asked  # live data
    assert Q in asked and out[Q] == "live, cached"
