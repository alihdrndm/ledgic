# 12 — Testing & QA

## 1. Unit (core, pytest + hypothesis) — must exist and pass
- `tolerance`: the hero case (736.00 vs 824.00 → fail, pct 11.96 → "+12.0%"); boundary cases at exactly 2% and exactly $25; min() selection; favorable deltas; rounding to cents with Decimal; property test: passing iff |delta| ≤ min(pct×exp, abs).
- `qty`: over-receipt, over-order, two-way vendors skip GRN.
- `gate`: weighted geometric mean; field floor; arithmetic checks; smudged-qty example → review.
- `duplicates`: hard duplicate; PR-2201 pair → ≥ 0.90 with the exact evidence JSON; near-miss (different amount) < 0.75.
- `fraud`: NV-0001 signals → 0.90 hold; established vendor with bank match → 0.
- `pairing`: Hungarian assignment picks correct PO lines with shuffled order and noisy descriptions.
- `recommend`: hero case → short_pay, 2759.60/88.00, confidence 0.94, the four bullet strings verbatim.
- `x12_810`: parse samples; malformed → error.
- `audit`: chain verify detects a modified row (test uses a superuser connection to simulate tampering).
Coverage gate 85% on `app/`.

## 2. Database (pgTAP via `supabase test db`)
- RLS enabled on every table (query `pg_tables` × `relrowsecurity`).
- Member of org A cannot select org B rows on each table.
- `authenticated` cannot insert/update pipeline tables directly.
- `audit_log` update/delete raise; `audit_verify` returns null on a clean chain.
- KPI views return expected numbers for a fixture dataset (a SQL fixture with known counts).

## 3. Integration (docker-compose.ci)
Pipeline tests drive real n8n + core + local Supabase with `CORE_LLM_MODE=fixture` (recorded tool-use outputs per corpus document) and `CORE_OCR_MODE=fixture`:
1. Touchless PDF → run succeeded, `touchless=true`, QBO **mock** posting (CI never hits real QBO), events in order.
2. Smudged photo → extraction_review exception → call resume via web action → completes.
3. Hero price variance → exception with recommendation → decide short_pay → posting request lines at $3.68.
4. Duplicate pair → second held → merge → second never posts.
5. Fraud vendor → held → release only by controller; SoD violation rejected.
6. ERP failure injection → retries → posting_failed exception → retry succeeds.
7. Re-delivery of same file → no second run.

## 4. End-to-end UI (Playwright)
- Auth flows (magic link via Supabase Inbucket locally), demo login, role gating tooltips.
- Each designed screen renders with live seeded data; keyboard shortcuts; ⌘K palette.
- Decision flows from the UI for each exception type.
- Accessibility: `@axe-core/playwright` on every screen — zero serious/critical violations.

### 4.1 Visual regression against the design
- Fixture mode: `LEDGIC_FIXTURE=design` (test-only env, rejected in production builds by a build-time check) seeds a dedicated org whose data reproduces the design's exact values (214/209/198/152/41, PS-88214, PR-2214, PR-2201, NV-0001, the Operations figures, clock frozen at 2026-07-13 09:41:23 America/New_York). This is the **only** place design numbers are hard-coded, and it lives in `e2e/fixtures/design-snapshot.sql`.
- Viewport 1600×1000, deviceScaleFactor 2; compare each screen to `design/screens/0N-*.png` with `toHaveScreenshot` threshold `maxDiffPixelRatio: 0.02`. Known intentional deltas (copy updated for the real system — listed in `03`) are masked by selector.
- Fonts must be loaded before capture (`document.fonts.ready`).

## 5. Extraction eval (see `06` §10)
- `pnpm eval` runs locally on the corpus; CI nightly on a fixed subset; weekly production run writes `eval_runs`.
- Report: overall accuracy, by field, by channel (photo is expected to be lowest), calibration curve (reliability diagram PNG), and the gate's precision/recall (what fraction of wrong fields were caught by the gate — target ≥ 90% recall of errors).

## 6. Load & resilience
- k6 or Locust: 500 documents over 10 minutes through intake with fixture LLM → no DLQ, p95 stage latency recorded.
- Kill the core task mid-run → n8n retries → run completes.
- Revoke QBO token → `needs_reconnect` state and Slack alert.

## 7. Manual QA checklist before launch
- Send a real PDF to the demo inbox from a personal email → appears in Pipeline ≤ 60s.
- Photograph a printed invoice with a phone on `/capture` → appears, skew shown on Extraction.
- Walk every screen at 1280, 1440, 1600 widths; check no text overflow, no wrapping in chips/top bar, tabular numerals aligned.
- Verify audit chain from the UI.
