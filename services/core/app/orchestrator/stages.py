"""Pipeline stages, in order (06 §2.1 reimplemented as code; DECISIONS D1)."""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    INTAKE = "intake"
    EXTRACTION = "extraction"
    REVIEW = "review"
    ENRICHMENT = "enrichment"
    SCREENING = "screening"
    MATCH = "match"
    APPROVAL = "approval"
    POSTING = "posting"
    CLOSE = "close"


ORDER: tuple[Stage, ...] = tuple(Stage)


def next_of(stage: Stage) -> Stage | None:
    i = ORDER.index(stage)
    return ORDER[i + 1] if i + 1 < len(ORDER) else None
