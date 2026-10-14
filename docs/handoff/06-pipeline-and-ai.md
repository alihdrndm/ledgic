# 06 — Pipeline, core service, and AI

## 1. Principles
- Deterministic rules in Python, unit-tested; the LLM does **reading**, never deciding.
- Every AI-produced value stores a calibrated confidence and a provenance (`field_source`, bbox, model/prompt version).
- Every stage is idempotent and writes `pipeline_events` + `audit_log` + `cost_ledger` in its transaction.

## 2. n8n workflows (`services/n8n/workflows/*.json`)

n8n is pinned (e.g. `n8nio/n8n:1.x.y` — use the latest stable at build time and record it). Database: Postgres (Supabase, schema `n8n`, dedicated DB user). `EXECUTIONS_DATA_PRUNE=true`, `EXECUTIONS_DATA_MAX_AGE=336` (14 days). `N8N_ENCRYPTION_KEY` from Secrets Manager. User management on; owner account created during setup (runbook §7). Public API enabled with an API key used by CI to import workflows.

All HTTP Request nodes to core: base URL `{{$env.CORE_URL}}`, header `X-Ledgic-Signature: <HMAC-SHA256 of body with CORE_HMAC_SECRET>` computed in a preceding Code node (one reusable sub-workflow `WF-00 sign-and-call`), timeout 120s for extraction, 30s otherwise, **Retry on Fail: 3, wait 5s** (extraction: 2 retries, wait 20s). Every workflow's Error Workflow setting = `WF-90`.

| ID | Name | Trigger | Steps |
|---|---|---|---|
| WF-00 | sign-and-call | Execute Workflow | Code(sign) → HTTP → return JSON; normalizes errors |
| WF-01 | intake-email | Webhook `POST /webhook/ses-inbound` (SNS HTTPS subscription) | Confirm SNS subscription (handle `SubscriptionConfirmation` by GETting `SubscribeURL`); verify SNS signature (Code node with cert fetch + cache); → core `/v1/intake/email` {bucket, key} (core fetches MIME from S3, extracts PDF/image attachments, stores each, returns document_ids) → for each: Execute WF-10 (wait = false) |
| WF-02 | intake-photo | Webhook `POST /webhook/capture` (called by web after upload; HMAC) | core `/v1/documents/ingest` → Execute WF-10 |
| WF-03 | intake-portal | Cron hourly at :05 | core `/v1/portal/sync` (all enabled portals) → for each new document_id: Execute WF-10 |
| WF-04 | intake-edi | Webhook from SNS (S3 `edi-inbound` ObjectCreated) | core `/v1/intake/edi` {bucket,key} → invoices created directly with `field_source='edi'`, confidence 1.0 → Execute WF-10 with `skip_extraction=true` |
| WF-10 | process-invoice | Execute Workflow (document_id, org_id, skip_extraction?) | See §2.1 |
| WF-20 | erp-post | Execute Workflow (invoice_id, pay_amount?, hold_amount?) | core `/v1/post` with retries 5, backoff 10/30/60/120/300s → on final failure core `/v1/exceptions` type posting_failed + Slack alert |
| WF-30 | slack-digest | Cron every 15 min; Code node checks each org's local time == digest time | core `/v1/digest/{org}` → Slack `chat.postMessage` (Block Kit, §7) → core `/v1/digest/{org}/sent` (status bar/Pipeline column shows "09:30 sent") |
| WF-31 | alerts | Execute Workflow (kind, payload) | Slack message to `#ap-alerts` or controller DM |
| WF-40 | sla-escalation | Cron every 15 min | core `/v1/exceptions/escalate-due` → for each escalated: WF-31 |
| WF-41 | resume-retry | Cron every minute | core `/v1/resumes/due` → POST each resume URL → core mark result |
| WF-50 | demo-replay | Cron every 5 min, 05:30–21:00 org-local, demo orgs only | core `/v1/demo/next-batch` → drops documents into channels (see `13` §6) |
| WF-60 | eval-weekly | Cron Monday 03:00 UTC | core `/v1/eval/run` → Slack summary |
| WF-90 | error-handler | Error Trigger | core `/v1/runs/fail` {execution, node, error} (marks run failed, inserts dead_letters) → WF-31 alert |

### 2.1 WF-10 process-invoice (node by node)
1. **Start** → core `/v1/runs/start` {document_id, n8n_execution_id: `{{$execution.id}}`, workflow_version: `{{$env.WORKFLOW_VERSION}}`} → `run_id`.
2. IF `skip_extraction` → go to 5.
3. **Extract** → core `/v1/extract` {run_id} → `{invoice_id, gate_passed, doc_confidence, flagged_fields[]}`.
4. IF `!gate_passed` → core `/v1/exceptions` {type: extraction_review, resume_url: `{{$execution.resumeUrl}}`} → **Wait** (Resume: On webhook call; limit wait time 7 days) → core `/v1/extract/rescore` {invoice_id} (applies human-confirmed values) → continue.
5. **Enrich** → `/v1/enrich` {run_id}.
6. **Screen** → `/v1/screen` {run_id} → `{hold: bool, exception_ids[]}`. IF hold → Wait (resume) → Switch on `decision.action`: `merge`/`reject_copy`/`reject_invoice` → `/v1/runs/close` (status rejected/duplicate) → end; `release_hold`/`not_duplicate` → continue.
7. **Match** → `/v1/match` {run_id} → `{verdict, exception_id?}`.
8. **Switch verdict**: `clean` → 10. Otherwise → Wait (resume; exception already created by `/v1/match` with this execution's resume URL passed in the request) → Switch `decision.action`: `short_pay` → 10 with pay/hold; `approve_as_is`/`approve_without_po` → 10; `dispute` → `/v1/runs/park` (status waiting, will be resumed again when dispute resolves) → Wait again; `link_po` → back to 7; `reject_invoice` → close rejected.
9. (notify branch in parallel on exception creation) IF `amount_at_risk > controller_notify_threshold` or type = new_vendor_screen → WF-31.
10. **Post** → Execute WF-20 (wait = true).
11. **Close** → `/v1/runs/close` {run_id} → computes `touchless`, `human_touches`, sets `posted_at`.

Workflow version string (`v14` in the design) = `WORKFLOW_VERSION` env on the n8n task, bumped by CI when workflow JSON changes (`services/n8n/VERSION`).

## 3. Core service layout (`services/core`)
```
app/
  main.py                 FastAPI app, routers, HMAC dependency, health
  config.py               pydantic-settings (env)
  db/                     connection pool (psycopg 3, Supabase pooler URL), repositories, models
  audit.py                write_audit(tx, actor, action, entity, before, after)
  events.py               emit_event(tx, run_id, stage, status, summary, detail, duration)
  costs.py                record_cost(tx, run_id, kind, amount, meta)
  intake/                 email.py (MIME via email stdlib), photo.py, portal/ (base.py, mock_portal.py), edi/x12_810.py
  preprocess/             pdf.py (pypdfium2 render @200dpi), image.py (OpenCV deskew, perspective, CLAHE), phash.py (imagehash)
  extraction/             schema.py, prompt.py, llm.py (anthropic SDK), textract.py (boto3), reconcile.py, calibrate.py, gate.py
  enrichment/             vendor.py, po.py, gl.py, coding.py
  screening/              duplicates.py, fraud.py
  matching/               pairing.py, tolerance.py, engine.py, recommend.py, templates.py
  posting/                base.py, quickbooks.py, netsuite.py, mock.py, vendor_notice.py
  exceptions_svc.py       create/escalate/resume bookkeeping
  digest.py               Slack digest payloads
  eval/                   harness.py, metrics.py
  demo/                   replay.py
tests/                    unit (rules), integration (against local Supabase), golden files
```
Dependencies (pin in `pyproject.toml`, manage with `uv`): fastapi, uvicorn[standard], pydantic, pydantic-settings, psycopg[binary,pool], anthropic, boto3, pypdfium2, pillow, opencv-python-headless, imagehash, numpy, scikit-learn (isotonic calibration), rapidfuzz, scipy (Hungarian), httpx, playwright (portal), python-multipart, sentry-sdk, structlog; dev: pytest, pytest-asyncio, hypothesis, ruff, mypy.

## 4. Preprocessing
- PDF: render each page to PNG at 200 DPI (pypdfium2); keep text layer if present (pass to LLM as auxiliary text).
- Photo: EXIF-orient; detect page quadrilateral (Canny + contour approx) → perspective warp; deskew via Hough/minAreaRect → record `skew_deg` (shown on the Extraction screen footer); CLAHE contrast; downscale longest side to 2000px.
- Store rendered pages at `org/<org>/docs/<doc_id>/page-<n>.png` and a 104×132 thumbnail.
- Compute pHash of page 1.

## 5. Extraction

### 5.1 Output schema (tool-use input schema passed to Claude; also the pydantic model)
```json
{
  "vendor_name": {"value": "string", "confidence": 0-1, "bbox": {"page":1,"x":0,"y":0,"w":0,"h":0}},
  "invoice_number": {...}, "invoice_date": {"value":"YYYY-MM-DD", ...}, "due_date": {...}, "terms": {...},
  "po_reference": {...}, "subtotal": {"value": "decimal string"}, "tax": {...}, "freight": {...}, "total": {...},
  "currency": {...},
  "remit_to": {"value": {"name":"","address":""}, ...},
  "bank_details": {"value": {"routing":"","account":""}, ...},
  "lines": [ { "description": {...}, "qty": {...}, "uom": {...}, "unit_price": {...}, "amount": {...} } ],
  "document_type": "invoice|credit_memo|statement|other",
  "multiple_invoices_detected": false
}
```
Bounding boxes are normalized to the rendered page (0–1). Money as decimal strings, never floats.

### 5.2 Prompt (store as `extraction/prompts/p-<n>.md`, versioned; record in `prompt_versions`)
System prompt essentials (write the full prompt; these are the requirements):
- Role: extract accounts-payable fields from the supplied page images exactly as printed; never infer values that are not visible; return `null` with confidence 0 when absent.
- Confidence: report how legible and unambiguous each value is (not whether it's "likely correct"); smudged/overwritten digits must lower confidence.
- Bounding boxes for every non-null value.
- Units: copy unit of measure literally; don't convert.
- Lines: one entry per printed line; don't merge; include fees as lines.
- Call the `record_invoice` tool exactly once.
Model: `LLM_MODEL` env — use the current Claude Sonnet vision-capable model at build time (record the exact model id in `prompt_versions`). `temperature=0`. Images as base64 PNG, max 5 pages per call (split longer docs and merge lines). Record token usage and compute cost into `cost_ledger` using a price table in config.

### 5.3 Cross-check and calibration
1. Call Textract `AnalyzeExpense` on the same pages (cost to `cost_ledger` kind `ocr`).
2. `reconcile.py`: for each header field and each line (paired by position/description similarity), compare normalized LLM vs Textract values → `agree ∈ {1, 0, missing}`.
3. Features per field: model confidence, agree flag, Textract confidence, arithmetic-consistency flag, field type. `calibrate.py` loads an isotonic regression model (per field type) trained by the eval harness on the labeled corpus (`models/calibration-<prompt>.joblib`, committed) → calibrated confidence stored in `invoice_fields.confidence` (raw in `raw_confidence`). Until the first training run exists, use a conservative fallback: `c = model_conf × (1.0 if agree else 0.8 if missing else 0.6)`.
4. Gate per `01` §4.3; flagged fields = those < field floor; persist `gate_passed`, `doc_confidence`.
5. EDI: parse to the same schema, `source=edi`, confidence 1.0, gate passes.

### 5.4 Rescore after human review
`/v1/extract/rescore` replaces reviewed fields with `source=human, confidence=1.0`, re-runs arithmetic checks, sets `gate_passed=true` (human confirmation always passes), increments `human_touches`.

## 6. Enrichment
- **Vendor**: exact alias match → tax-id hash match → trigram on `display_name`/aliases (rapidfuzz `token_set_ratio` ≥ 90) → else create **unverified** vendor record (triggers fraud screen `vendor_age_lt_14d`). Confidence recorded.
- **PO**: extracted `po_reference` exact (normalized) → open POs for vendor+location ordered within 30 days whose total is within 10% → none → `no_po`.
- **Entity/location**: from PO; else from `source_meta.location_id` (photo) or vendor default; else from "Sold to/Ship to" text via alias table.
- **Item pairing**: per invoice line: vendor SKU (if present) → description similarity (rapidfuzz + embedding cosine via pgvector) with UoM compatibility → Hungarian assignment (scipy `linear_sum_assignment`) on cost `1 − sim`; pairs below 0.6 → unmatched.
- **GL**: kNN over the org's historical coded lines (pgvector, k=7, cosine) → majority vote; confidence = vote share × mean similarity; fallback `items.default_gl`; fallback vendor default GL. Store `gl_confidence`. (No LLM needed; document why.) Embeddings: use a hosted embedding model (e.g., Voyage via Anthropic's recommendation) or `fastembed` locally in the container — choose `fastembed` (BAAI/bge-small, 384-dim) to avoid another vendor; **adjust `vector(1024)` to the chosen dimension**.

## 7. Screening
- `duplicates.py` implements `01` §4.4; candidate search: same vendor, total within $0.01 or same normalized number, invoice_date within 7 days, last 180 days. Evidence JSON exactly as consumed by the UI.
- `fraud.py` implements `01` §4.5. `amount_anomaly` uses vendor's last 90 days mean/std (≥ 5 invoices, else skipped). Bank fingerprint compares extracted `bank_details` (if any) to `vendors.w9_bank_fingerprint`.
- Hold → create exceptions (`duplicate` with `amount_at_risk = total`; `new_vendor_screen` assigned to controller).

## 8. Matching and recommendation
`engine.py`:
```
for each paired (inv_line, po_line):
    grn_qty = Σ grn_lines.qty_received for po_line
    expected_unit, source, clause = contract_price(vendor, item, invoice_date) or (po_line.unit_price, 'po', None)
    apply tolerance (01 §4.1) and qty rules (01 §4.2) → line verdict (+ note, e.g. 'ordered 12 · received 12 · invoiced 12')
invoice verdict = clean if all matched/favorable; else single failing type or 'mixed'
```
Write `match_results` + `match_line_results` (+ `duration_ms`). Exceptions: one per invoice for the dominant type with `amount_at_risk = Σ positive deltas beyond expected` and reason string template: `<item short> <pct>% over <contract|PO>` (e.g., `shrimp 12% over contract`).

`recommend.py` rules (first match wins):
1. price_variance ∧ all failing lines have contract source ∧ GRN full → **short_pay** to expected; confidence per `01` §4.6.
2. price_variance ∧ PO source (no contract) → **short_pay** to PO price, confidence 0.70.
3. qty_mismatch ∧ received < invoiced → **short_pay** to received qty, confidence 0.85.
4. no_po → **link_po** if a candidate PO exists (confidence = candidate score) else **approve_without_po** requires manager, confidence 0.50.
5. otherwise → no recommendation (rail shows "No recommendation — decide manually").

`templates.py` reason bullets (fill from facts; exact wording for the hero case):
- `The agreement on file fixes this item at $3.68/lb through September; the invoice bills $4.12.`
- `The same variance appeared twice this quarter ($61.60 and $47.20). Both were short-paid and both were accepted.` (omit if zero prior; singular form for one)
- `Goods were received in full, so there is no quantity basis to dispute — only price.`
- `A vendor notice is drafted with the clause reference attached.`

## 9. Posting
`posting/base.py` interface: `create_bill(invoice, lines, pay_amount, hold_amount, coding) -> PostingResult`. Implementations:
- `quickbooks.py` — QBO REST v3 `Bill` with `VendorRef`, `Line[] (AccountBasedExpenseLineDetail: AccountRef=GL, ClassRef=location, amount at expected price)`, `PrivateNote` containing hold reason and Ledgic invoice id; `RequestId` = posting id. OAuth2 tokens from Supabase Vault via `integrations.vault_secret_id`; refresh token rotation stored back to Vault. Sandbox company for demo.
- `netsuite.py` — REST Record API `vendorBill` with subsidiary/location/class; TBA (OAuth 1.0a) or OAuth 2.0 M2M. **Use `mock.py` unless NetSuite credentials are provided** (record in BUILD_LOG); mock returns deterministic ids and latency 300–900ms so the UI and KPIs behave realistically; mock postings are labeled `system=netsuite, response.mock=true` and the Operations sync block shows `NetSuite (mock)` for demo orgs.
- `vendor_notice.py` — renders a short-pay notice (plain text + PDF) to the vendor contact; in demo orgs it is stored, not sent.

## 10. Eval harness (`app/eval`)
- Inputs: the synthetic corpus with ground truth (`13` §3) + (for real orgs) human-verified corrections as labels.
- Weekly: sample N=200 documents from the week's processed set (stratified by channel), compare final *pre-human* extracted values to labels with normalization rules (dates ISO, money to cents, invoice numbers normalized, descriptions fuzzy ≥ 0.9), write `eval_runs` with `by_field` breakdown. This is the **only** source for "Field accuracy, sampled".
- Also trains the isotonic calibration model when the prompt version changes (CI job `eval.yml`, artifacts committed via PR).
- Target: ≥ 95% field accuracy on the corpus; if below, the dashboard shows the real number — never tweak the display.
