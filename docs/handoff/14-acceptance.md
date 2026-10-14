# 14 — Acceptance checklist

Check every item on **production** unless marked. Record evidence (URL, screenshot path, CI run link) next to each in `docs/ops/BUILD_LOG.md`.

## Phase 0 — Foundations
- [ ] Repo created, branch protection on `main`, secret scanning + push protection on.
- [ ] AWS Budget ($50) and Anthropic spend limit ($30) set **before** other resources.
- [ ] CI green on the scaffold.
- [ ] `INVENTORY.md` lists every resource; no secrets anywhere in the repo (`gitleaks detect` clean on full history).

## Phase 1 — Database
- [ ] All migrations apply from zero; types generated and committed.
- [ ] pgTAP suite green: RLS on every table, cross-org isolation, audit immutability, KPI views on fixtures.
- [ ] Demo org skeleton seeded (34 locations, 3 entities, vendors, contracts incl. clause 4.2 shrimp $3.68, POs, GRNs, 6 months history).

## Phase 2 — Design system & shell
- [ ] `modernist.css` vendored verbatim; no color/radius/font outside tokens (lint rule or grep check in CI).
- [ ] Rail, top bar, status bar match `02` §5 at 1600px (pixel check vs design PNG in fixture mode).
- [ ] Demo badge appears once per screen, top bar only, only for demo orgs.
- [ ] Red appears only in risk contexts (manual review of every screen).

## Phase 3 — Core
- [ ] All unit tests in `12` §1 exist and pass; coverage ≥ 85%.
- [ ] Hero case math exact: 736.00 / 824.00 / 88.00 / 14.72 / +12.0% / 2,759.60 / 0.94.
- [ ] QBO sandbox bill created with GL, Class=location, expected prices, hold memo.

## Phase 4 — n8n
- [ ] All workflows in repo JSON, imported by CI, active; `WORKFLOW_VERSION` shown in rail and status bar.
- [ ] Human-in-the-loop resumes work for every decision type; resume retry job covers n8n downtime.
- [ ] Error workflow creates dead letters and Slack alerts; DLQ count visible in status bar.
- [ ] Slack digest posts at 09:30 org-local.

## Phase 5 — Intake
- [ ] Email to the demo inbox → run visible ≤ 60s.
- [ ] `/capture` works on iOS Safari and Android Chrome; offline queue retries.
- [ ] Portal sync logs into the mock portal and ingests new PDFs hourly.
- [ ] EDI 810 dropped to S3 → invoice with source `edi`, gate passes.
- [ ] Re-delivered file → no duplicate run.

## Phase 6 — Screens
- [ ] Pipeline, Extraction, Match, Exceptions, Operations populated by live data; realtime updates without reload.
- [ ] Visual regression (fixture mode) within threshold for all 5 screens.
- [ ] Derived screens (login, invoices, vendors, settings, capture, mock portal) built per `03` §7.
- [ ] Loading, empty, error, degraded states implemented for every screen.
- [ ] axe: 0 serious/critical; keyboard shortcuts work; text contrast ≥ 4.5:1.
- [ ] No text overflow or unintended wrapping at 1280 / 1440 / 1600.

## Phase 7 — Data, eval, replay
- [ ] Corpus generator produces all four channels with labels; hero cases deterministic.
- [ ] Eval run recorded for the current week; Extraction and Operations show that value.
- [ ] Replay drips documents all day through real channels within caps; hero cases appear at their times.
- [ ] Operations disclosure reads "Computed …" for the demo org; benchmark labeled as external.

## Phase 8 — Launch
- [ ] Security checks in `11` §5 done; findings fixed.
- [ ] Load test passed; resilience drills done.
- [ ] Uptime monitor live; Sentry receiving events; CloudWatch alarms route to the user.
- [ ] Runbooks written.
- [ ] Public demo: `https://app.<domain>/login` → "Open the demo" → all screens live; audit chain verifies from the UI.
- [ ] Monthly reset tested on staging (or on a copy).
- [ ] The user has walked through the demo and signed off.
