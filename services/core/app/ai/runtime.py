"""Glue between the gateway Meter and the OpenAI Agents SDK.

Agents are declared once at module level without a model; each run gets a `RunConfig` whose model
wraps the per-request client from the gateway (owner key or BYOK). Tracing export is disabled so a
BYOK key is never reused for trace uploads and invoice data is not sent to the traces dashboard.
"""

from __future__ import annotations

from typing import Any

from agents import Agent, ModelSettings, RunConfig, Runner, RunResult, set_tracing_disabled
from agents.models.openai_responses import OpenAIResponsesModel

from .gateway import Meter

set_tracing_disabled(True)


def run_config(meter: Meter, *, max_tokens: int, temperature: float = 0.0, workflow: str) -> RunConfig:
    return RunConfig(
        model=OpenAIResponsesModel(model=meter.model, openai_client=meter.client),
        model_settings=ModelSettings(temperature=temperature, max_tokens=max_tokens, store=False),
        tracing_disabled=True,
        workflow_name=workflow,
    )


async def run_agent(
    agent: Agent[Any],
    input: Any,
    meter: Meter,
    *,
    max_tokens: int,
    max_turns: int,
    context: Any = None,
    workflow: str,
) -> RunResult:
    result = await Runner.run(
        agent,
        input,
        context=context,
        max_turns=max_turns,
        run_config=run_config(meter, max_tokens=max_tokens, workflow=workflow),
    )
    meter.add_agents_usage(result.context_wrapper.usage)
    return result
