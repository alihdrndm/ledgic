"""Embeddings for the knowledge base and queries (text-embedding-3-small @ 512 dims, DECISIONS D3).

Fixture mode (and any time the live call is unavailable at *index* time) uses a deterministic
hashed bag-of-words pseudo-embedding so local dev and CI work offline. It is lexical, not semantic:
with it, retrieval quality relies mostly on the full-text arm of `kb_search` (RRF still fuses both).
`retrieve.py` detects which scheme an org's index uses and embeds queries the same way.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from ..gateway import BudgetExceeded, LlmGateway, LlmUnavailable, get_gateway

DIMS = 512
BATCH = 96
HASH_SCHEME = "hash-bow-512"
_TOKEN = re.compile(r"[a-z0-9]+(?:[./][a-z0-9]+)*")
_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "the",
        "this",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "we",
        "you",
        "your",
        "can",
    ]
)


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def hash_embedding(text: str, dims: int = DIMS) -> list[float]:
    """Signed feature hashing of unigrams (+ bigrams at half weight), L2-normalized."""
    vec = [0.0] * dims
    toks = tokens(text)
    feats = [(t, 1.0) for t in toks] + [(f"{a} {b}", 0.5) for a, b in zip(toks, toks[1:], strict=False)]
    for feat, w in feats:
        h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % dims
        sign = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sign * w
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec[0] = 1.0
        return vec
    return [v / norm for v in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


async def embed_texts(
    texts: Sequence[str],
    *,
    org_id: str | None,
    api_key: str | None = None,
    purpose: str = "embed",
    scheme: str | None = None,
    gateway: LlmGateway | None = None,
) -> tuple[list[list[float]], str]:
    """Embed `texts`, returning (vectors, scheme). scheme is the model name or HASH_SCHEME.

    `scheme=HASH_SCHEME` forces the offline embedding (used when the index was built that way).
    In live mode BudgetExceeded / LlmUnavailable propagate: queries then go FTS-only, indexing
    falls back to the hash scheme (`embed_for_index`)."""
    gw = gateway or get_gateway()
    if scheme == HASH_SCHEME or not gw.can_call(api_key):
        return [hash_embedding(t) for t in texts], HASH_SCHEME
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out += await gw.embed(texts[i : i + BATCH], org_id=org_id, api_key=api_key, purpose=purpose)
    return out, gw.embed_model


async def embed_for_index(
    texts: Sequence[str], *, org_id: str | None, api_key: str | None = None, gateway: LlmGateway | None = None
) -> tuple[list[list[float]], str]:
    """Index-time embedding: live when possible, otherwise (fixture mode / budget) hash scheme."""
    try:
        return await embed_texts(texts, org_id=org_id, api_key=api_key, purpose="kb_index", gateway=gateway)
    except (BudgetExceeded, LlmUnavailable):
        return [hash_embedding(t) for t in texts], HASH_SCHEME


def vector_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
