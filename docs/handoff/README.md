# Handoff: Ledgic — AI Accounts-Payable Automation (full build)

> **To Claude Code:** this folder is your complete brief. Read this file end to end first, then the numbered docs in order. You own the entire implementation: design system, frontend, backend services, database, AI pipeline, n8n orchestration, integrations, infrastructure, CI/CD, and the live demo. You have access to the user's browser and cursor — use it for console work (Vercel, Supabase, AWS, GitHub, Intuit, Slack, Anthropic) following `10-browser-runbook.md`, including every STOP point in it.

---

## 1. Overview

Ledgic is accounts-payable automation for multi-location operators (restaurant groups, hospitality, franchise operators). Invoices arrive from four channels — supplier email PDFs, phone photos of paper invoices taken at the receiving dock, vendor portal downloads, and EDI 810 feeds. An LLM extraction layer turns each document into structured header fields and line items, every field carrying a calibrated confidence score. A matching engine performs line-level three-way matching (invoice × purchase order × goods receipt) against contract prices. Clean invoices post to the ERP (QuickBooks Online / NetSuite) with entity, location and GL coding and **no human touch**. Everything else — low-confidence extractions, price variances, quantity mismatches, missing POs, suspected duplicates, new-vendor/bank-change fraud signals — routes to human approval lanes with evidence attached, and every decision is written to an append-only, hash-chained audit log.

The pipeline is orchestrated by **n8n**; the deterministic logic and AI calls live in a **Python core service**; the operator UI is a **Next.js** app on **Vercel**; data, auth, storage and realtime are **Supabase**; inbound email, OCR cross-check, container hosting and secrets are **AWS**.

### 1.1 Why this is being built for real (read this — it shapes decisions)

Ledgic began as a set of portfolio design mocks. A reviewer correctly pointed out that mock screens with metrics written as measurements ("96.4% accuracy", "$3.10 per invoice") are unverifiable and read as invented. **The fix is to make them true**: ship a live, deployed, working system running on a clearly labeled synthetic demo tenant, where every number on every screen is *computed* from real pipeline runs over a real (synthetic) document corpus, and can be inspected.

Non-negotiable honesty rules that follow from this:

1. **No hard-coded metrics anywhere in the product.** Every KPI is a SQL view over real rows. (The only exception is the visual-regression fixture mode in `12-testing-qa.md`, which is test-only and never deployed.)
2. **Demo data is labeled once, in the app chrome.** Orgs with `is_demo = true` show a `Demo · sample data` badge in the top bar. Nowhere else. Never in footers, never repeated.
3. **External benchmarks are cited as external.** The "$12–30 per invoice manual processing" figure is an industry benchmark; the UI labels it as such and never implies Ledgic measured it.
4. **Assumptions are visible.** Cost-per-invoice uses a loaded human hourly rate that is a configurable assumption; the Operations screen shows the assumption on hover/in the metric's detail.
5. **Claims we can't measure, we don't make.** Uptime is shown only if an uptime monitor is actually recording it.

## 2. About the Design Files

The files in `design/` are **design references created in HTML** — high-fidelity prototypes showing the intended look, layout and content. They are **not production code to copy**. Your task is to **recreate these designs in a real Next.js + React codebase** using the component architecture described in `02-design-system.md`.

- `design/screens/*.png` — the primary visual reference, rendered at 2× (3200×2000 per screen; the 4:3 thumbnail is 3200×2400). **Treat these as the pixel target.**
- `design/Ledgic v2.dc.html` — the source of those renders. It is a "Design Component" file that depends on a runtime not included here, so it will not open standalone; read it as text for exact values (every style is inline — sizes, paddings, colors, copy). When a PNG and the HTML disagree, the HTML wins (it is the source).
- `design/modernist-styles.css` — the design-system token sheet and component classes. **Vendor this file into the codebase verbatim** (see `02-design-system.md`).
- `design/ledgic-wordmark.svg` — the wordmark.

## 3. Fidelity

**High-fidelity.** Colors, typography, spacing, rules, layout, and copy are final for the five designed screens. Recreate them pixel-accurately at a 1600×1000 viewport (the design canvas; the rail is 64px, the top bar 56px, the status bar 34px). Screens that the product needs but that were **not** designed (login, invoice detail, vendors, settings, capture, empty/loading/error states) must be derived strictly from the same system — `03-screens.md` specifies each one.

## 4. Document map

| # | File | What it defines |
|---|---|---|
| — | `README.md` | This file: mission, operating rules, execution plan, definition of done |
| 01 | `01-product.md` | Users, roles, glossary, business rules, KPI definitions |
| 02 | `02-design-system.md` | Tokens, type, components, states, app shell, icon map |
| 03 | `03-screens.md` | Every screen — designed and derived — element by element |
| 04 | `04-architecture.md` | System topology, data flow, sequence diagrams, idempotency |
| 05 | `05-database.md` | Full Postgres schema (SQL), RLS, triggers, KPI views |
| 06 | `06-pipeline-and-ai.md` | n8n workflows, core service modules, extraction, matching, dedupe, fraud, GL, eval |
| 07 | `07-api.md` | Web server actions/route handlers, core service API, webhooks, auth between services |
| 08 | `08-integrations.md` | SES inbound email, Textract, QuickBooks, NetSuite, Slack, portals, EDI |
| 09 | `09-infrastructure-devops.md` | Monorepo, environments, Vercel, Supabase, AWS Terraform, GitHub Actions |
| 10 | `10-browser-runbook.md` | Exactly what to do in each web console, with STOP points |
| 11 | `11-security.md` | Threat model, secrets, RLS, PII, audit integrity |
| 12 | `12-testing-qa.md` | Unit, integration, e2e, visual regression, extraction eval |
| 13 | `13-demo-data.md` | Synthetic tenant, corpus generator, hero cases, demo replay |
| 14 | `14-acceptance.md` | The checklist you must pass before declaring done |

## 5. Operating rules for Claude Code

### 5.1 General
- Work in a new GitHub repository named `ledgic` under the user's account (confirm the account in the browser; see runbook §2). Commit early and often with conventional commits (`feat:`, `fix:`, `chore:`, `infra:`, `docs:`).
- Keep a running log at `docs/ops/BUILD_LOG.md`: what you did, what's pending, every decision where you deviated from this spec and why.
- Keep a non-secret resource inventory at `docs/ops/INVENTORY.md`: project IDs, regions, URLs, ARNs, app IDs, webhook URLs. **Never** secrets.
- When this spec is ambiguous, choose the simplest option consistent with it, record the choice in `BUILD_LOG.md`, and continue. Do not stop for questions that don't involve money, identity, or irreversible actions.
- Prefer managed services and boring technology. Every moving part must be reproducible from the repo (IaC, migrations, workflow JSON, seed scripts).

### 5.2 Browser and cursor use
You may drive the user's browser to operate consoles. Follow `10-browser-runbook.md`. Hard rules:
- **STOP and ask the user** before: entering or confirming payment details; upgrading any plan; accepting terms of service on the user's behalf for a new account; buying a domain; any action that creates a recurring cost beyond the budget in §5.4; deleting any resource you did not create; changing DNS on an existing domain that has live traffic.
- **Hand control to the user** for: logins, passwords, 2FA/MFA codes, CAPTCHAs, SSO consent screens that ask for broad personal scopes. Wait until they confirm they're done.
- **Secrets never pass through chat, logs, commits, or files in the repo.** Copy them directly from the provider console into their destination (GitHub Actions secrets, Vercel environment variables, AWS Secrets Manager, Supabase Vault). Where a CLI is authenticated, prefer `gh secret set`, `vercel env add`, `aws secretsmanager put-secret-value` with values piped from the clipboard or entered interactively — never echoed.
- Don't leave consoles in half-configured states. If you must pause, write what's pending in `BUILD_LOG.md`.

### 5.3 Human checkpoints (pause and show the user)
Pause and ask for a quick review at the end of each phase in §6 — show the relevant URL or screenshot and the acceptance items you've met. Continue once they confirm.

### 5.4 Budget guardrails
- Target steady-state cost: **≤ $60/month** for the whole demo stack (excluding LLM usage). Set an **AWS Budget alarm at $50/month** and **Anthropic usage limit at $30/month** as the first infra actions. Use the free tiers of Vercel (Hobby is fine unless the user says otherwise), Supabase (Free or Pro — ask), Slack, Intuit sandbox.
- The demo replay job (`13-demo-data.md` §6) must be capped: default 180 documents/day, hard ceiling 400/day, configurable.

## 6. Execution plan (phases with gates)

Do the phases in order. Each phase ends with its gate in `14-acceptance.md`.

**Phase 0 — Accounts, repo, guardrails** (runbook §§1–4)
GitHub repo, local toolchain, Supabase project(s), Vercel project, AWS account access with budget alarm, Anthropic API key with spend limit. Monorepo scaffold (`09` §1), CI skeleton green on an empty project.

**Phase 1 — Database and auth** (`05`)
All migrations, RLS, audit triggers, KPI views, generated TypeScript types. Supabase Auth with magic link. Seed the demo org skeleton (org, entities, locations, vendors, contracts, POs, GRNs — no invoices yet).

**Phase 2 — Design system and app shell** (`02`, `03` §1)
Vendor the Modernist stylesheet, build the React primitives, the rail/top bar/status bar shell, routing, org switcher, demo badge, ⌘K palette stub. Storybook-free: build a `/_system` route (dev only) that renders every primitive and state.

**Phase 3 — Core service** (`06` §§3–9, `07` §3)
Python FastAPI service with extraction (Claude vision + Textract cross-check), confidence calibration, enrichment, dedupe, fraud screen, three-way match, recommendation engine, ERP posting adapters (QBO real sandbox, NetSuite mock), cost ledger. Full unit tests for matching/dedupe/fraud/tolerance math.

**Phase 4 — n8n orchestration** (`06` §2)
All workflows as version-controlled JSON; n8n deployed on AWS; human-in-the-loop via Wait/resume webhooks; error workflow + dead-letter; Slack digest and alerts.

**Phase 5 — Intake channels** (`08`)
SES inbound email (MX on a subdomain), mobile photo capture page, mock vendor portal + portal sync, EDI 810 parser with S3 drop.

**Phase 6 — Screens** (`03`)
All five designed screens wired to real data with realtime updates, then the derived screens. Visual regression against the design PNGs in fixture mode.

**Phase 7 — Synthetic corpus, eval, demo replay** (`13`, `12` §5)
Corpus generator with ground-truth labels, extraction eval harness feeding the accuracy KPI, demo replay drip so the demo is live every day.

**Phase 8 — Hardening and launch** (`11`, `12`, `14`)
Security review, load test, uptime monitor, error tracking, runbooks, the public read-only demo login, final acceptance.

## 7. Definition of done

`14-acceptance.md` passes in full, on production, and the user has walked through the live demo. Summary of the essentials:

- A visitor can open the public demo URL, sign in with the read-only demo account, and see all five screens populated by **live** data that changes during the day.
- Sending a PDF invoice to the demo inbox results in a run visible in the Pipeline screen within 60 seconds, with a full stage timeline in the run inspector.
- The hero cases in `13-demo-data.md` §4 appear and behave exactly as designed (price variance short-pay, smudged quantity confirm, duplicate merge, bank-change fraud hold).
- Every KPI on Operations traces to a SQL view; the extraction-accuracy figure traces to the eval harness output for that week.
- A decision taken in the UI resumes the n8n execution, posts to the QuickBooks sandbox, and writes a verifiable, hash-chained audit entry.
- CI is green; deploys are automated from `main`; infrastructure is reproducible from Terraform; nothing secret is in the repo.

## 8. Files in this handoff

```
design_handoff_ledgic/
  README.md
  01-product.md … 14-acceptance.md
  design/
    Ledgic v2.dc.html          source of the renders (read as text)
    modernist-styles.css       token sheet + component classes (vendor verbatim)
    ledgic-wordmark.svg
    screens/
      00-thumbnail.png         3200×2400 (4:3 portfolio card — not an app screen)
      01-pipeline.png          3200×2000
      02-extraction.png        3200×2000
      03-three-way-match.png   3200×2000
      04-exceptions.png        3200×2000
      05-operations.png        3200×2000
```
