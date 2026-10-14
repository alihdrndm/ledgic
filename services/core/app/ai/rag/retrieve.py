"""Hybrid retrieval over the org's knowledge base.

Primary path: `kb_search(org, embedding, text, k, kinds)` RPC — pgvector + full-text, reciprocal-rank
fusion (contracts/rpc.md). Fallback (no embedding: budget spent, RPC missing) is FTS-only SQL.
The query text is OR-ed (`shrimp or price or contract`) so `websearch_to_tsquery` ranks partial
matches instead of requiring every word. A question naming a clause (`clause 4.2`, `§4.2`) pins the
chunks with that `clause_ref` first.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from ..gateway import BudgetExceeded, LlmGateway, LlmUnavailable
from .embed import HASH_SCHEME, cosine, embed_texts, hash_embedding, tokens, vector_literal

log = logging.getLogger("ledgic.ai.rag")

_CLAUSE_Q = re.compile(r"(?:§\s*|\bclause\s+|\bsection\s+)(\d+(?:\.\d+)+|\d+)", re.IGNORECASE)
_scheme_cache: dict[str, str] = {}


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    kind: str
    heading_path: str | None
    clause_ref: str | None
    content: str
    score: float = 0.0
    contract_id: str | None = None
    vendor_id: str | None = None

    def snippet(self, query: str | None = None, max_chars: int = 280) -> str:
        """Most query-relevant sentence(s)/table row of the chunk, trimmed to `max_chars`."""
        units: list[str] = []
        for para in re.split(r"\n\s*\n", self.content):
            rows = [r.strip() for r in para.splitlines() if r.strip()]
            if rows and all(r.startswith("|") for r in rows):
                units += rows  # table: one row per unit
            else:
                units += re.split(r"(?<=[.!?])\s+", " ".join(rows))
        units = [u for u in units if u and not re.fullmatch(r"[|\-:\s]+", u)]
        if not units:
            return ""
        if query:
            q = set(tokens(query))
            best = max(units, key=lambda u: (len(q & set(tokens(u))), -units.index(u)))
            text = best if q & set(tokens(best)) else units[0]
        else:
            text = units[0]
        text = re.sub(r"\s*\|\s*", " | ", text).strip(" |")
        return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def or_query(text: str) -> str:
    terms = list(dict.fromkeys(tokens(text)))
    return " or ".join(terms) if terms else text


def forget_scheme(org_id: str) -> None:
    _scheme_cache.pop(org_id, None)


async def _index_scheme(conn: Any, org_id: str) -> str | None:
    """'hash-bow-512' if the org's chunks were embedded offline, else 'openai' (None: empty index)."""
    if org_id in _scheme_cache:
        return _scheme_cache[org_id]
    cur = await conn.execute(
        "select heading_path, content, embedding::text as emb from public.kb_chunks"
        " where org_id = %s and embedding is not null order by ord limit 1",
        (org_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    stored = [float(x) for x in row["emb"].strip("[]").split(",")]
    probe = hash_embedding(f"{row['heading_path']}\n{row['content']}")
    scheme = HASH_SCHEME if cosine(stored, probe) > 0.999 else "openai"
    _scheme_cache[org_id] = scheme
    return scheme


def _chunk(row: dict[str, Any], score: float | None = None) -> Chunk:
    return Chunk(
        chunk_id=str(row["chunk_id"]),
        document_id=str(row["document_id"]),
        title=row["title"],
        kind=row["kind"],
        heading_path=row.get("heading_path"),
        clause_ref=row.get("clause_ref"),
        content=row["content"],
        score=float(score if score is not None else row.get("rrf_score") or row.get("rank") or 0.0),
        contract_id=str(row["contract_id"]) if row.get("contract_id") else None,
        vendor_id=str(row["vendor_id"]) if row.get("vendor_id") else None,
    )


_FTS_SQL = """
select c.id as chunk_id, c.document_id, d.title, d.kind, d.contract_id, d.vendor_id,
       c.heading_path, c.clause_ref, c.content,
       ts_rank_cd(c.tsv, websearch_to_tsquery('english', %(q)s)) as rank
from public.kb_chunks c
join public.kb_documents d on d.id = c.document_id
where c.org_id = %(org)s
  and c.tsv @@ websearch_to_tsquery('english', %(q)s)
  and (%(kinds)s::text[] is null or d.kind = any(%(kinds)s::text[]))
order by rank desc, c.ord
limit %(k)s
"""

_CLAUSE_SQL = """
select c.id as chunk_id, c.document_id, d.title, d.kind, d.contract_id, d.vendor_id,
       c.heading_path, c.clause_ref, c.content, 1.0 as rank
from public.kb_chunks c
join public.kb_documents d on d.id = c.document_id
where c.org_id = %(org)s and c.clause_ref = %(clause)s
  and (%(kinds)s::text[] is null or d.kind = any(%(kinds)s::text[]))
order by d.kind = 'contract' desc, c.ord
limit 3
"""


async def search_kb(
    org_id: str,
    query: str,
    k: int = 6,
    *,
    kinds: list[str] | None = None,
    api_key: str | None = None,
    gateway: LlmGateway | None = None,
) -> list[Chunk]:
    """Top-k chunks for `query` in `org_id`'s knowledge base (RRF hybrid, FTS-only fallback)."""
    from psycopg import errors

    from app.db.pool import connection

    q_text = or_query(query)
    pool = max(4 * k, 20)  # candidate pool for the lexical rerank
    results: list[Chunk] = []
    async with connection() as conn:
        clause = _CLAUSE_Q.search(query)
        if clause:
            cur = await conn.execute(_CLAUSE_SQL, {"org": org_id, "clause": clause.group(1), "kinds": kinds})
            results += [_chunk(r, 1.0) for r in await cur.fetchall()]

        embedding: list[float] | None = None
        scheme = await _index_scheme(conn, org_id)
        if scheme is not None:
            try:
                vecs, _ = await embed_texts(
                    [query],
                    org_id=org_id,
                    api_key=api_key,
                    purpose="kb_query",
                    scheme=HASH_SCHEME if scheme == HASH_SCHEME else None,
                    gateway=gateway,
                )
                embedding = vecs[0]
            except (BudgetExceeded, LlmUnavailable) as exc:
                log.info("kb query embedding unavailable (%s); FTS only", type(exc).__name__)

        rows: list[dict[str, Any]] = []
        if embedding is not None:
            try:
                cur = await conn.execute(
                    "select * from public.kb_search(%s::uuid, %s::extensions.vector, %s, %s, %s::text[])",
                    (org_id, vector_literal(embedding), q_text, pool, kinds),
                )
                rows = list(await cur.fetchall())
            except (errors.UndefinedFunction, errors.UndefinedObject) as exc:
                await conn.rollback()
                log.info("kb_search RPC unavailable (%s); FTS only", type(exc).__name__)
                embedding = None
        if embedding is None:
            cur = await conn.execute(_FTS_SQL, {"org": org_id, "q": q_text, "k": pool, "kinds": kinds})
            rows = list(await cur.fetchall())
        await conn.rollback()  # read-only

    seen = {c.chunk_id for c in results}
    for ch in rerank(query, [_chunk(r) for r in rows]):
        if ch.chunk_id not in seen:
            seen.add(ch.chunk_id)
            results.append(ch)
    return results[:k]


def _stem(t: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break
    return t[:-1] if t.endswith("e") and len(t) > 4 else t


_KIND_HINTS = {
    "contract": ("contract", "agreement", "clause", "schedule"),
    "policy": ("policy", "policies", "allowed", "approve", "approval", "limit", "who"),
    "vendor_note": ("vendor note", "history", "usually", "recurring"),
}


def _kind_hint(query: str) -> set[str]:
    ql = query.lower()
    return {kind for kind, words in _KIND_HINTS.items() if any(w in ql for w in words)}


def rerank(query: str, cands: list[Chunk], *, k1: float = 1.2, b: float = 0.75) -> list[Chunk]:
    """Re-order the hybrid candidate pool: BM25 over the pool (section heading counted twice; rewards
    short, precise passages such as a single contract clause) fused by reciprocal rank with the pool
    order (vector + full-text RRF from kb_search). A small bonus goes to the document kind the question
    names ("contract", "policy", ...)."""
    if len(cands) < 2:
        return cands
    q = {_stem(t) for t in tokens(query)}
    hints = _kind_hint(query)
    docs = []
    for c in cands:
        section = (c.heading_path or "").split(" > ")[-1]
        docs.append([_stem(t) for t in tokens(f"{c.heading_path or ''} {section} {c.content}")])
    n = len(docs)
    avg = sum(len(d) for d in docs) / n or 1.0
    df = {t: sum(1 for d in docs if t in d) for t in q}
    scores = []
    for d in docs:
        s = 0.0
        for t in q:
            tf = d.count(t)
            if tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg))
        scores.append(s)
    bm_rank = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: -scores[i]), start=1)}

    def fused(i: int) -> float:
        score = 1 / (20 + i + 1)  # pool order (hybrid RRF) — weaker than the BM25 rank
        if scores[i]:
            score += 1 / (10 + bm_rank[i])
        if cands[i].kind in hints:
            score += 0.02
        return score

    return [cands[i] for i in sorted(range(n), key=lambda i: -fused(i))]
