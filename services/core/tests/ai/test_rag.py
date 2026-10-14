from __future__ import annotations

from datetime import date

import pytest

from app.ai.rag.chunker import chunk_markdown, clause_ref_of, parse_front_matter
from app.ai.rag.embed import HASH_SCHEME, cosine, embed_texts, hash_embedding
from app.ai.rag.index import fill_placeholders
from app.ai.rag.retrieve import Chunk, or_query

from .conftest import REPO, needs_db

DOC = """---
kind: contract
title: Test agreement
vendor: Protein Supplier
---

# Test agreement

Intro paragraph.

## 4. Pricing

General pricing terms.

### 4.2 Pricing: Shrimp

Shrimp 16/20 IQF is priced at $3.68 per lb.

## Section 7.1 — Term

Runs through {{EFFECTIVE_TO}}.

## Schedule A — Prices

| Ref | Item |
|---|---|
| A-1 | Oil |
"""


@pytest.mark.parametrize(
    ("heading", "ref"),
    [
        ("4.2 Pricing", "4.2"),
        ("4. Pricing", "4"),
        ("§ 4.2 Pricing", "4.2"),
        ("Section 7.1 — Term", "7.1"),
        ("Clause 12 Notices", "12"),
        ("Schedule A — Prices", "Sched. A"),
        ("Pricing", None),
        ("2026 outlook", "2026"),
    ],
)
def test_clause_ref_detection(heading: str, ref: str | None) -> None:
    assert clause_ref_of(heading) == ref


def test_chunker_sections_and_paths() -> None:
    chunks = chunk_markdown(DOC)
    by_ref = {c.clause_ref: c for c in chunks}
    assert by_ref["4.2"].content == "Shrimp 16/20 IQF is priced at $3.68 per lb."
    assert by_ref["4.2"].heading_path == "Test agreement > 4. Pricing > 4.2 Pricing: Shrimp"
    assert by_ref["4"].content == "General pricing terms."
    assert by_ref["7.1"].heading_path.endswith("Section 7.1 — Term")
    assert "A-1" in by_ref["Sched. A"].content
    assert chunks[0].clause_ref is None and chunks[0].content == "Intro paragraph."
    assert [c.ord for c in chunks] == list(range(len(chunks)))


def test_front_matter() -> None:
    doc = parse_front_matter(DOC)
    assert doc.meta == {"kind": "contract", "title": "Test agreement", "vendor": "Protein Supplier"}
    assert doc.body.startswith("# Test agreement")


def test_long_sections_split() -> None:
    para = "word " * 200
    chunks = chunk_markdown("## 1. Long\n\n" + "\n\n".join([para] * 4))
    assert len(chunks) > 1 and all(c.clause_ref == "1" for c in chunks)


def test_kb_protein_contract_clause_42() -> None:
    text = (REPO / "tools/corpus/kb/contracts/protein-supplier-agreement-2026.md").read_text(encoding="utf-8")
    body = fill_placeholders(
        parse_front_matter(text).body,
        {
            "effective_from": date(2026, 3, 1),
            "effective_to": date(2027, 3, 31),
            "countersigned_at": date(2026, 3, 3),
        },
    )
    assert "{{" not in body and "March 31, 2027" in body
    chunks = chunk_markdown(body, "Protein Supplier — Vendor agreement 2026")
    c42 = [c for c in chunks if c.clause_ref == "4.2"]
    assert len(c42) == 1 and "$3.68 per lb" in c42[0].content and "Shrimp 16/20 IQF" in c42[0].content


def test_all_kb_files_parse() -> None:
    files = sorted((REPO / "tools/corpus/kb").rglob("*.md"))
    assert len(files) >= 8
    for f in files:
        doc = parse_front_matter(f.read_text(encoding="utf-8"))
        assert doc.meta.get("kind") in {"contract", "policy", "vendor_note"}, f
        assert chunk_markdown(doc.body, doc.meta.get("title")), f


def test_hash_embedding_is_deterministic_and_lexical() -> None:
    a = hash_embedding("contract price for shrimp")
    assert a == hash_embedding("contract price for shrimp") and len(a) == 512
    assert abs(sum(x * x for x in a) - 1) < 1e-9
    near = cosine(a, hash_embedding("Shrimp 16/20 IQF contract price $3.68 per lb"))
    far = cosine(a, hash_embedding("bank details verified by phone with the controller"))
    assert near > far


async def test_embed_texts_offline(fixture_gateway, no_network: None) -> None:
    vecs, scheme = await embed_texts(["a b c"], org_id=None)
    assert scheme == HASH_SCHEME and vecs[0] == hash_embedding("a b c")


def test_or_query_and_snippet() -> None:
    assert or_query("What is the contract price for shrimp?") == "contract or price or shrimp"
    c = Chunk(
        "c1",
        "d1",
        "T",
        "contract",
        "T > 4.2",
        "4.2",
        "Shrimp 16/20 IQF 2lb × 10 is priced at **$3.68 per lb** for the Term. The price applies everywhere.",
    )
    assert "$3.68" in c.snippet("contract price for shrimp")


@needs_db
async def test_fts_retrieval_finds_clause_42(kb_org: str) -> None:
    from app.ai.rag.retrieve import search_kb

    hits = await search_kb(kb_org, "What is the contract price for shrimp?", k=4)
    assert hits and hits[0].clause_ref == "4.2", [(h.title, h.clause_ref) for h in hits]
    assert "$3.68" in hits[0].content
    pinned = await search_kb(kb_org, "What does clause 4.2 say?", k=3)
    assert pinned[0].clause_ref == "4.2" and pinned[0].kind == "contract"
    fraud = await search_kb(kb_org, "Who can release a fraud hold?", k=3)
    assert any("controller" in h.content.lower() and h.kind == "policy" for h in fraud)
    contracts_only = await search_kb(kb_org, "bank details", k=5, kinds=["contract"])
    assert contracts_only and all(h.kind == "contract" for h in contracts_only)
