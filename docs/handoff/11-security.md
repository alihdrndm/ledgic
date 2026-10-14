# 11 — Security

## 1. Threat model (what we defend against)
| Threat | Control |
|---|---|
| Vendor impersonation / bank-detail swap | Fraud screen (`01` §4.5); controller-only release; bank fingerprints hashed; bank changes require documented verification checkbox + comment; audit |
| Duplicate payment | Hash dedupe at intake; fuzzy duplicate screen; `duplicate_of` invoices can never post (DB check constraint on `erp_postings` insert via trigger) |
| Insider approving own edits | SoD rule enforced in `rpc_decide_exception` |
| Tampering with history | Append-only, hash-chained `audit_log`; `audit_verify` exposed in UI; privileges revoked; nightly verify job alerts on break |
| Cross-tenant data access | RLS on every table; pgTAP tests per table for member vs non-member; storage paths namespaced by org |
| Malicious attachments | MIME sniffing (not extension), size caps, PDFs rendered to images in an isolated container (no JS execution), SES virus verdict honored |
| Prompt injection inside invoices | The LLM only returns a schema via tool-use; its output never triggers actions; all values validated/typed; free-text fields rendered as text, never HTML |
| Webhook forgery | HMAC with timestamp on every internal call; SNS signature verification; resume URLs server-only |
| Secret leakage | No secrets in repo (gitleaks in pre-commit + CI + GitHub push protection); OIDC for AWS; Vault for integration tokens; Sentry scrubbing of `authorization`, `cookie`, bank fields |
| Public demo abuse | Viewer role cannot write; inbound demo email rate limit per sender; demo replay caps; Anthropic spend limit |

## 2. Data handling
- PII/financial: bank routing/account stored only as salted SHA-256 fingerprints + last 4; tax IDs likewise. Raw values exist transiently in core memory and in the source document image.
- Source documents: private bucket, signed URLs 5 min, access logged (`ui_events kind=document_viewed`).
- Retention: raw email 90 days (S3 lifecycle); documents and audit retained (configurable per org; demo org reset monthly — see `13` §7).
- Encryption: Supabase at rest; S3 SSE; TLS everywhere; ALB TLS policy `ELBSecurityPolicy-TLS13-1-2-2021-06`.

## 3. AuthN/AuthZ
- Supabase Auth sessions (httpOnly cookies via `@supabase/ssr`); session 12h, refresh rotation.
- Roles from `memberships`; every server action re-checks role server-side; UI gating is cosmetic.
- n8n UI behind its own auth + strong owner password; consider IP allowlist on ALB listener rule for `/` (not `/webhook/*`) — variable `n8n_admin_cidrs`.

## 4. Headers & web hardening
CSP (no `unsafe-inline` scripts; styles may need `'unsafe-inline'` for Next — use nonces if feasible), HSTS preload-ready, frame-ancestors none, CSRF inherent to server actions (origin check on), rate limiting on `/login` and `openDemo` (Upstash-free approach: Postgres-backed token bucket table).

## 5. Reviews before launch
- Run `supabase db lint` and the security advisor; fix all warnings.
- Run OWASP ZAP baseline against staging (CI job optional).
- Manually attempt: accessing another org's invoice by id; calling core without HMAC; replaying a resume webhook (must be idempotent/no-op); updating `audit_log` via SQL as service role (must fail).
