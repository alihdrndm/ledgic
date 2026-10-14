"""Stage handlers: `async (StageContext, RunRow) -> Transition`."""

from __future__ import annotations

from ..stages import Stage
from . import approval, close, enrichment, extraction, intake, match, posting, review, screening

HANDLERS = {
    Stage.INTAKE: intake.handle,
    Stage.EXTRACTION: extraction.handle,
    Stage.REVIEW: review.handle,
    Stage.ENRICHMENT: enrichment.handle,
    Stage.SCREENING: screening.handle,
    Stage.MATCH: match.handle,
    Stage.APPROVAL: approval.handle,
    Stage.POSTING: posting.handle,
    Stage.CLOSE: close.handle,
}

EXHAUSTED = {Stage.POSTING: posting.exhausted}

__all__ = ["EXHAUSTED", "HANDLERS"]
