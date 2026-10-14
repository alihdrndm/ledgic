# 07 — API contracts

## 1. Service-to-service auth
- **n8n → core**: header `X-Ledgic-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, t + "." + raw_body)>`; core rejects if |now − t| > 300s or signature mismatch. Secret `CORE_HMAC_SECRET` in AWS Secrets Manager, injected into both ECS tasks.
- **web → n8n** (resume + capture webhooks): same scheme with `N8N_WEBHOOK_SECRET`; n8n verifies in the first Code node. Resume URLs are never exposed to the browser — only server actions call them.
- **web → core** (a few synchronous reads: document page URLs, audit verify): same HMAC with `CORE_HMAC_SECRET` from Vercel env (server-only).
- **SNS → n8n**: SNS message signature verification (X.509 cert from `SigningCertURL`, host must end with `.amazonaws.com`).
- **Core → Supabase**: service role via the pooled Postgres connection string; never exposed.

## 2. Web (Next.js)

### 2.1 Reads
Server Components query Supabase with the user's session (RLS). Client components use TanStack Query + Supabase Realtime for invalidation. Query modules in `apps/web/lib/queries/*.ts`:
- `getPipelineToday(orgId)` → `mv_stage_today`, `v_pipeline_today`, `mv_channel_today`
- `getRecentRuns(orgId, limit)` → runs join invoices/vendors/locations (latest status)
- `getRun(runId)` → run + events + invoice summary
- `getReviewQueue(orgId)`, `getReviewItem(invoiceId)` → invoice, fields, lines, document pages (signed URLs via route handler `/api/documents/[id]/pages/[n]`)
- `getMatch(invoiceId)` → invoice, PO, GRN, match results, recommendation, decision
- `getExceptionQueue(orgId, sort)`, `getException(id)` (type-specific payloads)
- `getOps(orgId, period)` → `mv_ops_period`, `mv_location_period`, `mv_eval_weekly`, catches, sync status
- `getAuditTrail(entityType, entityId)`

### 2.2 Server actions (`apps/web/app/actions/*.ts`) — all call `security definer` RPCs, then side effects
| Action | Input | Checks | Effects |
|---|---|---|---|
| `confirmExtraction` | invoiceId, fields: [{field\|lineId+key, value}] | role ≥ ap_clerk; exception open | `rpc_confirm_fields` (writes fields v+1 source human, audit, resolves exception, `time_spent`) → resume n8n |
| `decideException` | exceptionId, action, comment?, payAmount?, holdAmount?, poId? | role & limit per `01` §4.7; SoD; action valid for type; amounts consistent with recommendation or recomputed server-side | `rpc_decide_exception` → approvals, exception status, audit → resume n8n (or `pending_resumes`) |
| `retryPosting` | exceptionId | ap_manager+ | resume WF-20 via core `/v1/post/retry` |
| `updatePolicy` | tolerance/gate/thresholds | admin | new `tolerance_policies` row / `org_settings` update + audit |
| `previewPolicy` | proposed values | admin | core `/v1/policy/preview` → counts over last 30 days |
| `inviteMember`, `updateMemberRole`, `removeMember` | … | admin | Supabase admin API + memberships + audit |
| `connectIntegration` | provider | admin | redirect to OAuth; callback route stores tokens in Vault via RPC |
| `trackUiEvent` | exceptionId, kind | member | ui_events insert (batched) |
| `openDemo` | — | none | signs in as demo viewer (server-side password grant with env secret) |

Money arguments are strings with 2 decimals, parsed with a decimal library (`decimal.js`), never JS floats.

### 2.3 Route handlers
- `GET /api/documents/[docId]/pages/[n]` → verifies membership → 302 to 5-minute signed Storage URL.
- `POST /api/capture/upload-url` → signed upload URL for `org/<org>/uploads/<uuid>.<ext>`.
- `POST /api/capture/complete` → calls n8n `capture` webhook with {org_id, storage_path, location_id, uploaded_by}.
- `GET /api/integrations/quickbooks/callback`, `GET /api/integrations/slack/callback` → OAuth code exchange (server-only secrets) → Vault.
- `GET /api/health` → web + DB ping.
- `/demo/vendor-portal/*` → mock portal pages + `GET /demo/vendor-portal/files/[id].pdf` (basic auth from env).

## 3. Core service (`https://core.<domain>`), JSON over HTTPS, HMAC-protected
All responses `{ok: true, data}` or `{ok: false, error: {code, message, retryable}}`. `retryable=true` → n8n retry; else → error workflow.

| Method & path | Body | Returns |
|---|---|---|
| `GET /health` | — | `{db, anthropic, textract, version}` (no HMAC) |
| `POST /v1/intake/email` | `{bucket, key}` | `{document_ids[], skipped:[{reason}]}` |
| `POST /v1/intake/edi` | `{bucket, key}` | `{invoice_ids[], document_ids[]}` |
| `POST /v1/documents/ingest` | `{org_id, channel, storage_path, source_meta}` | `{document_id, redelivered: bool}` |
| `POST /v1/portal/sync` | `{org_id?}` | `{document_ids[]}` |
| `POST /v1/runs/start` | `{document_id, n8n_execution_id, workflow_version}` | `{run_id, run_number}` |
| `POST /v1/extract` | `{run_id}` | `{invoice_id, gate_passed, doc_confidence, flagged_fields[]}` |
| `POST /v1/extract/rescore` | `{invoice_id}` | `{gate_passed: true}` |
| `POST /v1/enrich` | `{run_id}` | `{vendor_id, po_id?, entity_id, location_id, gl_coverage}` |
| `POST /v1/screen` | `{run_id, resume_url}` | `{hold, exception_ids[]}` |
| `POST /v1/match` | `{run_id, resume_url}` | `{verdict, exception_id?, recommendation?}` |
| `POST /v1/exceptions` | `{invoice_id, type, resume_url, reason?, amount_at_risk?}` | `{exception_id}` |
| `POST /v1/exceptions/escalate-due` | `{}` | `{escalated:[…]}` |
| `GET /v1/resumes/due` · `POST /v1/resumes/{id}/result` | — | resume jobs |
| `POST /v1/post` | `{invoice_id, pay_amount?, hold_amount?}` | `{system, external_id, status}` |
| `POST /v1/post/retry` | `{exception_id}` | same |
| `POST /v1/runs/park` · `/close` · `/fail` | `{run_id, …}` | `{}` |
| `POST /v1/digest/{org_id}` · `/sent` | — | Slack blocks |
| `POST /v1/policy/preview` | `{org_id, policy}` | `{would_hold, currently_held}` |
| `POST /v1/demo/next-batch` | `{org_id}` | `{dropped:[{channel, document}]}` |
| `POST /v1/eval/run` | `{org_id, week_start?}` | eval_run |
| `GET /v1/audit/verify/{org_id}` | — | `{ok, entries, first_broken_id?}` |

OpenAPI is generated by FastAPI at `/openapi.json`; CI exports it to `docs/api/core.openapi.json` and generates a TS client (`openapi-typescript`) for the few web → core calls.

## 4. Error codes (core)
`INVALID_SIGNATURE`, `NOT_FOUND`, `CONFLICT_STAGE` (stage already completed — returns stored result, not an error in practice), `LLM_RATE_LIMITED` (retryable), `LLM_BAD_OUTPUT` (retryable once, then review), `OCR_FAILED` (retryable), `ERP_AUTH` (non-retryable → posting_failed + reconnect prompt), `ERP_VALIDATION` (non-retryable), `ERP_UNAVAILABLE` (retryable), `DB_UNAVAILABLE` (retryable).
