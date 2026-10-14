# 04 — Architecture

## 1. Topology

```
                    ┌──────────────────────────── Internet ─────────────────────────────┐
 Suppliers ─email──▶ AWS SES (inbound, ap.<domain>) ─▶ S3 raw-mail ─▶ SNS ─┐
 Dock staff ─photo─▶ Vercel /capture ─▶ Supabase Storage ───────────────────┤
 Vendor portals ◀─sync── core-service (Playwright/httpx) ◀── n8n cron ──────┤
 EDI 810 ─SFTP/S3──▶ S3 edi-inbound ─▶ SNS ─────────────────────────────────┤
                                                                            ▼
                                    ┌────────────── AWS (us-east-1) ───────────────┐
                                    │  ALB (HTTPS, ACM)                            │
                                    │   ├─ n8n.<domain>   → ECS Fargate: n8n       │
                                    │   └─ core.<domain>  → ECS Fargate: core-svc  │
                                    │  Secrets Manager · CloudWatch · ECR          │
                                    │  Textract (AnalyzeExpense)                   │
                                    └───────────────┬──────────────────────────────┘
                                                    │ Postgres (pooled), Storage, Realtime
                                    ┌───────────────▼──────────────┐
                                    │ Supabase                     │
                                    │  Postgres 15 + pgvector,     │
                                    │  pg_trgm, pgcrypto, pg_cron  │
                                    │  Auth · Storage · Realtime   │
                                    │  Vault (integration tokens)  │
                                    └───────────────▲──────────────┘
                                                    │
 Operators ──browser──▶ Vercel: Next.js app (RSC + server actions) ──┘
                                     │  decisions → n8n resume webhooks
 Anthropic API ◀── core-service (extraction)
 QuickBooks Online / NetSuite ◀── core-service (posting adapters)
 Slack ◀── n8n (digest, alerts)
```

### Components
| Component | Tech | Hosted | Responsibility |
|---|---|---|---|
| `apps/web` | Next.js 15 (App Router), React 19, TypeScript strict | Vercel | UI, auth session, server actions for human decisions, capture PWA, mock vendor portal, read APIs via Supabase with RLS |
| `services/core` | Python 3.12, FastAPI, pydantic v2, psycopg 3, uv | AWS ECS Fargate | All deterministic logic + AI: ingest, preprocessing, extraction, calibration, enrichment, screening, match, recommendation, posting adapters, cost ledger, eval |
| `services/n8n` | n8n (pinned version), workflow JSON in repo | AWS ECS Fargate | Orchestration: intake triggers, stage sequencing, retries, human-in-the-loop waits, schedules, notifications, error workflow |
| Database | Supabase Postgres | Supabase | System of record; RLS for web; service role for core/n8n |
| Object storage | Supabase Storage (`documents` private bucket) | Supabase | Source documents, rendered page images, thumbnails |
| Raw inbound | S3 buckets `ledgic-<env>-raw-mail`, `ledgic-<env>-edi-inbound` | AWS | SES-delivered MIME, EDI drops |
| OCR cross-check | AWS Textract AnalyzeExpense | AWS | Independent read of totals/line items to calibrate LLM confidence |
| LLM | Anthropic Claude (vision) | Anthropic | Structured extraction via tool-use JSON schema |
| Observability | Sentry (web + core), CloudWatch logs/metrics, n8n execution log, Better Stack (or CloudWatch Synthetics) uptime | — | Errors, logs, uptime |

### Why this split
- **n8n** is the visible orchestration layer (a product claim) and owns *when* things happen: triggers, waits, retries, schedules, fan-out, notifications.
- **core-service** owns *what* happens: every rule in `01` §4 is implemented and unit-tested in Python, never inside n8n Function nodes. n8n nodes call core endpoints and branch on their JSON.
- **web** never calls the LLM or ERP directly. Human decisions are recorded by server actions (DB + audit), then the action calls the n8n resume webhook to continue the waiting execution.

## 2. Data flow per stage

```
intake ──▶ POST core /v1/documents/ingest        → documents row (sha256 unique per org)
            (re-delivery? → event 'redelivered', stop)
       ──▶ n8n Execute Workflow WF-10 process-invoice(document_id)

WF-10:
  1 extract   POST /v1/extract            → invoices + invoice_fields + invoice_lines, gate result
  2 gate?     IF gate == review → POST /v1/exceptions (extraction_review) → Wait(resume webhook) → (on resume) re-score
  3 enrich    POST /v1/enrich             → vendor_id, po_id, entity, location, GL per line
  4 screen    POST /v1/screen             → duplicate_candidates, fraud_signals, hold flag
  5 held?     IF hold → exception(s) → Wait(resume) → decision branch (merge/reject → end; release → continue)
  6 match     POST /v1/match              → match_results + match_line_results, verdict
  7 verdict   Switch: clean → 8 · else → exception + recommendation → Wait(resume) → decision
  8 post      POST /v1/post               → erp_postings (with idempotency key) ; failure → retries → posting_failed exception
  9 close     POST /v1/runs/{id}/close    → touchless computed, KPIs update
 10 notify    impact > $500 → Slack controller ; fraud → Slack controller
```

Every core endpoint writes its own `pipeline_events` row (stage, status, duration_ms, detail) inside the same transaction as its data writes, so the Pipeline screen is exactly as fresh as the data.

## 3. Sequence: human decision

```
Operator ─click Short-pay─▶ web server action decideException(exceptionId, 'short_pay')
  web: authz (role, SoD, limits) → tx { insert approvals; update exceptions status=resolved;
        insert audit_log } → commit
  web: POST n8n resume URL (stored on exceptions.resume_url) with {decision_id, action} + HMAC
  n8n: Wait node resumes → POST core /v1/post {invoice_id, pay_amount=2759.60, hold_amount=88.00}
  core: build ERP bill (lines at expected price; memo with hold reason) → QBO API → erp_postings
  core: POST /v1/notify/vendor-short-pay (email draft to vendor contact, logged)
  n8n: close run → Slack (if > $500) 
  web: Realtime event → UI updates, toast
```
If the n8n resume call fails, the server action still succeeds (decision is recorded); a `pending_resumes` row is created and WF-41 `resume-retry` (every minute) retries it. The UI shows `Decision recorded · posting queued`.

## 4. Idempotency and consistency
- `documents (org_id, sha256)` unique → duplicate deliveries are no-ops.
- Every core stage endpoint takes `(invoice_id, stage, attempt_key)`; writes are upserts keyed by `(invoice_id, stage)`; replays return the stored result.
- ERP posting uses `erp_postings (invoice_id, system)` unique + provider idempotency (QBO `RequestId` header = posting UUID).
- n8n executions are linked to `pipeline_runs.n8n_execution_id`; the error workflow marks the run `failed` and inserts into `dead_letters`.
- Clock: all timestamps `timestamptz` UTC; UI renders in org timezone (`orgs.timezone`, demo `America/New_York`).

## 5. Environments
| Env | Web | DB | AWS | n8n | Use |
|---|---|---|---|---|---|
| `local` | `pnpm dev` | `supabase start` (Docker) | LocalStack optional; Textract mocked | docker compose | Development |
| `staging` | Vercel Preview (per PR) + `staging` branch deployment | Supabase project `ledgic-staging` | account/ns `staging` | ECS service `n8n-staging` (scale 0 when idle) | Integration, QA |
| `production` | Vercel Production (`main`) | Supabase project `ledgic-prod` | `prod` | `n8n-prod` | Live demo |

Cost option (ask the user in Phase 0): collapse to **production + local only** (skip staging AWS services, use Vercel previews against the prod DB's `preview` schema is **not** allowed — previews use the staging Supabase project on the free tier).

## 6. Scaling notes (document, don't build)
- n8n → queue mode with Redis (ElastiCache) and separate worker tasks at > ~5k invoices/day.
- core → horizontal Fargate autoscaling on CPU; extraction concurrency limited by `EXTRACTION_MAX_CONCURRENCY` (default 4) to respect Anthropic rate limits.
- KPI views → materialized, refreshed by `pg_cron` every minute (already the design).
