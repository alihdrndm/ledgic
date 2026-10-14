from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_PATH = Path(__file__).resolve().parents[4] / "contracts" / "fixtures.json"


@pytest.fixture(scope="session")
def fixtures() -> dict[str, Any]:
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def heroes(fixtures: dict[str, Any]) -> dict[str, Any]:
    return fixtures["heroes"]


@pytest.fixture(scope="session")
def policy(fixtures: dict[str, Any]) -> dict[str, Any]:
    return fixtures["policy"]
