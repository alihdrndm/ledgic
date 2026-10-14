"""Markdown → retrieval chunks, one per heading section (long sections split by paragraph).

Clause references come from numbered headings: `## 4.2 Pricing` → `4.2`, `### Section 7.1 — Term` →
`7.1`, `## Schedule A` → `Sched. A`. A chunk inherits the nearest numbered ancestor's clause ref.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_CLAUSE = re.compile(r"^(?:§\s*|section\s+|clause\s+|article\s+)?(\d+(?:\.\d+)*)\b[.)]?", re.IGNORECASE)
_SCHEDULE = re.compile(r"^schedule\s+([A-Z])\b", re.IGNORECASE)
MAX_CHARS = 1400


@dataclass(frozen=True)
class KbChunk:
    ord: int
    heading_path: str
    clause_ref: str | None
    content: str


@dataclass
class ParsedDoc:
    meta: dict[str, str] = field(default_factory=dict)
    body: str = ""


def parse_front_matter(text: str) -> ParsedDoc:
    """Minimal `---\\nkey: value\\n---` front matter (no YAML dependency)."""
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return ParsedDoc({}, text)
    end = text.find("\n---", 3)
    if end < 0:
        return ParsedDoc({}, text)
    meta: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    body = text[end + 4 :].lstrip("\n")
    return ParsedDoc(meta, body)


def clause_ref_of(heading: str) -> str | None:
    h = heading.strip().lstrip("§").strip()
    m = _CLAUSE.match(heading.strip()) or _CLAUSE.match(h)
    if m:
        return m.group(1)
    s = _SCHEDULE.match(h)
    if s:
        return f"Sched. {s.group(1).upper()}"
    return None


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts: list[str] = []
    cur = ""
    for para in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(para) + 2 > MAX_CHARS:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def chunk_markdown(text: str, title: str | None = None) -> list[KbChunk]:
    doc = parse_front_matter(text)
    title = title or doc.meta.get("title")
    stack: list[tuple[int, str, str | None]] = []  # (level, heading text, clause_ref)
    sections: list[tuple[str, str | None, list[str]]] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        names = [h for _, h, _ in stack]
        if title and names and names[0] in title:
            names[0] = title
        elif title:
            names = [title, *names]
        clause = next((c for _, _, c in reversed(stack) if c), None)
        sections.append((" > ".join(names), clause, [body]))

    in_code = False
    for line in doc.body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _HEADING.match(line)
        if m:
            flush()
            level, heading = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading, clause_ref_of(heading)))
        else:
            buf.append(line)
    flush()

    chunks: list[KbChunk] = []
    for path, clause, bodies in sections:
        for body in bodies:
            for piece in _split_long(body):
                chunks.append(KbChunk(len(chunks), path, clause, piece.strip()))
    return chunks
