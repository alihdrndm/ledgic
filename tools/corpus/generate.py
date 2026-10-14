"""Render a day of the synthetic corpus to disk.

    uv run --project services/core python tools/corpus/generate.py
        --day 2026-10-14 --n 20 --out tools/corpus/out    (one command line)

Writes one file per document (PDF or JPEG) plus ``labels.jsonl`` (one JSON object per document,
keyed by the document's sha256) for the eval harness. Thin wrapper over ``app.demo.corpus``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "core"))

from app.demo.corpus import SEED, build_catalog, plan_day  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", type=date.fromisoformat, default=date.today(), help="demo day (YYYY-MM-DD)")
    ap.add_argument("--n", type=int, default=180, help="documents for the day, heroes included (cap 400)")
    ap.add_argument("--out", type=Path, default=ROOT / "tools" / "corpus" / "out")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--heroes-only", action="store_true", help="only the 5 hero cases (6 documents)")
    ap.add_argument("--no-heroes", action="store_true")
    args = ap.parse_args(argv)

    catalog = build_catalog(args.day, seed=args.seed)
    docs = plan_day(catalog, args.day, n=args.n, seed=args.seed, include_heroes=not args.no_heroes)
    if args.heroes_only:
        docs = [d for d in docs if d.hero]
    args.out.mkdir(parents=True, exist_ok=True)
    labels = args.out / "labels.jsonl"
    with labels.open("w", encoding="utf-8") as fh:
        for d in docs:
            r = d.render()
            name = r.filename if d.hero else f"{d.key.replace(':', '_')}_{r.filename}"
            (args.out / name).write_bytes(r.content)
            row = d.label(r.sha256)
            row.update(
                {
                    "file": name,
                    "mime": r.mime,
                    "pages": r.pages,
                    "bboxes": r.bboxes,
                    "skew_deg": r.skew_deg,
                    "bytes": len(r.content),
                }
            )
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(
                f"{d.release_at:%H:%M:%S} {d.channel:6} {d.condition:14} {name} ({len(r.content) // 1024} KB)"
            )
    print(f"{len(docs)} documents -> {args.out} (labels: {labels.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
