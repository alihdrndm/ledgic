"""Retrieval-augmented generation over contracts, AP policy and vendor notes (DECISIONS D10)."""

from .chunker import KbChunk, chunk_markdown, clause_ref_of
from .index import IndexStats, index_kb
from .retrieve import Chunk, search_kb

__all__ = ["Chunk", "IndexStats", "KbChunk", "chunk_markdown", "clause_ref_of", "index_kb", "search_kb"]
