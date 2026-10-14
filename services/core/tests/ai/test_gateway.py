from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from app.ai.gateway import (
    BudgetExceeded,
    LlmGateway,
    LlmUnavailable,
    TokenUsage,
    cost_usd,
    estimate_usd,
    price_for,
)

from .conftest import MemoryBudgetStore, make_settings

ORG = "992e72b7-9d9b-5104-9051-f5ef581c99e0"


def test_price_table_math() -> None:
    # gpt-4.1-mini: $0.40 / 1M in, $0.10 cached, $1.60 out
    assert cost_usd("gpt-4.1-mini", TokenUsage(1000, 500)) == Decimal("0.001200")
    assert cost_usd("gpt-4.1-mini", TokenUsage(1000, 0, cached_tokens=1000)) == Decimal("0.000100")
    assert cost_usd("text-embedding-3-small", TokenUsage(1_000_000, 0)) == Decimal("0.020000")
    assert price_for("gpt-4.1-mini-2025-04-14") == price_for("gpt-4.1-mini")
    assert price_for("some-unknown-model") == price_for("gpt-4.1")  # conservative fallback
    assert estimate_usd("gpt-4.1-mini", 10_000, 1_500) == Decimal("0.006400")


async def test_reserve_call_settle_and_ledger(store: MemoryBudgetStore) -> None:
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key="sk-owner"), store)
    async with gw.metered(
        purpose="copilot", org_id=ORG, est_input_tokens=10_000, max_output_tokens=1_500
    ) as m:
        assert store.reserved == Decimal("0.006400")
        m.add(TokenUsage(2_000, 300, requests=1))
    assert store.reserved == 0
    assert store.spent == Decimal("0.001280")
    [row] = store.ledger
    assert row["org_id"] == ORG and row["amount"] == Decimal("0.001280")
    assert row["meta"]["billing"] == "owner" and row["meta"]["purpose"] == "copilot"
    assert row["meta"]["input_tokens"] == 2000 and row["meta"]["output_tokens"] == 300
    assert row["meta"]["model"] == "gpt-4.1-mini"


async def test_budget_refusal_raises_and_spends_nothing() -> None:
    store = MemoryBudgetStore(cap=Decimal("0.001"))
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key="sk-owner"), store)
    with pytest.raises(BudgetExceeded):
        async with gw.metered(
            purpose="copilot", org_id=ORG, est_input_tokens=10_000, max_output_tokens=1_500
        ):
            raise AssertionError("must not run")
    assert store.spent == 0 and store.reserved == 0 and store.ledger == []


async def test_failed_call_settles_actual_usage(store: MemoryBudgetStore) -> None:
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key="sk-owner"), store)
    with pytest.raises(RuntimeError):
        async with gw.metered(purpose="x", org_id=ORG, est_input_tokens=1000, max_output_tokens=100) as m:
            m.add(TokenUsage(1000, 0))
            raise RuntimeError("api blew up")
    assert store.reserved == 0 and store.spent == Decimal("0.000400")
    assert store.ledger[0]["meta"]["failed"] is True


async def test_failed_call_without_usage_releases_reservation(store: MemoryBudgetStore) -> None:
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key="sk-owner"), store)
    with pytest.raises(RuntimeError):
        async with gw.metered(purpose="x", org_id=ORG, est_input_tokens=1000, max_output_tokens=100):
            raise RuntimeError("timeout")
    assert store.reserved == 0 and store.spent == 0 and store.ledger == []
    assert list(store.settled.values()) == [Decimal(0)]


async def test_byok_skips_budget_and_is_never_logged(
    store: MemoryBudgetStore, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "sk-byok-SECRET-1234567890"
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key=""), store)
    caplog.set_level(logging.DEBUG)
    async with gw.metered(
        purpose="copilot", org_id=ORG, est_input_tokens=1000, max_output_tokens=100, api_key=secret
    ) as m:
        assert m.billing == "byok"
        assert m.client.api_key == secret  # used for this call only
        m.add(TokenUsage(1000, 100))
    assert store.reserve_calls == 0  # owner budget untouched
    [row] = store.ledger
    assert row["meta"]["billing"] == "byok"
    assert secret not in repr(store.ledger)
    assert secret not in caplog.text
    assert not any(secret in repr(v) for v in vars(gw).values())  # not stored on the gateway


def test_fixture_mode_refuses_clients(no_network: None) -> None:
    gw = LlmGateway(make_settings(llm_mode="fixture", openai_api_key="sk-owner"), MemoryBudgetStore())
    assert not gw.can_call() and not gw.can_call("sk-byok")
    with pytest.raises(LlmUnavailable):
        gw.client()
    with pytest.raises(LlmUnavailable):
        gw.client("sk-byok")


def test_live_mode_without_key_is_unavailable() -> None:
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key=""), MemoryBudgetStore())
    assert not gw.can_call()
    assert gw.can_call("sk-byok")
    with pytest.raises(LlmUnavailable):
        gw.client()


async def test_embed_goes_through_budget(store: MemoryBudgetStore, monkeypatch: pytest.MonkeyPatch) -> None:
    gw = LlmGateway(make_settings(llm_mode="live", openai_api_key="sk-owner"), store)

    class _Resp:
        class usage:  # noqa: N801
            prompt_tokens = 12

        data = [type("D", (), {"embedding": [0.1] * 512})(), type("D", (), {"embedding": [0.2] * 512})()]

    class _Emb:
        async def create(self, **kw):
            assert kw["dimensions"] == 512 and kw["model"] == "text-embedding-3-small"
            return _Resp()

    class _Client:
        embeddings = _Emb()

    monkeypatch.setattr(gw, "client", lambda api_key=None: _Client())
    vecs = await gw.embed(["a", "b"], org_id=ORG)
    assert len(vecs) == 2 and len(vecs[0]) == 512
    assert store.ledger[0]["meta"]["model"] == "text-embedding-3-small"
    assert store.ledger[0]["meta"]["input_tokens"] == 12
