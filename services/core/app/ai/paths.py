"""Locations of the knowledge-base markdown and recorded hero fixtures.

Both live under `tools/corpus/` in the repo. In a container, set `LEDGIC_KB_DIR` /
`LEDGIC_FIXTURES_DIR` (or copy `tools/corpus/{kb,fixtures}` next to the app) so they resolve.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _find_upwards(rel: str) -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / rel
        if cand.is_dir():
            return cand
    return None


@lru_cache
def kb_dir() -> Path:
    env = os.environ.get("LEDGIC_KB_DIR")
    if env:
        return Path(env)
    found = _find_upwards("tools/corpus/kb")
    if found is None:
        raise FileNotFoundError("knowledge base not found; set LEDGIC_KB_DIR")
    return found


@lru_cache
def fixtures_dir() -> Path:
    env = os.environ.get("LEDGIC_FIXTURES_DIR")
    if env:
        return Path(env)
    found = _find_upwards("tools/corpus/fixtures")
    if found is None:
        raise FileNotFoundError("fixtures not found; set LEDGIC_FIXTURES_DIR")
    return found


def heroes_dir() -> Path:
    return fixtures_dir() / "heroes"


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
