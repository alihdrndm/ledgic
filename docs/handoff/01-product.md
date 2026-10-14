# 01 — Product specification

## 1. Users and roles

| Role (`member_role` enum) | Who | Can do |
|---|---|---|
| `viewer` | Execs, auditors, the **public demo account** | Read everything in the org. No actions. Every action button renders disabled with a tooltip "Read-only access". |
| `ap_clerk` | AP staff | Confirm/correct extracted fields; resolve extraction reviews; add notes; resolve `no_po` by linking a PO; cannot approve money decisions above tolerance. |
| `ap_manager` | AP manager (design persona **Elena Marsh**, initials `EM`) | Everything a clerk can, plus decide price/quantity exceptions and duplicates, with impact ≤ `approval_rules.manager_limit` (default **$5,000.00**). |
| `controller` | Controller (design persona **Tom Iwu**, initials `TI`) | Everything; the only role that can release **fraud holds** and decide exceptions above the manager limit. Receives escalations. |
| `admin` | Org owner / implementer | Everything plus settings: tolerance policy, approval rules, integrations, team. |

Personas: the design uses `EM` in the top bar on operator screens and `TI` on the Operations screen. In the demo, seed both users (see `13-demo-data.md`).

Segregation of duties (enforced server-side and in DB policy):
- A user who **edited** an invoice's extracted monetary fields cannot be the approver of an exception on that same invoice.
- A fraud hold can only be released by a `controller`, and never by the user who created the vendor record.

## 2. Glossary

- **Document** — one received file (PDF, image, EDI interchange). Identified by SHA-256.
- **Invoice** — the structured record extracted from a document. One document → one invoice (multi-invoice PDFs are split at intake; see `06` §3.2).
- **Run** — one pass of an invoice through the pipeline (`pipeline_runs`). Stage transitions are `pipeline_events`.
- **Stage** — `intake → extraction → enrichment → screening → match → approval → posting` (plus `notify`). The Pipeline screen groups `enrichment` + `screening` as "03 Enrichment".
- **Confidence gate** — the threshold (default **0.90** document confidence, **0.75** field floor) below which extraction goes to a person.
- **Tolerance** — the variance allowed before a line fails the match: **± 2% or $25.00, whichever is lower** (default policy).
- **Touchless** — an invoice that went from received to posted with **zero human actions** (no field confirmation, no decision).
- **Exception** — any item needing a person. Types: `extraction_review`, `price_variance`, `qty_mismatch`, `no_po`, `unmatched_line`, `duplicate`, `new_vendor_screen`, `posting_failed`.
- **Short-pay** — paying less than invoiced (to contract/PO price) and notifying the vendor of the held difference.
- **Contract price** — unit price from a vendor agreement on file (`contract_prices`), which overrides the PO unit price when active on the invoice date.
- **GRN** — goods receipt note: what was physically received, per PO line.
- **Entity** — a legal company in the org, mapped to one ERP company/subsidiary. **Location** — a site (restaurant, commissary) belonging to one entity.

## 3. Core flows

### 3.1 Happy path (touchless)
1. Document arrives on a channel → stored, hashed, deduplicated by file hash.
2. Extraction → all fields ≥ gate → invoice created.
3. Enrichment → vendor resolved, PO linked, GL predicted per line, entity/location assigned.
4. Screening → no duplicate, no fraud signal.
5. Match → every line within tolerance, quantities ≤ received.
6. Posting → ERP bill created with entity + location + GL per line.
7. Run closes as `touchless = true`. Appears in "Recent runs" with status `Touchless`.

### 3.2 Extraction review
Document confidence < 0.90 **or** any required field < 0.75 → exception `extraction_review`. A person confirms or edits flagged fields (design screen 02). On confirm the run resumes at enrichment. The invoice is no longer touchless.

### 3.3 Price variance
A line's invoiced amount exceeds expected (contract price if active, else PO price) by more than the tolerance → exception `price_variance` with a recommendation (design screen 03). Decisions: **Short-pay** (pay expected, hold difference, notify vendor), **Approve as-is** (pay invoiced), **Dispute** (hold the whole invoice, notify vendor, exception stays open in `disputed` state).

### 3.4 Quantity mismatch
Invoiced qty > received qty (GRN) or > ordered qty (PO beyond over-receipt allowance, default 0%) → `qty_mismatch`. Decisions: short-pay to received qty, approve as-is, dispute.

### 3.5 No PO / unmatched line
No PO referenced or found → `no_po`. Decisions: link an existing PO (then re-match), approve without PO (manager/controller, requires comment), reject. An invoice line that can't be paired to any PO line → `unmatched_line` (same decisions at line level).

### 3.6 Duplicate
Screening finds a prior invoice with high similarity (design screen 04) → `duplicate`, **payment blocked**. Decisions: **Merge** (keep one as source of truth; the other is marked `duplicate_of` and can never be paid), **Reject the second copy**, **Not a duplicate** (controller only; requires comment).

### 3.7 New vendor / bank-change fraud screen
Signals (bank details differ from W-9/bank on file, vendor record < 14 days old, no PO, remit-to address recently created/changed, amount anomaly) score ≥ 0.70 → `new_vendor_screen`, **held**, routed to controller. Decisions: **Request W-9 re-verification** (keeps hold, sends templated request, sets `awaiting_vendor`), **Release** (controller only, requires comment and a verification checkbox), **Reject invoice**.

### 3.8 Posting failure
ERP write fails after retries → `posting_failed` exception, visible in Exceptions; Slack alert; retry button for manager.

### 3.9 Escalation
Any open exception untouched for **24 hours** (`sla_due_at`) is escalated: `escalated = true`, assigned to controller, Slack DM. Exceptions with impact > **$500.00** notify the controller on creation (do not reassign).

## 4. Business rules (canonical — implement exactly)

### 4.1 Tolerance
```
expected_unit = contract_price(vendor, item, invoice_date) ?? po_line.unit_price
expected_ext  = round(expected_unit × invoiced_qty, 2)
delta         = invoice_line.amount − expected_ext
allowed       = min(policy.pct × expected_ext, policy.abs)        -- 0.02, 25.00
line passes price check  ⇔  |delta| ≤ allowed   (delta < 0 always passes; record as favorable)
```
Worked example (hero case): shrimp, 200 lb, invoiced $4.12/lb = $824.00; contract $3.68/lb → expected $736.00; allowed = min(14.72, 25.00) = 14.72; delta = 88.00 > 14.72 → **fails**. delta_pct = 88/736 = **+11.96% → displayed "+12.0%"**.

Display rules: percentages to one decimal with sign; money always 2 decimals with thousands separators; tabular numerals.

### 4.2 Quantity
```
line passes qty check ⇔ invoiced_qty ≤ grn_received_qty  AND  invoiced_qty ≤ po_qty × (1 + over_receipt_allowance)
```
Service vendors flagged `match_mode = 'two_way'` (e.g., janitorial) skip the GRN check.

### 4.3 Confidence gate
```
doc_confidence = exp( Σ wᵢ · ln(cᵢ) / Σ wᵢ )           -- weighted geometric mean of calibrated field confidences
weights: vendor 3, invoice_number 3, invoice_date 2, total 3, po_ref 2, terms 1, each line qty 1, each line unit_price 1, each line amount 1
gate passes ⇔ doc_confidence ≥ 0.90  AND  min(required field cᵢ) ≥ 0.75  AND  arithmetic checks pass
arithmetic checks: |qty × unit − amount| ≤ 0.01 per line; |Σ amounts + tax + freight − total| ≤ 0.02
```
When an arithmetic check *confirms* a low-confidence value (e.g., the smudged qty: $125.00 ÷ $31.25 = 4.0), show that cross-check in the review UI, but **still require confirmation** — the gate is not auto-overridden.

### 4.4 Duplicate similarity (0–1)
```
if same vendor AND normalized invoice_number equal → 1.00 (hard duplicate)
else score = 0.30·amount_eq + 0.20·date_close + 0.30·line_jaccard + 0.10·number_sim + 0.10·image_sim
  amount_eq   = 1 if |Δtotal| ≤ 0.01 else 0
  date_close  = max(0, 1 − |Δdays|/7)
  line_jaccard= Jaccard over (normalized description, qty, amount) tuples
  number_sim  = trigram similarity of normalized invoice numbers
  image_sim   = 1 − (pHash Hamming distance / 64) for image/PDF first page
hold ⇔ score ≥ 0.90 ; suggest (no hold) ⇔ 0.75 ≤ score < 0.90
```
Identical SHA-256 → not a duplicate invoice, a **re-delivery**: dropped at intake, logged in `pipeline_events`, no exception.

### 4.5 Fraud screen (0–1)
```
signals (weights): bank_mismatch_w9 0.50 · vendor_age_lt_14d 0.20 · no_po 0.10 · remit_address_new 0.10 · amount_anomaly(z>3 vs vendor history) 0.10
score = min(1, Σ weights of present signals)  → hold ⇔ score ≥ 0.70
```
Hero case NV-0001: bank_mismatch 0.50 + vendor_age 0.20 + no_po 0.10 + remit_new 0.10 = 0.90 → held. (Design copy says "conf 0.89"; the implemented score will read 0.90 — acceptable; the UI label is "Signal score".)

### 4.6 Recommendation (deterministic, auditable)
For `price_variance` where a contract price is active and GRN confirms full receipt → recommend **short_pay** to expected; confidence = 0.80 + 0.07 × min(2, count of prior short-pays accepted by this vendor in 90 days), capped at 0.95 (hero case: 2 prior accepted → 0.94). Reason bullets are generated from templates with the concrete numbers (see `06` §8). No LLM prose in recommendations.

### 4.7 Approval authority
- Impact = amount at risk (hold amount, or full invoice for duplicates/fraud/no-PO).
- `ap_manager` may decide impact ≤ $5,000.00; above → controller.
- Fraud holds → controller only.
- All decisions require the actor to be different from any user who edited monetary fields on the invoice.

## 5. KPI definitions (the only allowed sources for the numbers on screen)

All computed per org, per period, in the org's timezone. Implemented as SQL views in `05-database.md` §9.

| KPI | Definition | Screen |
|---|---|---|
| Received today | count of runs with `received_at` today | Pipeline bar 1 |
| Extracted above gate | runs today whose extraction event passed the gate without review | bar 2 |
| Enriched, PO linked | runs today with a linked PO after enrichment | bar 3 |
| Matched clean → ERP | runs today with match verdict `clean` | bar 4 |
| Routed to people | runs today with ≥ 1 exception created | bar 5 |
| Cost per invoice | (Σ llm_cost + Σ ocr_cost + infra_alloc + Σ human_minutes × loaded_rate) ÷ invoices processed, period | Operations |
| Touchless rate | posted invoices with `touchless` ÷ all posted invoices, period | Operations |
| Median cycle | median(`posted_at − received_at`) for posted invoices, period | Operations |
| Held back this quarter | Σ held amounts on short-pays + Σ totals of duplicates blocked + Σ rejected fraud invoices, quarter to date | Operations |
| Field accuracy (sampled) | from the eval harness: correct fields ÷ labeled fields in the weekly sample | Extraction, Operations chart |
| Median extraction | median extraction stage duration today | Pipeline, Extraction |
| Avg decision time | mean(`decided_at − opened_at`) for exceptions decided today | Exceptions |

- `infra_alloc` = monthly infra cost from config (`org_settings.infra_monthly_usd`, default 55.00) × (invoices this period ÷ invoices this month), so it's apportioned, not guessed per call.
- `human_minutes` = sum of time from opening an exception/review to decision, capped at 30 min per item, from UI telemetry events.
- `loaded_rate` = `org_settings.loaded_hourly_rate_usd`, default **35.00**, shown as an assumption.
- The manual benchmark "$12–30" is a constant string with a citation label ("industry benchmark for manual processing"). Don't compute it.
