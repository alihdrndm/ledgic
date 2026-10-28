# Architecture

This document covers how Ledgic is put together: the components, the data model, the orchestrator,
auth, realtime, scheduling and cost. The interfaces between parts are frozen in `contracts/`
(`core-api.md`, `rpc.md`, `views.md`, `extraction.schema.json`, `fixtures.json`). Why the design departs
from the original spec is recorded in [DECISIONS.md](DECISIONS.md).

## 1. Components

| Component | Where | Runs on | Responsibility |
|---|---|---|---|
| Web console | `apps/web` | Vercel Hobby | Next.js 16 App Router. Server components read Supabase with the **user's JWT** (RLS applies). Server actions call the decision RPCs. Route handlers proxy the copilot (SSE), uploads and search to core. The browser never talks to core directly. |
| Core service | `services/core` | Railway (one replica, Dockerfile) | One FastAPI process that hosts the REST API, the orchestrator worker, the scheduler and the MCP server. |
| Database | `supabase/migrations` | Supabase Free | Postgres 15 with pgvector, pg_trgm, pgcrypto, pg_cron. Holds all state, the security model (RLS, RPCs), KPI views and the audit chain. Also Auth, Storage (`documents` bucket) and Realtime. |
| LLM provider | `services/core/app/ai/gateway.py` | OpenAI | `gpt-4.1-mini` (vision + agents), `text-embedding-3-small` @ 512 dims. Called only for live uploads, live drafts and copilot answers, always metered and capped. |
| Corpus + KB | `services/core/app/demo/corpus`, `tools/corpus` | in core | Deterministic synthetic invoices (PDF and degraded dock photos), labels, the knowledge base markdown, and recorded hero outputs. |

Inside core (`services/core/app`):

| Package | Role |
|---|---|
| `main.py` | App factory. The lifespan opens the psycopg pool, starts the MCP session manager, the worker and the scheduler. `/mcp` is added with `add_route`, not `mount`, so clients never see a redirect. |
| `api/` | `routes.py` (`/v1/documents/ingest`, `/v1/runs/{id}`, `/v1/runs/{id}/wake`, `/v1/copilot/ask`, `/v1/exceptions/{id}/draft`), `admin.py` (`/health`, `/v1/admin/*`), `auth.py` (JWT, HMAC, BYOK), `envelope.py` (`{ok, data}` / `{ok, error}`). |
| `orchestrator/` | `engine.py` (step + apply), `worker.py` (claim loop, LISTEN), `stages.py`, `transitions.py`, `routing.py` (resume table), `handlers/` (one module per stage), `drafts.py` (background resolution-agent drafts). |
| `domain/` | Pure functions over `Decimal`: `tolerance`, `qty`, `gate` (confidence and calibration), `duplicates`, `fraud`, `pairing` (Hungarian assignment), `gl_knn`, `vendor_resolve`, `match_engine`, `recommend`, `approval`, `money`, `templates`. No I/O. |
| `ai/` | `gateway.py`, `extraction.py`, `resolution.py`, `copilot.py`, `tools.py`, `schemas.py`, `rag/` (`chunker`, `embed`, `index`, `retrieve`), `seed_kb.py`. See [AGENTS_RAG.md](AGENTS_RAG.md). |
| `mcp/` | `server.py` (tools/resources/prompts), `service.py` (queries), `auth.py` (PAT verification, demo token), `http.py`, `stdio.py`, `tokens.py` (CLI). See [MCP.md](MCP.md). |
| `scheduler/` | APScheduler jobs, leader-elected with a Postgres advisory lock. |
| `posting/` | `base.py` adapter protocol and `mock.py` deterministic QuickBooks / NetSuite adapters. |
| `repo/`, `db/` | SQL helpers per aggregate (`runs`, `invoices`, `exceptions`, `journal` for events and audit, `master`, `storage`) and the async pool with `as_user()`. |
| `demo/` | `seed.py` (master data), `corpus/` (generator), `planner.py`, `replay.py` (live drip, simulated decisions, nightly), `backfill.py` (history through the real stages). |

## 2. Data model

All tables live in `public`, carry `org_id`, and have RLS enabled. The DDL is in
`supabase/migrations/20261014000001_schema.sql`.

| Area | Tables |
|---|---|
| Tenancy and people | `orgs` (`is_demo`), `org_settings`, `profiles`, `memberships` (role enum `viewer < ap_clerk < ap_manager < controller`, with `admin` counted as controller) |
| Policy | `tolerance_policies` (± 2 % / $25 by default), `org_settings` (confidence gate 0.90, field floor 0.75, manager limit $5,000) |
| Master data | `entities`, `locations`, `vendors` (bank + W-9 fingerprints, `created_by`), `vendor_aliases`, `items`, `gl_accounts`, `contracts`, `contract_prices` (clause references) |
| Procurement | `purchase_orders`, `po_lines`, `goods_receipts`, `grn_lines` |
| Documents and invoices | `documents` (sha256, channel, storage path), `invoices` (status, `extraction_mode`, `touchless`, `human_touches`, `duplicate_of`), `invoice_fields` (versioned, `source` model or human, confidence, bbox), `invoice_lines` (per-cell confidences) |
| Checks | `duplicate_candidates`, `fraud_signals`, `match_results`, `match_line_results` |
| Workflow | `pipeline_runs` (orchestrator columns below), `pipeline_events` (stage timeline), `exceptions` (type, status, `amount_at_risk`, `sla_due_at`, `escalated`, `assigned_role`), `recommendations`, `approvals`, `exception_drafts`, `dead_letters` |
| ERP | `erp_postings`, `integrations` |
| AI | `kb_documents`, `kb_chunks` (`vector(512)`, `tsv`, `clause_ref`), `copilot_cache`, `llm_budget`, `llm_budget_reservations`, `cost_ledger`, `prompt_versions`, `eval_runs` |
| Access | `mcp_tokens` (sha256 only), `rate_limits`, `ui_events` |
| Audit | `audit_log` (`prev_hash`, `hash`) |

**Views** (`20261014000004_views.sql`), all `security_invoker` so RLS still applies:
`v_pipeline_today`, `v_stage_today`, `v_channel_today`, `v_recent_runs`, `v_run_timeline`,
`v_review_queue`, `v_invoice_detail`, `v_match_detail`, `v_exception_queue`, `v_invoice_audit`,
`v_kpi_periods`, `v_ai_budget_today` and `v_status_bar`. KPIs come from the materialized views `mv_ops_period`,
`mv_location_period` and `mv_eval_weekly`, exposed through `v_ops_period`, `v_location_period` and
`v_eval_weekly`, and refreshed every minute by `refresh_kpis()` (pg_cron, or the scheduler fallback).
Column-level definitions are in `contracts/views.md`.

**Audit chain.** A `before insert` trigger (`audit_chain`) takes a per-org advisory lock, reads the
previous row's hash and stores `hash = sha256(prev_hash | org | at (UTC, µs) | actor | action | entity | before | after)`.
Update, delete and truncate are blocked by triggers and revoked from every role. The one exception is
`demo_purge_org`, which may delete a whole demo org's chain so that verification still starts at `000…0`.
`audit_verify(org)` / `audit_verify_org(org)` recompute the chain. The UI's "Verify chain" button and the
MCP `verify_audit_chain` tool call these.

## 3. Orchestrator

Pipeline orchestration is code rather than an n8n workflow (DECISIONS D1). The state lives in
`pipeline_runs`, so a deploy or a crash never loses a run.

### 3.1 Stages

```
intake → extraction → review → enrichment → screening → match → approval → posting → close
```

| Stage | Handler | Typical transitions |
|---|---|---|
| intake | `handlers/intake.py` | advance → extraction |
| extraction | `handlers/extraction.py` | `simulated` / `recorded` / `live` read → calibrate → gate. Passes → enrichment. Fails gate → review |
| review | `handlers/review.py` | park on `extraction_review`. After `rpc_confirm_fields`, re-score → enrichment |
| enrichment | `handlers/enrichment.py` | vendor, PO, entity/location, line pairing (Hungarian), GL kNN → screening |
| screening | `handlers/screening.py` | duplicate ≥ 0.90 or fraud ≥ 0.70 → park on the hold (payment blocked). Else → match |
| match | `handlers/match.py` | clean → posting. Variance / qty / no PO → exception + recommendation → approval |
| approval | `handlers/approval.py` | park until `rpc_decide_exception` |
| posting | `handlers/posting.py` | mock ERP bill. Failure → retry. Exhausted → `posting_failed` exception (park) |
| close | `handlers/close.py` | touchless flag, final invoice status → finish |

### 3.2 Transitions

A handler returns a `Transition` (`orchestrator/transitions.py`) and `Engine.apply` persists it in the same
transaction as the handler's writes:

| Kind | Effect on `pipeline_runs` |
|---|---|
| `advance(next)` | `status=running`, `next_stage=next`, `attempt=0`, `next_attempt_at=now` and a `succeeded` event |
| `park(exception)` | `status=waiting`, `wait_exception_id`, `context.parked_stage`, `exceptions.run_id` linked, and a `waiting` event |
| `retry(error)` | `attempt+1`, `next_attempt_at = now + backoff`, `last_error`, and a `failed` event ("attempt n of 5 · next try in Ns") |
| `finish` | `status=succeeded` (or other final), `finished_at` |
| `fail` | `status=failed`, `last_error`, and a row in `dead_letters` |

- **Backoff:** 10, 30, 60, 120 and 300 s. `MAX_ATTEMPTS = 5`. A handler raising `StageError` rolls back
  the step, then records a retry. `FatalStageError` fails immediately.
- **Exhausted hooks:** after 5 failures a stage may provide a follow-up transition instead of failing.
  Posting opens a `posting_failed` exception and parks.
- **Leases:** `repo/runs.claim_next` does
  `update … where id = (select … where status='running' and next_attempt_at <= now() and (lease_until is null or lease_until < now()) order by next_attempt_at limit 1 for update skip locked)`,
  and sets `lease_owner = host:pid` and `lease_until = now() + 60 s`. A crashed worker's runs become
  claimable when the lease expires. `apply` clears the lease.
- **Worker:** `orchestrator/worker.py` runs 3 claim loops and 1 `LISTEN ledgic_runs` task. Ingest, the
  decision RPCs and `/v1/runs/{id}/wake` all `pg_notify('ledgic_runs', run_id)`. A 2 s poll covers retries
  that come due and missed notifications.
- **Idempotency:** ingest dedupes on `(org, sha256)` (a re-delivery logs `intake/skipped` on the original
  run). Decisions are consumed once (`context.consumed_decision`). `llm_budget_settle` is idempotent.

### 3.3 Human-in-the-loop resume

`rpc_decide_exception` and `rpc_confirm_fields` do everything in **one transaction**: role and limit
checks, segregation of duties, the `approvals` row, hash-chained audit rows, `pipeline_runs.status='running'`
with `context.decision`, a `resumed` event, and `pg_notify`. The worker then picks the run up and
`routing.route_resume(action)` decides where it continues:

| Decision | Resumes at |
|---|---|
| `confirm_fields` | review (re-score) → enrichment |
| `short_pay`, `approve_as_is`, `approve_without_po`, `retry_posting` | posting |
| `link_po` | match |
| `release_hold`, `not_duplicate` | screening (next open hold, else match) |
| `merge`, `reject_copy`, `reject_invoice` | close (a merged survivor continues through screening) |
| `dispute`, `request_w9` | stays parked |

## 4. Auth model

| Caller | Mechanism | Identity in the DB |
|---|---|---|
| Browser → Supabase | Supabase Auth session (magic link, or the demo password grant done **server-side** in `app/login/actions.ts`, so demo passwords never reach the browser) | `auth.uid()`. RLS on every table |
| Web server → core | `Authorization: Bearer <user access token>` | Core verifies the JWT (HS256 with `SUPABASE_JWT_SECRET`, falling back to `GET /auth/v1/user`) and acts as that user |
| Operator tooling → core admin | `X-Ledgic-Signature: t=<unix>,v2=HMAC_SHA256(CORE_HMAC_SECRET, "<t>.<METHOD>.<path>.<raw body>")`, ± 300 s window, constant-time compare (`api/auth.py`) | service principal |
| MCP client → core | `Authorization: Bearer lgc_pat_…`, sha256 lookup in `mcp_tokens`, scopes `read` / `decide` | the token's user |
| Visitor's own key | `X-OpenAI-Key` on copilot / draft / ingest | used for that request only, never stored or logged |

**Act-as-user.** Whenever core, the MCP server or the replay needs a role check, it runs the work in a
transaction after `db.pool.as_user(conn, user_id)`:

```sql
select set_config('request.jwt.claims', '{"sub":"<uuid>","role":"authenticated"}', true);
set local role authenticated;
```

From then on `auth.uid()`, RLS policies and the `security definer` RPC checks behave exactly as for a
browser request. Role limits, the $5,000 manager limit, controller-only fraud release and segregation of
duties are therefore implemented once, in SQL (`20261014000003_rpc.sql`), and tested with pgTAP. RPC errors
use stable prefixes (`LEDGIC_FORBIDDEN:`, `LEDGIC_NOT_FOUND:`, `LEDGIC_CONFLICT:`, `LEDGIC_INVALID:`)
that core maps to 403/404/409/422 (`contracts/rpc.md`).

Rate limits use one SQL primitive, `rate_limit_hit(key, limit, window)`: login 5/IP/hour, uploads
10/IP/day, MCP 60 calls/min/token.

## 5. Realtime

Migration `20261014000005_realtime.sql` adds `pipeline_events`, `exceptions`, `approvals`, `erp_postings`
and `pipeline_runs` to the `supabase_realtime` publication. Screens mount
`useRealtimeRefresh(tables, { orgId })` (`apps/web/lib/realtime.ts`), which subscribes with
`org_id=eq.<id>` (Realtime applies each table's RLS select policy per subscriber) and calls a debounced
`router.refresh()` (500 ms). Server components re-render from the views, so the UI never patches state by hand.

## 6. Scheduler and demo replay

`scheduler/jobs.py` runs APScheduler inside core. Only the process holding
`pg_try_advisory_lock(0x1ED61C)` on a dedicated connection executes jobs, so a second replica is harmless.

| Job | When | What |
|---|---|---|
| `replay_tick` | every 5 min, if `REPLAY_ENABLED` | releases the demo documents due since the last tick (about 180/day, heroes at fixed local times) and applies simulated decisions by the "Demo replay" AP manager through the real RPCs |
| `sla_escalation` | every 15 min | open, unviewed exceptions past `sla_due_at` → `escalated`, assigned to controller, audit row |
| `nightly` | 03:00 America/New_York | auto-resolve stale demo exceptions, reset earlier heroes, purge data older than 30 days, drop stored files older than 7 days |
| `refresh_kpis` | every minute, only without pg_cron | `select refresh_kpis()` |
| `release_stale_llm` | every 5 min, only without pg_cron | releases LLM reservations older than 10 min |

History is produced by `app.demo.backfill`, which pushes each historical document through **the same
stage handlers** on a virtual clock (`drive_run`). The KPIs are therefore computed from real runs, not
inserted. Admin endpoints (`/v1/admin/replay/tick`, `/v1/admin/seed-today`, `/v1/admin/reset-demo`) expose
the same operations under HMAC.

## 7. Cost guardrails

| Guard | Implementation |
|---|---|
| Daily LLM cap | `LLM_DAILY_CAP_USD` (default `0.50`). `LlmGateway.metered()` estimates the cost, calls `llm_budget_reserve(est, cap)` (an atomic conditional update; `null` means over budget), makes the call, settles the actual cost from token usage with `llm_budget_settle`, and writes `cost_ledger`. If the budget RPC is missing or errors, the call is refused (fail closed). |
| Degradation | Extraction over budget → park in review with empty fields. Draft → recorded or template draft. Copilot → cached or retrieval-only answer. `search_contracts` → full-text only. |
| $0 replay | Replay and backfill use simulated extraction (from the corpus) and recorded hero outputs. `LLM_MODE=fixture` never constructs an OpenAI client. |
| Copilot | Cache keyed by `sha256(normalized question)`, with suggested questions precomputed at seed time. ≤ 6 tool calls, ≤ 1.5k output tokens. |
| Uploads | 10/IP/day, ≤ 10 MB, ≤ 3 pages, pages downscaled to 1600 px. |
| BYOK | `X-OpenAI-Key` skips the owner's budget. The call is still recorded in `cost_ledger` with `meta.billing='byok'`, so cost KPIs stay truthful. |

## 8. Free-tier fit

- **Supabase Free (500 MB DB, 1 GB storage):** 30-day rolling demo data, purged nightly. Non-hero
  documents' files are dropped after 7 days. Synthetic PDFs are under 10 KB each. Scheduler activity
  keeps the project from pausing. Demo logins use a password grant, so no auth email quota is used.
- **Railway:** one replica, about 300 MB RAM. No OpenCV, torch or onnx (embeddings come from the API, and
  image work uses Pillow and pypdfium2). Health check `/health`, restart on failure.
- **Vercel Hobby:** server components and route handlers only, with no long-running work. SSE for the
  copilot is proxied from core.
- **OpenAI:** a $0.50/day cap in the database, plus a monthly limit set in the provider dashboard.
