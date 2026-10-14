# 08 — Integrations

## 1. Inbound email (AWS SES)
- Region **us-east-1** (SES receiving is regional).
- Domain: a subdomain the user controls, e.g. `ap.<domain>` (ask the user which domain in Phase 0; if none, STOP — buying one needs approval). Records: `MX 10 inbound-smtp.us-east-1.amazonaws.com` on the subdomain; SES domain identity verification (DKIM CNAMEs).
- Receipt rule set `ledgic-<env>`: recipients `invoices@ap.<domain>` (prod) and `invoices-staging@ap.<domain>`; actions: (1) S3 → `ledgic-<env>-raw-mail/incoming/`, (2) SNS → topic `ledgic-<env>-inbound-mail` (HTTPS subscription to n8n WF-01). Spam/virus scanning on; drop if `spamVerdict`/`virusVerdict` FAIL (Lambda-free: n8n checks the verdicts in the SNS payload and skips).
- Core `/v1/intake/email`: parse MIME, accept `application/pdf`, `image/*` attachments ≤ 20 MB, ignore inline logos (< 20 KB images with Content-ID), record `from`, `subject`, `message_id` in `source_meta`. Org resolution: recipient address → org (table `inbound_addresses`, `05` §7).
- Demo: the demo inbox address is shown on the login page's demo block ("Send an invoice PDF to invoices@… and watch it arrive"); rate-limit per sender (10/hour) to protect cost.

## 2. OCR cross-check (AWS Textract)
`AnalyzeExpense` synchronous API per page (≤ 10 MB images). IAM: the core task role gets `textract:AnalyzeExpense` only. Record page count cost (use current AWS price in config).

## 3. LLM (Anthropic)
- API key in Secrets Manager (`ledgic/<env>/anthropic`), injected into core. Workspace spend limit set in the console (runbook §6).
- Model id via `LLM_MODEL`; tool-use structured output; retries with exponential backoff on 429/529 (max 4).
- Log `request_id`, tokens, latency to `cost_ledger.meta`. No document images are logged anywhere else.

## 4. QuickBooks Online (real sandbox)
- Intuit Developer account → app `Ledgic` → **Accounting** scope `com.intuit.quickbooks.accounting`; redirect URIs: `https://<web>/api/integrations/quickbooks/callback` (+ staging, + `http://localhost:3000/...`).
- Sandbox company: one per entity that maps to QBO (demo: Entity 1 and Entity 2 → two sandbox companies if the developer account allows; else one company with Classes for entities and Locations for sites — record choice).
- Seed the sandbox with the demo vendors (display names = demo vendor categories), GL accounts (`5000 COGS-Food`, `5010 COGS-Beverage`, `6100 Janitorial`, `6200 Smallwares & Equipment`, `2000 Accounts Payable`), Classes = locations, and the POs (QBO PurchaseOrder) via a one-time script `tools/seed_qbo.py`.
- Posting = `Bill` (not JE). The design's inspector text says `JE 18,240` — display the QBO Bill `DocNumber`/Id as `Bill <id>`; update copy to `Posted — QuickBooks, Bill <id>`.
- Token storage in Supabase Vault; refresh every < 60 min on use; if refresh fails → integration status `needs_reconnect`, Slack alert, posting exceptions `posting_failed`.

## 5. NetSuite
Adapter implemented against the REST Record API (`vendorBill`) with OAuth 2.0 client credentials (M2M) and contract tests using recorded fixtures. **Default to the mock adapter** (see `06` §9) unless the user provides a NetSuite sandbox. The UI must label mock mode (`NetSuite (mock)`) on demo orgs — do not pretend.

## 6. Slack
- Slack app `Ledgic` (manifest in `infra/slack/manifest.yml`): bot scopes `chat:write`, `chat:write.public`, `im:write`, `users:read.email`. OAuth redirect `https://<web>/api/integrations/slack/callback`. Install to a workspace the user chooses (runbook §9; for the demo a dedicated free workspace `ledgic-demo` is fine).
- Channels: `#ap-digest` (daily digest), `#ap-alerts` (DLQ, posting failures, fraud holds). Controller DMs resolved by email.
- Digest (Block Kit): header `AP digest · <date>`; section with yesterday's received / touchless / exceptions opened / cleared / held back; list of open exceptions older than 12h with links; context line `Computed from pipeline runs · Ledgic`.
- Alert formats: `Fraud hold · <vendor> · <invoice> · $<amount> — <signals>` with a button link to the exception.

## 7. Vendor portals
- `portal/base.py`: `PortalConnector.list_new(since) -> [RemoteInvoice]`, `download(ri) -> bytes`. Credentials per portal in Vault.
- `mock_portal.py`: logs into `/demo/vendor-portal` with Playwright (Chromium in the core image) or httpx if the portal is form-based (it is), lists invoices newer than the last sync cursor, downloads PDFs. This exercises the real code path.
- Real portals are per-customer work; document the connector contract in `docs/portals.md`.

## 8. EDI 810
- Transport for demo: files dropped to `s3://ledgic-<env>-edi-inbound/<org_slug>/` (the demo replay writes them; a real partner would use AWS Transfer Family SFTP — document, don't build).
- Parser `edi/x12_810.py`: handle ISA/GS/ST/BIG/N1/IT1/TDS/CAD/SE/GE/IEA; element separator from ISA; map BIG02 invoice number, BIG01 date, BIG04 PO, IT1 lines (qty, UoM, unit price, product ids), TDS total (implied 2 decimals). Validate control numbers; reject malformed with a dead letter. Unit tests with sample 810s generated by the corpus tool.

## 9. Receiving (GRNs)
In the demo, GRNs are seeded and also created by the demo replay at "delivery time". Document the future integration (a receiving app / POS inventory feed) in `docs/receiving.md`; expose `POST /v1/grns` in core for it.
