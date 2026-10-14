# Core API (frozen contract) — `services/core` (FastAPI, Python 3.12)

Base URL: `CORE_URL` (Railway in prod, `http://localhost:8000` locally). OpenAPI at `/openapi.json`.

## Envelope
Every JSON response (except `/mcp` and SSE streams):
```json
{"ok": true,  "data": { ... }}
{"ok": false, "error": {"code": "NOT_FOUND", "message": "Run not found", "retryable": false}}
```
HTTP status matches the error (400/401/403/404/409/422/429/500/503). Money is always a **decimal string** (`"2759.60"`), never a float. Timestamps ISO-8601 UTC.

Error codes: `UNAUTHENTICATED` (401), `INVALID_SIGNATURE` (401), `FORBIDDEN` (403, from `LEDGIC_FORBIDDEN:`; message is UI copy), `NOT_FOUND` (404), `CONFLICT` (409), `INVALID` (422), `RATE_LIMITED` (429, retryable), `BUDGET_EXHAUSTED` (429; the endpoint usually degrades instead of failing), `LLM_RATE_LIMITED` / `LLM_BAD_OUTPUT` (502, retryable), `DB_UNAVAILABLE` (503, retryable), `INTERNAL` (500).

## Auth
1. **User** — `Authorization: Bearer <Supabase access token>`. Core verifies the JWT locally with
   `SUPABASE_JWT_SECRET` (HS256, `aud=authenticated`, `exp`), falling back to `GET {SUPABASE_URL}/auth/v1/user`
   when the project uses asymmetric keys. The `sub` becomes the acting user: DB work that needs role checks
   runs in a transaction with `set local role authenticated` + `request.jwt.claims = {"sub": ..., "role": "authenticated"}`.
2. **Admin / service** — `X-Ledgic-Signature: t=<unix seconds>,v1=<hex>` where
   `v1 = HMAC_SHA256(CORE_HMAC_SECRET, f"{t}.{raw_body}")` (empty body → `f"{t}."`). Rejected when
   `|now − t| > 300` or mismatch (constant-time compare). Used by Vercel server code, GitHub Actions / cron, and replay tooling.
3. **MCP** — `Authorization: Bearer lgc_pat_<random>`; core hashes (sha256 hex) and looks up `mcp_tokens.token_hash`
   (not revoked); acts as `mcp_tokens.user_id` in `mcp_tokens.org_id`; `scopes` ⊇ `read` for reads, `decide` for `decide_exception`.
4. **BYOK** — optional `X-OpenAI-Key` header on copilot/draft/ingest: used for that request only, never stored or logged; bypasses the daily budget.

Rate limits via `rate_limit_hit` (see rpc.md); over limit → 429 `RATE_LIMITED`.

## Endpoints

### `GET /health` (no auth)
`data: {"status":"ok"|"degraded", "db": bool, "llm_mode": "fixture"|"recorded"|"live", "budget_remaining_usd": "0.42", "worker": {"alive": bool, "last_tick_at": ts}, "version": "<git sha>"}`. Always 200 unless the process is down (use `status`).

### `POST /v1/documents/ingest` (user JWT, role ≥ ap_clerk; or HMAC)
Body: `{"org_id": uuid, "channel": "upload"|"photo"|"email"|"portal"|"edi", "storage_path": "org/<org_id>/uploads/<uuid>.<ext>", "original_filename": str|null, "source_meta": {"location_id"?: uuid, "uploaded_by"?: uuid, ...}, "extraction_mode"?: "live"|"recorded"|"simulated"}`
- Verifies the object exists in bucket `documents` under the org prefix, ≤ 10 MB, ≤ 3 pages (pdf) / image; computes sha256.
- Same sha256 in org → `redelivered: true`, logs a `pipeline_events` intake/skipped on the original run, no new run.
- Else inserts `documents` + `pipeline_runs(status running, next_stage intake)` and `NOTIFY ledgic_runs`.
- Uploads from users are rate-limited `upload:ip:<ip>` 10/day; `live` extraction needs budget or BYOK, else falls back to `simulated`.
`data: {"document_id": uuid, "run_id": uuid|null, "run_number": int|null, "redelivered": bool}` (201)

### `POST /v1/runs/{run_id}/wake` (user JWT member of the run's org, or HMAC)
Belt-and-braces after an RPC decision (the RPC already did `pg_notify`). Sets nothing; nudges the worker.
`data: {"run_id": uuid, "status": "running"|"waiting"|..., "queued": bool}` (202)

### `GET /v1/runs/{run_id}` (user JWT member, or HMAC)
`data: {"run": {id, run_number, org_id, document_id, invoice_id, status, current_stage, next_stage, attempt, next_attempt_at, wait_exception_id, last_error, workflow_version, started_at, finished_at}, "events": [v_run_timeline rows]}`

### `POST /v1/copilot/ask` (user JWT, any member incl. viewer)
Body: `{"org_id": uuid, "question": str (≤ 500 chars), "context"?: {"invoice_id"?: uuid, "exception_id"?: uuid}, "stream"?: bool}`
- `Accept: text/event-stream` or `stream: true` → **SSE**. Events:
  - `event: status` `data: {"step": "retrieving"|"calling_tool"|"answering", "tool"?: str}`
  - `event: token`  `data: {"text": "..."}`
  - `event: citation` `data: {"n": 1, "chunk_id": uuid, "document_id": uuid, "title": str, "clause_ref": str|null, "quote": str}`
  - `event: done` `data: <final JSON as below>`
  - `event: error` `data: {"code","message","retryable"}`
- Otherwise JSON. Final payload:
`data: {"answer_md": str, "citations": [{n, chunk_id, document_id, title, kind, clause_ref, quote}], "mode": "live"|"cached"|"retrieval_only", "model": str|null, "tool_calls": [{"name": str, "args": {...}}], "cost_usd": "0.0012"}`
- Cache: `copilot_cache(org_id, sha256(normalized question))`; suggested questions are pre-seeded. Budget exhausted → `mode: retrieval_only` (top chunks, no LLM). Limits: ≤ 6 tool calls, ≤ 1.5k output tokens.

### `POST /v1/exceptions/{exception_id}/draft` (user JWT, role ≥ ap_clerk)
Body: `{"kind": "vendor_notice"|"explanation", "regenerate"?: bool}`
Runs the resolution agent (tools: kb_search, vendor history, PO/GRN, deterministic recommendation). Money guard: every money figure in `body_md` must equal one from the recommendation/match facts, else falls back to the template draft.
Returns the latest stored draft unless `regenerate`.
`data: {"draft_id": uuid, "kind": str, "body_md": str, "citations": [...], "mode": "live"|"recorded", "model": str|null, "prompt_version": str|null, "cost_usd": "0.0000", "created_at": ts, "guard": {"passed": bool, "figures": ["88.00","2759.60"]}}`

### Admin (HMAC only)
- `POST /v1/admin/replay/tick` body `{"org_id"?: uuid, "now"?: ts}` → drops the scheduled replay documents due since the last tick (demo orgs). `data: {"dropped": [{"document_id", "run_id", "channel", "hero": str|null}], "decided": int}`
- `POST /v1/admin/seed-today` body `{"org_id"?: uuid}` → backfills today's runs up to the current org-local time (idempotent). `data: {"runs_created": int}`
- `POST /v1/admin/reset-demo` body `{"org_id"?: uuid, "backfill_days"?: 30}` → purges demo org data (`demo_purge_org`), reseeds master data + history + today. `data: {"purged": {...counts}, "seeded": {...counts}}`

### `/mcp` (MCP streamable HTTP, bearer PAT; not wrapped in the envelope)
Tools: `list_exceptions`, `get_invoice`, `explain_match`, `search_contracts`, `get_kpis`, `decide_exception` (requires `decide` scope; role checked by `rpc_decide_exception`). Also `ledgic-mcp` stdio entry point with `LEDGIC_MCP_TOKEN`. Details in `docs/MCP.md`.

## Extraction output
`contracts/extraction.schema.json` is the strict JSON Schema for the extraction agent's output (strip `$schema`/`$id` before passing it as an OpenAI `json_schema` response format; the pydantic model in `app/ai` must produce an identical schema).
