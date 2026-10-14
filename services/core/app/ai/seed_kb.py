"""Seed the knowledge base and precompute copilot answers for the suggested questions.

    uv run python -m app.ai.seed_kb [--org <uuid>] [--no-cache]

Indexes every markdown file under tools/corpus/kb for the org (contract placeholders filled from the
`contracts` table), then answers SUGGESTED_QUESTIONS and stores them in `copilot_cache`. In fixture mode
(or with no budget) the cached answers are deterministic retrieval-only answers ($0).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from .copilot import SUGGESTED_QUESTIONS, ask, cache_put
from .rag.index import index_kb

NORTHSIDE_ORG_ID = "992e72b7-9d9b-5104-9051-f5ef581c99e0"  # contracts/fixtures.json org.id

log = logging.getLogger("ledgic.ai.seed")


async def seed_kb(org_id: str = NORTHSIDE_ORG_ID, *, precompute: bool = True) -> dict[str, Any]:
    stats = await index_kb(org_id)
    answers: dict[str, str] = {}
    if precompute:
        for q in SUGGESTED_QUESTIONS:
            ans = await ask(org_id, q, use_cache=False)
            await cache_put(org_id, q, ans)
            answers[q] = ans.mode
    return {
        "documents": stats.documents,
        "chunks": stats.chunks,
        "embedding_scheme": stats.scheme,
        "unresolved": stats.unresolved,
        "cached_answers": answers,
    }


async def _main(org_id: str, precompute: bool) -> dict[str, Any]:
    from app.db.pool import close_pool, open_pool

    await open_pool()
    try:
        return await seed_kb(org_id, precompute=precompute)
    finally:
        await close_pool()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", default=NORTHSIDE_ORG_ID)
    ap.add_argument("--no-cache", action="store_true", help="skip precomputing copilot answers")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    if sys.platform == "win32":  # psycopg async needs a selector loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    result = asyncio.run(_main(args.org, not args.no_cache))
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
