# Synthetic corpus

Everything in the Northside demo tenant is generated from code, reproducible from seed `20260713`
(`docs/handoff/13-demo-data.md`). The generator lives inside the core package so the Railway service
can render documents at runtime: `services/core/app/demo/corpus/`. This folder holds a thin CLI.

```bash
uv run --project services/core python tools/corpus/generate.py --day 2026-10-14 --n 20 --out tools/corpus/out
uv run --project services/core python tools/corpus/generate.py --day 2026-10-14 --heroes-only
```

Output: one PDF or JPEG per document and `labels.jsonl` (one row per document, keyed by `sha256`)
with the ground truth (`06` §5.1 schema without confidences), channel, injected condition, expected
exceptions and the field bboxes. `out/` is not committed; generate it in CI.

## Modules (`app/demo/corpus`)

| Module | What it does |
|---|---|
| `catalog.py` | `build_catalog(today)`: org, 3 entities, 34 locations, GL accounts, 10 vendors (tax ids, bank and W-9 fingerprints; the Unlisted Supplier's bank differs from its W-9), ~185 items, contracts (Protein clause 4.2 shrimp $3.68/lb with a rolling end date, DECISIONS D8), delivery schedules. Single source of truth for the DB seed. |
| `heroes.py` | The 5 hero cases, numbers exactly as in `contracts/fixtures.json`. |
| `invoices.py` | `plan_day(catalog, day, n=180)`: POs, GRNs and invoice documents with injected conditions, channel mix, release times and `simulated_extraction` (values, confidences, bboxes). |
| `layout.py` | Four supplier templates (A modern, B classic grid, C table-less ticket, D portal/EDI) as pure layouts; the same layout feeds the renderer and the bboxes. |
| `render.py` | reportlab PDF (deterministic `invariant` mode, built-in fonts, < 10 KB). |
| `photo.py` | Dock photo: pypdfium2 raster, smudge on the chosen digit, signature, fold/coffee ring, perspective (±8°) + rotation (±4°), lighting gradient, blur, JPEG. `phash_hex()` helper. |
| `../planner.py` | Replay: `due_docs`, `simulated_decision`, `backfill_days`, `historical_coded_lines`, `prior_short_pays`. |

## Rates (per base invoice)

Price variance ~11% (contract drift on one line), short delivery ~4% (GRN short), no PO ~4%
(mostly ad-hoc equipment buys), fraud screen ~0.5% (bank details ≠ W-9, new remit address, no PO),
~1% second copies via another channel, ~14% of dock photos carry one smudged field (~2.5% of all).
Channel mix: email 59% · photo 18% · portal 14% · EDI 10% (EDI is rendered as a clean portal-style
PDF, `channel='edi'`, extraction confidence 1.0). Rates are not tuned to the mock's numbers.

## Heroes (every demo day, fixed times America/New_York)

| Case | Time | Channel |
|---|---|---|
| PR-2201 | 08:02 / 16:44 | email PDF, then dock photo (duplicate, invoice dated the previous day) |
| NV-0001 | 09:00 | email (Unlisted Supplier → Commissary, bank ≠ W-9, no PO) |
| PR-2214 | 09:12:44 | dock photo, skew +2.0°, line 2 qty smudged (conf 0.71, doc 0.88) |
| PS-88214 | 09:41 | email (shrimp $4.12 vs contract $3.68) |
| BD-104882 | 09:41:07 | email, 14 lines, 2 pages, touchless |
