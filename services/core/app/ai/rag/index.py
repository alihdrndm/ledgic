"""Index knowledge-base markdown into `kb_documents` / `kb_chunks` for one org.

Front matter keys: `kind` (contract | policy | vendor_note), `title`, `vendor` (vendors.display_name),
`contract` (contracts.title). Contract placeholders `{{EFFECTIVE_FROM}}`, `{{EFFECTIVE_TO}}`,
`{{COUNTERSIGNED_AT}}` are filled from the `contracts` row (the demo's rolling end date, DECISIONS D8).
Re-indexing a path replaces its document (delete + insert, chunks cascade), so it is idempotent.
"""

from __future__ import annotations

import calendar
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..gateway import LlmGateway
from ..paths import kb_dir
from .chunker import chunk_markdown, parse_front_matter
from .embed import embed_for_index, vector_literal

log = logging.getLogger("ledgic.ai.rag")

KINDS = {"contract", "policy", "vendor_note"}
_DIR_KIND = {"contracts": "contract", "policies": "policy", "vendor-notes": "vendor_note"}


@dataclass
class IndexStats:
    documents: int = 0
    chunks: int = 0
    scheme: str | None = None
    unresolved: list[str] = field(default_factory=list)


def fmt_long_date(d: date) -> str:
    return f"{calendar.month_name[d.month]} {d.day}, {d.year}"


def _rolling_end(today: date) -> date:
    """Fallback when no contracts row exists: last day of the 5th month after today (D8)."""
    m = today.month - 1 + 5
    y, m = today.year + m // 12, m % 12 + 1
    return date(y, m, calendar.monthrange(y, m)[1])


def fill_placeholders(body: str, contract: dict[str, Any] | None, today: date | None = None) -> str:
    today = today or date.today()
    eff_from = contract["effective_from"] if contract else date(today.year, 3, 1)
    eff_to = contract["effective_to"] if contract else _rolling_end(today)
    signed = (contract or {}).get("countersigned_at") or eff_from
    return (
        body.replace("{{EFFECTIVE_FROM}}", fmt_long_date(eff_from))
        .replace("{{EFFECTIVE_TO}}", fmt_long_date(eff_to))
        .replace("{{COUNTERSIGNED_AT}}", fmt_long_date(signed))
    )


def default_paths() -> list[Path]:
    root = kb_dir()
    return sorted(p for p in root.rglob("*.md") if p.name.lower() != "readme.md")


async def index_kb(
    org_id: str,
    paths: Iterable[str | Path] | None = None,
    *,
    api_key: str | None = None,
    gateway: LlmGateway | None = None,
) -> IndexStats:
    """Upsert the given markdown files (default: all of tools/corpus/kb) for `org_id`."""
    from app.db.pool import connection

    root = kb_dir()
    files = [Path(p) for p in paths] if paths is not None else default_paths()
    stats = IndexStats()
    async with connection() as conn:
        for path in files:
            full = path if path.is_absolute() else root / path
            try:
                rel = full.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                rel = full.name
            doc = parse_front_matter(full.read_text(encoding="utf-8"))
            kind = doc.meta.get("kind") or _DIR_KIND.get(Path(rel).parts[0], "policy")
            if kind not in KINDS:
                raise ValueError(f"{rel}: unknown kind {kind!r}")
            title = doc.meta.get("title") or full.stem.replace("-", " ").title()

            vendor_id = contract = None
            if doc.meta.get("vendor"):
                cur = await conn.execute(
                    "select id from public.vendors where org_id = %s and display_name = %s limit 1",
                    (org_id, doc.meta["vendor"]),
                )
                row = await cur.fetchone()
                vendor_id = row["id"] if row else None
                if vendor_id is None:
                    stats.unresolved.append(f"{rel}: vendor {doc.meta['vendor']!r}")
            if kind == "contract" and vendor_id is not None:
                cur = await conn.execute(
                    "select id, effective_from, effective_to, countersigned_at from public.contracts"
                    " where org_id = %s and vendor_id = %s and (%s::text is null or title = %s)"
                    " order by effective_to desc limit 1",
                    (org_id, vendor_id, doc.meta.get("contract"), doc.meta.get("contract")),
                )
                contract = await cur.fetchone()
                if contract is None:
                    stats.unresolved.append(f"{rel}: contract {doc.meta.get('contract')!r}")

            body = fill_placeholders(doc.body, contract)
            chunks = chunk_markdown(body, title)
            vectors, scheme = await embed_for_index(
                [f"{c.heading_path}\n{c.content}" for c in chunks],
                org_id=org_id,
                api_key=api_key,
                gateway=gateway,
            )
            stats.scheme = scheme

            await conn.execute(
                "delete from public.kb_documents where org_id = %s and source_path = %s", (org_id, rel)
            )
            cur = await conn.execute(
                "insert into public.kb_documents (org_id, kind, title, contract_id, vendor_id, source_path)"
                " values (%s, %s, %s, %s, %s, %s) returning id",
                (org_id, kind, title, contract["id"] if contract else None, vendor_id, rel),
            )
            doc_row = await cur.fetchone()
            assert doc_row is not None
            async with conn.cursor() as c2:
                await c2.executemany(
                    "insert into public.kb_chunks (document_id, org_id, ord, heading_path, clause_ref,"
                    " content, embedding) values (%s, %s, %s, %s, %s, %s, %s::extensions.vector)",
                    [
                        (
                            doc_row["id"],
                            org_id,
                            ch.ord,
                            ch.heading_path,
                            ch.clause_ref,
                            ch.content,
                            vector_literal(vec),
                        )
                        for ch, vec in zip(chunks, vectors, strict=True)
                    ],
                )
            stats.documents += 1
            stats.chunks += len(chunks)
        await conn.commit()
    for u in stats.unresolved:
        log.warning("kb index: unresolved %s", u)
    from .retrieve import forget_scheme

    forget_scheme(org_id)
    return stats
