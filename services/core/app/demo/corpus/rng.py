"""Deterministic randomness and identifiers.

Never use ``hash()`` (salted per process) or the global ``random`` module: every value in the
synthetic tenant derives from ``SEED`` plus a stable string key, so the corpus is reproducible
byte-for-byte across machines and processes.
"""

from __future__ import annotations

import hashlib
import random
import uuid

SEED = 20260713

# Namespace for every deterministic UUID in the demo tenant (uuid5 over "<kind>:<key>").
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://ledgic.dev/demo/northside")


def derive_seed(*parts: object) -> int:
    """A 64-bit integer seed derived from the parts (stable across processes)."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(*parts: object) -> random.Random:
    return random.Random(derive_seed(*parts))


def stable_uuid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()
