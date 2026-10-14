"""AI layer: LLM gateway (budget, BYOK, fixture mode), extraction / resolution / copilot agents, RAG.

Public async API (all scoped by org; DB access via app.db.pool):

    extract_document(pages, *, mime, fixture=None, api_key=None, org_id=None, run_id=None, hero=None)
        -> ExtractionOutcome
    ask(org_id, question, context=None, api_key=None) -> CopilotAnswer
    stream_ask(org_id, question, context=None, api_key=None) -> AsyncIterator[event dict]  (+ sse())
    draft_for_exception(exception_id, api_key=None, *, kind="vendor_notice", regenerate=False) -> Draft
    search_kb(org_id, query, k=6, *, kinds=None, api_key=None) -> list[Chunk]
    index_kb(org_id, paths=None) / seed_kb(org_id)

Read-only data tools (also used by the MCP server) live in `app.ai.tools`.
"""

from .copilot import SUGGESTED_QUESTIONS, CopilotAnswer, ask, sse, stream_ask
from .extraction import ExtractionOutcome, ExtractionUnavailable, extract_document, load_hero_fixture
from .gateway import BudgetExceeded, LlmGateway, LlmUnavailable, budget_remaining, get_gateway
from .rag import Chunk, index_kb, search_kb
from .resolution import Draft, draft_for_exception, money_guard
from .schemas import ExtractionResult, normalize_extraction

__all__ = [
    "SUGGESTED_QUESTIONS",
    "BudgetExceeded",
    "Chunk",
    "CopilotAnswer",
    "Draft",
    "ExtractionOutcome",
    "ExtractionResult",
    "ExtractionUnavailable",
    "LlmGateway",
    "LlmUnavailable",
    "ask",
    "budget_remaining",
    "draft_for_exception",
    "extract_document",
    "get_gateway",
    "index_kb",
    "load_hero_fixture",
    "money_guard",
    "normalize_extraction",
    "search_kb",
    "sse",
    "stream_ask",
]
