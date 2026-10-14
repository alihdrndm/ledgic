"""LLM gateway: mode switch, per-request BYOK, price table, daily budget and cost ledger.

Every OpenAI call in Ledgic goes through `LlmGateway.metered(...)`:

    estimate → select llm_budget_reserve(est, cap) → call → settle(actual from usage) → cost_ledger row

* `LLM_MODE=fixture` never builds an OpenAI client, so nothing can touch the network.
* A BYOK key (`X-OpenAI-Key`) is used for that request only: it is never logged, stored or put in the
  ledger, and it skips the owner's daily budget. The call is still written to `cost_ledger` with
  `meta.billing = 'byok'` so the cost KPIs stay truthful.
* Over budget → `BudgetExceeded`; callers degrade (recorded output, retrieval-only answer, template draft).
* The budget fails closed: if the RPC is missing or errors, the call is refused.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Protocol

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from openai import AsyncOpenAI

log = logging.getLogger("ledgic.ai.gateway")

# USD per 1M tokens. Override per deployment by editing this table (prices change; keep in sync with
# https://openai.com/api/pricing). Unknown models fall back to the most expensive row (conservative).
PRICE_TABLE: dict[str, dict[str, Decimal]] = {
    "gpt-4.1-mini": {"input": Decimal("0.40"), "cached_input": Decimal("0.10"), "output": Decimal("1.60")},
    "gpt-4.1-nano": {"input": Decimal("0.10"), "cached_input": Decimal("0.025"), "output": Decimal("0.40")},
    "gpt-4.1": {"input": Decimal("2.00"), "cached_input": Decimal("0.50"), "output": Decimal("8.00")},
    "text-embedding-3-small": {
        "input": Decimal("0.02"),
        "cached_input": Decimal("0.02"),
        "output": Decimal(0),
    },
}
_FALLBACK_PRICE = PRICE_TABLE["gpt-4.1"]
_MILLION = Decimal(1_000_000)
_MICRO = Decimal("0.000001")


class BudgetExceeded(Exception):
    """The owner's daily LLM budget would be exceeded (or cannot be checked). Callers degrade."""


class LlmUnavailable(Exception):
    """No LLM can be called: fixture mode or no API key configured."""


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    requests: int = 0

    def __iadd__(self, other: TokenUsage) -> TokenUsage:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_tokens += other.cached_tokens
        self.requests += other.requests
        return self


def price_for(model: str) -> dict[str, Decimal]:
    if model in PRICE_TABLE:
        return PRICE_TABLE[model]
    for name, row in PRICE_TABLE.items():  # dated snapshots, e.g. gpt-4.1-mini-2025-04-14
        if model.startswith(name + "-"):
            return row
    return _FALLBACK_PRICE


def cost_usd(model: str, usage: TokenUsage) -> Decimal:
    p = price_for(model)
    cached = min(usage.cached_tokens, usage.input_tokens)
    fresh = usage.input_tokens - cached
    total = (fresh * p["input"] + cached * p["cached_input"] + usage.output_tokens * p["output"]) / _MILLION
    return total.quantize(_MICRO, rounding=ROUND_HALF_UP)


def estimate_usd(model: str, input_tokens: int, max_output_tokens: int) -> Decimal:
    """Upper-bound estimate reserved before the call (no cache discount, full output budget)."""
    p = price_for(model)
    est = (input_tokens * p["input"] + max_output_tokens * p["output"]) / _MILLION
    return max(_MICRO, est.quantize(_MICRO, rounding=ROUND_HALF_UP))


class BudgetStore(Protocol):
    async def reserve(self, est: Decimal, cap: Decimal) -> str | None: ...
    async def settle(self, reservation_id: str, actual: Decimal) -> None: ...
    async def record_cost(
        self, org_id: str | None, run_id: str | None, amount: Decimal, meta: dict[str, Any]
    ) -> None: ...


class PgBudgetStore:
    """`llm_budget_reserve` / `llm_budget_settle` RPCs (contracts/rpc.md) + `cost_ledger`."""

    async def reserve(self, est: Decimal, cap: Decimal) -> str | None:
        from psycopg import errors

        from app.db.pool import connection

        try:
            async with connection() as conn:
                try:
                    cur = await conn.execute(
                        "select public.llm_budget_reserve(%s::numeric, %s::numeric) as id", (est, cap)
                    )
                except errors.UndefinedFunction:
                    await conn.rollback()
                    cur = await conn.execute("select public.llm_budget_reserve(%s::numeric) as id", (est,))
                row = await cur.fetchone()
                await conn.commit()
        except Exception as exc:  # fail closed: no budget check, no call
            log.warning("llm budget reserve failed: %s", type(exc).__name__)
            raise BudgetExceeded("LLM budget unavailable") from exc
        rid = row["id"] if row else None
        return str(rid) if rid else None

    async def settle(self, reservation_id: str, actual: Decimal) -> None:
        from app.db.pool import connection

        try:
            async with connection() as conn:
                await conn.execute(
                    "select public.llm_budget_settle(%s::uuid, %s::numeric)", (reservation_id, actual)
                )
                await conn.commit()
        except Exception as exc:  # the scheduler releases stale reservations
            log.warning("llm budget settle failed: %s", type(exc).__name__)

    async def record_cost(
        self, org_id: str | None, run_id: str | None, amount: Decimal, meta: dict[str, Any]
    ) -> None:
        if not org_id:
            return
        from app.db.pool import connection

        try:
            async with connection() as conn:
                await conn.execute(
                    "insert into public.cost_ledger (org_id, run_id, kind, amount_usd, meta)"
                    " values (%s, %s, 'llm', %s, %s::jsonb)",
                    (org_id, run_id, amount, json.dumps(meta)),
                )
                await conn.commit()
        except Exception as exc:
            log.warning("cost_ledger insert failed: %s", type(exc).__name__)


@dataclass
class Meter:
    """Handle yielded by `LlmGateway.metered`; add token usage as responses arrive."""

    purpose: str
    model: str
    billing: str  # owner | byok
    estimate_usd: Decimal
    client: AsyncOpenAI = field(repr=False)
    reservation_id: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)

    def add(self, usage: TokenUsage) -> None:
        self.usage += usage

    def add_agents_usage(self, u: Any) -> None:
        """Add an `agents.usage.Usage` (RunResult.context_wrapper.usage)."""
        details = getattr(u, "input_tokens_details", None)
        self.add(
            TokenUsage(
                input_tokens=int(getattr(u, "input_tokens", 0) or 0),
                output_tokens=int(getattr(u, "output_tokens", 0) or 0),
                cached_tokens=int(getattr(details, "cached_tokens", 0) or 0) if details else 0,
                requests=int(getattr(u, "requests", 0) or 0),
            )
        )

    @property
    def cost_usd(self) -> Decimal:
        return cost_usd(self.model, self.usage)


class LlmGateway:
    def __init__(self, settings: Settings | None = None, store: BudgetStore | None = None) -> None:
        self.settings = settings or get_settings()
        self.store: BudgetStore = store or PgBudgetStore()

    @property
    def mode(self) -> str:
        return self.settings.llm_mode

    @property
    def chat_model(self) -> str:
        return self.settings.llm_model

    @property
    def embed_model(self) -> str:
        return self.settings.embed_model

    def can_call(self, api_key: str | None = None) -> bool:
        return self.mode == "live" and bool(api_key or self.settings.openai_api_key)

    def client(self, api_key: str | None = None) -> AsyncOpenAI:
        """A fresh client per call (BYOK keys never outlive the request). Fixture mode refuses."""
        if self.mode != "live":
            raise LlmUnavailable("LLM_MODE=fixture: network calls are disabled")
        key = api_key or self.settings.openai_api_key
        if not key:
            raise LlmUnavailable("no OpenAI API key configured")
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=key, max_retries=1, timeout=90.0)

    @asynccontextmanager
    async def metered(
        self,
        *,
        purpose: str,
        org_id: str | None,
        model: str | None = None,
        est_input_tokens: int,
        max_output_tokens: int,
        api_key: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Meter]:
        """Reserve budget, yield a Meter (with a client), then settle and write the ledger row."""
        model = model or self.chat_model
        client = self.client(api_key)  # raises LlmUnavailable before any reservation
        billing = "byok" if api_key else "owner"
        est = estimate_usd(model, est_input_tokens, max_output_tokens)
        reservation: str | None = None
        if billing == "owner":
            reservation = await self.store.reserve(est, self.settings.llm_daily_cap_usd)
            if reservation is None:
                raise BudgetExceeded(f"daily LLM budget of ${self.settings.llm_daily_cap_usd} reached")
        meter = Meter(purpose, model, billing, est, client, reservation)
        failed = False
        try:
            yield meter
        except BaseException:
            failed = True
            raise
        finally:
            actual = meter.cost_usd
            if reservation is not None:
                await self.store.settle(reservation, actual)
            if actual > 0 or not failed:
                meta = {
                    "model": model,
                    "purpose": purpose,
                    "billing": billing,
                    "input_tokens": meter.usage.input_tokens,
                    "cached_tokens": meter.usage.cached_tokens,
                    "output_tokens": meter.usage.output_tokens,
                    "requests": meter.usage.requests,
                    "estimate_usd": str(est),
                    "failed": failed,
                }
                await self.store.record_cost(org_id, run_id, actual, meta)
            log.info(
                "llm call purpose=%s model=%s billing=%s in=%d out=%d cost=%s failed=%s",
                purpose,
                model,
                billing,
                meter.usage.input_tokens,
                meter.usage.output_tokens,
                actual,
                failed,
            )

    async def embed(
        self,
        texts: Sequence[str],
        *,
        org_id: str | None,
        purpose: str = "embed",
        api_key: str | None = None,
        run_id: str | None = None,
    ) -> list[list[float]]:
        """One embeddings request (callers batch). Raises BudgetExceeded / LlmUnavailable."""
        est_tokens = sum(len(t) // 3 + 1 for t in texts)
        async with self.metered(
            purpose=purpose,
            org_id=org_id,
            model=self.embed_model,
            est_input_tokens=est_tokens,
            max_output_tokens=0,
            api_key=api_key,
            run_id=run_id,
        ) as m:
            resp = await m.client.embeddings.create(
                model=self.embed_model, input=list(texts), dimensions=self.settings.embed_dims
            )
            m.add(TokenUsage(input_tokens=resp.usage.prompt_tokens, requests=1))
        return [list(d.embedding) for d in resp.data]


async def budget_remaining() -> Decimal | None:
    """Today's remaining owner budget (UTC day), or None if unknown. For /health and the copilot banner."""
    from app.db.pool import connection

    try:
        async with connection() as conn:
            cur = await conn.execute(
                "select cap_usd - spent_usd - reserved_usd as remaining from public.llm_budget"
                " where day = (now() at time zone 'utc')::date"
            )
            row = await cur.fetchone()
    except Exception:
        return None
    if row is None:
        return get_settings().llm_daily_cap_usd
    return max(Decimal(0), Decimal(row["remaining"]))


_gateway: LlmGateway | None = None


def get_gateway() -> LlmGateway:
    global _gateway
    if _gateway is None:
        _gateway = LlmGateway()
    return _gateway


def set_gateway(gw: LlmGateway | None) -> None:
    """Test hook / app startup override."""
    global _gateway
    _gateway = gw
