# 03 — Screens

Routes are under `/o/[orgSlug]/…`. All authenticated screens use the shell in `02` §5. Numbers shown below are the **design's sample values** — in the product every one is bound to live data (the binding is given in brackets). Copy is exact unless marked as data.

---

## 1. Shell behaviors (all screens)
- Rail navigation changes route; active item follows route.
- Top-bar search opens the command palette.
- Realtime: each screen subscribes to Supabase Realtime channels listed per screen; on event, refetch the affected query (debounced 500ms).
- Role gating: actions a role can't perform render disabled with tooltip "Needs AP manager" / "Needs controller" / "Read-only access".

---

## 2. Pipeline — `/o/[org]/pipeline` (design: `01-pipeline.png`)

**Purpose:** live view of today's flow through every stage; drill into any run.

### Layout (inside main column, below top bar)
1. **Attrition ledger** — full width, padding 18px 24px 20px, 2px bottom rule.
   - Header row: left section label `Today · volume through the pipeline`; right meta `orchestrated with n8n + LLM extraction layer · retries and dead-letter on every node`.
   - `.attrition` bars (margin-top 14px): 214 / 209 / 198 / 152 / **41** [KPIs in `01` §5]. Labels: `received`, `extracted above gate`, `enriched, PO linked`, `matched clean → ERP`, `routed to people` (accent-700).
2. **Body** — flex row: left column (flex 1) + **Run inspector** (392px, 2px left rule).
   - Left column = **stage grid** (`.stage-col` ×5, 2px bottom rule) + **Recent runs** table.
   - Stage columns (header text exact; rows are label/value):
     - `01 Intake`: Email PDFs 126 · Photo OCR 38 · Vendor portals 29 · EDI 810 21 [counts by `documents.channel` today]. Footnote: `IMAP polled every 60s · portal scrapes on schedule · every file hashed and stored before parsing.` → **update copy for real system**: `SES inbound · portal sync hourly · every file hashed and stored before parsing.`
     - `02 Extraction`: Auto-passed 209 · **Below gate → review 5** (risk row) · Median time 11.8s. Paragraph: `Confidence gate at 0.90. Every field carries a score; anything under the gate goes to a person before it moves.` [gate from `org_settings`]. Footnote: `model extraction-v14 · prompt p-38` [bind to deployed `EXTRACTION_MODEL_TAG` and `PROMPT_VERSION`].
     - `03 Enrichment`: Vendor resolved 214 · PO linked 198 · GL predicted 214 · Duplicate screen 214. Footnote: `Entity and location coding applied here, so the ERP write needs no manual touch.`
     - `04 Three-way match`: Clean 152 · **Price variance 24** (risk) · Quantity mismatch 9 · No PO found 8. Footnote: `Tolerance: auto-approve within ±2% or $25, whichever is lower.` [from `tolerance_policies`].
     - `05 Approve + post`: **Awaiting a person 41** (risk) · Posted · QuickBooks 104 · Posted · NetSuite 48 · Slack digest `09:30 sent`. Footnote: `Nothing posts without entity + location + GL coding attached.`
   - **Recent runs** (padding 16px 18px 0): header `Recent runs` / meta `Last 9 of 214 today · newest first`. Table columns: Time · Vendor · Invoice · Location · Amount (right) · Stage · Status. Status text for exceptions in `accent-800` 600 (e.g., `Price variance`, `Below gate`, `No PO found`); touchless rows `Touchless`. Show as many rows as fit (design: 9). Row click → selects run in inspector.
   - **Run inspector**:
     - Header row: `Run inspector` / `run 88,412` [run number].
     - Summary block (16px 20px, 1px bottom rule): vendor (16px 800) · `BD-104882 · $1,982.47 · Bayside` · chips `Touchless` (ink) and `16s end to end` (neutral).
     - Timeline rows (12px padding, 1px rules): time column 62px (12px 800) + text (`Received — email PDF, 2 pages` / sub `ap@<inbox> · SHA-256 stored`; `Extracted — 14 line items, conf 0.97` / `every field above the 0.90 gate`; `Matched — PO-BS-2041, GRN-BS-5518` / `14 of 14 lines within tolerance`; `Posted — QuickBooks, JE 18,240` / `Entity 2 · loc BS · GL 5000 COGS-Food`). [from `pipeline_events`.] For non-touchless runs, add rows for exception opened / decision by <actor>.
     - Footer (2px top rule): `No person opened this invoice. The 41 that needed one are in the exception queue.` For non-touchless runs: `<N> people touched this invoice.` with link to the exception.
- **Default selection:** most recent touchless run.
- **Status bar:** see `02` §5.3.
- **Realtime:** `pipeline_events` inserts for the org.

---

## 3. Extraction review — `/o/[org]/extraction` and `/o/[org]/extraction/[invoiceId]` (design: `02-extraction.png`)

**Purpose:** a person confirms or corrects fields the model wasn't sure about.

- Top bar: title `Extraction review`; context `5 of 214 documents need a person today` [queue count / received today].
- **Stats row** (4 equal cells, 1px rules, 2px bottom rule, padding 14px 24px): `Field accuracy, sampled` 96.4% [eval, latest week] · `Auto-passed today` 209 / 214 · `Median extraction` 11.8s · `Queue position` 3 of 5 + prev/next square buttons (30×30, 1px border).
- **Body:** source pane (600px, `neutral-200` ground, 2px right rule) + fields pane (flex 1, padding 18px 24px).
  - Source pane: header (12px 20px, 1px bottom rule, field-label style): `Source · dock photo` / `IMG_4187 · Riverside · 09:12:44` [document meta]. Center: the **actual document image** (rendered page from storage) inside `.grayscale`, with `.flag-region` overlays for fields below 0.75 at their bbox. Footer (12px 20px, 1px top rule): `Skew corrected +2.0°, perspective normalized. The outlined region is the field awaiting confirmation.` [bind skew value from preprocessing]. Zoom: scroll to zoom, drag to pan; clicking a field in the right pane scrolls/zooms to its bbox.
  - Fields pane:
    - Header: section label `Extracted fields` / right `Document confidence 0.88 — below the 0.90 gate` (accent-700).
    - Header-field grid: 5 cells, 1px border & rules, padding 10px 12px: Vendor `Produce Supplier` conf 0.99 · Invoice `PR-2214` 0.98 · Date · terms `Jul 12 · Net 14` 0.97 · PO reference `PO-RS-1866` `0.96 · exists` · Total `$491.60` `0.99 · sums`. Each value is click-to-edit (inline `.input`).
    - Line table (margin-top 18px): Line item · Qty · Unit · Extended · Conf (numbers right). Low-confidence row = risk row with chip `Qty unclear` (riskOutline) and value `4 ?` + conf `0.71` in accent-800 700.
    - **RiskCallout** (margin-top 18px): title `One field needs confirmation — quantity, line 2`; body `Model read 4 at confidence 0.71. Cross-check: $125.00 ÷ $31.25 unit = 4.0, so the arithmetic agrees with the smudged digit.` [templated from the flagged field + arithmetic check]; actions `Confirm 4 × $31.25` (ink) and `Edit value` (outline). If multiple fields: title `<n> fields need confirmation`, one row per field, and a single `Confirm all` button.
    - Footer (1px top rule, pinned bottom): `On confirm: re-scored, enriched, then matched against PO-RS-1866` / `Every correction is logged with actor and timestamp`.
- **Behavior:** Confirm → server action `confirmExtraction` → writes `invoice_fields` (source `human`), audit entries, closes the `extraction_review` exception, resumes n8n; toast; auto-advance to next queue item. Edit → inline input with validation (numeric > 0, 2 decimals for money); Enter saves; arithmetic re-checked live.
- `/extraction` with no id redirects to the oldest queue item; empty queue → EmptyState `Queue clear` / `Every document today passed the confidence gate.`
- **Realtime:** `exceptions` where type = extraction_review.

---

## 4. Three-way match — `/o/[org]/match/[invoiceId]` (design: `03-three-way-match.png`)

**Purpose:** see the line-level verdict for one invoice and decide.

- Top bar: title `Three-way match`; context `PS-88214 · Protein Supplier · Riverside`; risk chip with the verdict (`Price variance`). No search field on this screen in the design — keep search (it fits) but it may be hidden below 1440px.
- **Document trio row** (grid `repeat(3,1fr) 460px`, 2px bottom rule; cells 14px 24px, 1px rules):
  - `Invoice` → `PS-88214 · $2,847.60` (17px 800) / `Email PDF, Jul 13 09:41 · extraction conf 0.98`
  - `Purchase order` → `PO-RS-1873 · $2,759.60` / `QuickBooks · contract pricing applied`
  - `Goods receipt` → `GRN-RS-4410 · in full` / `Receiving app, Jul 12 18:22`
  - Difference cell (accent-100 fill): label `Difference to purchase order` (accent-800) / `+$88.00` (30px 800 accent) / right `one line of five / exceeds tolerance` (11.5px accent-900).
- **Body:** comparison (flex 1, padding 18px 24px) + decision rail (400px, 2px left rule).
  - Header: `Line-level comparison` / `Auto-approve within ±2% or $25, whichever is lower`.
  - Table: Line item · Invoice · Purchase order · Receipt · Verdict (210px). Cells show `unit · qty` on line 1 and extended on line 2. Failing line = risk row: invoice unit in accent-800 bold; verdict chip `Price variance` (risk) + `+12.0% · $88.00 impact` (accent-800 600). Matched lines: `Matched`, optional sub `quantity verified against receipt`. Totals row (heading font 800): `$2,847.60` · `$2,759.60` · `all received` · `Δ $88.00` (accent-800). 2px rule above totals.
  - Tolerance strip (1px border, 12px 16px): label `Tolerance` · `Line 1 is +12.0% against a ±2% limit and $88.00 against a $25 limit — it fails both, so the invoice holds for approval.` · right `4 of 5 lines auto-verified`. [Templated. When only one limit applies the sentence says which.]
  - Provenance (pinned bottom, 1px top rule, 11px): `Provenance — invoice values from extraction-v14 (conf 0.98); purchase order from QuickBooks; receipt from the receiving app. Contract price of $3.68/lb comes from the vendor agreement on file, clause 4.2, in effect through Sep 2026.` The contract name is a link opening the contract PDF.
  - **Decision rail:** header `Recommended action`; block: `Short-pay to contract price` (20px 800) · `Pay $2,759.60, hold $88.00` (15px; hold in accent-800) · `Recommendation confidence 0.94, from contract terms and payment history`. Reason list (1px rules, 12px): the four templated bullets (`06` §8). Footer (2px top rule): `Short-pay $2,759.60 and notify vendor` (ink, full width), then `Approve as-is` + `Dispute` (outline, equal halves), then note `The decision posts to QuickBooks and is written to the audit log with actor and timestamp. Impacts above $500 also notify the controller.`
- **Behavior:** buttons call `decideException`. `Approve as-is` opens a Dialog showing the full amount and requiring a comment. After decision: toast, chips update, rail replaced by a "Decision" summary (actor, time, action, amount, ERP reference), buttons removed.
- Invoices that matched clean also render here (verdict chip `Matched`, no decision rail — show "Posted" summary instead).

---

## 5. Exceptions — `/o/[org]/exceptions` and `/o/[org]/exceptions/[id]` (design: `04-exceptions.png`)

**Purpose:** triage queue + detail for duplicates, fraud, and everything else.

- Top bar: title `Exceptions`; context `14 open · 41 raised today · 38 cleared`.
- **Body:** queue (412px, 2px right rule) + detail (flex 1).
- **Queue:** header `Queue` / `Oldest first` (sort toggle: Oldest first / Largest impact). Groups (header rows: `neutral-200` fill, 8px 20px, 11.5px 800 0.04em; risk groups — duplicates, new vendor — use accent-100 fill + accent-800 text): `Price variance 7`, `No purchase order 4`, `Suspected duplicate 2`, `New vendor screen 1` (+ `Quantity mismatch`, `Unmatched line`, `Posting failed`, `Extraction review` when non-empty). Items (11px 20px, 1px rules): line 1 vendor · invoice number (bold if selected) + amount right; line 2 `Location · age · reason` (11px `neutral-700`). Show 3 per group then `<n> more` (click expands). Selected item: 3px accent left rule + `neutral-100` fill. Footer: `Anything untouched for 24 hours escalates to the controller.`
- **Detail — duplicate (designed):**
  - Heading row (16px 24px, 1px bottom rule): `Produce Supplier · PR-2201` (18px 800) · risk chip `Duplicate · similarity 0.96` · right `Payment blocked while held`.
  - Copy cards (2 columns, gap 18px, 18px 24px, 1px border each, 14px 16px): header `Copy A · emailed PDF` / `Jul 11 08:02`; thumbnail (52×66, 1px neutral-400 border; real page thumbnail) + meta (`billing@<vendor domain>` / `Invoice date Jul 10 · $612.40` / `SHA-256 …a41f · extraction 0.98`). Copy B: `Copy B · dock photo`, `Uploaded by Riverside receiving`.
  - Evidence strip (5 cells under the cards, 1px border, no top border): Invoice no. `Exact match` · Amount `Exact match` · Invoice date `Exact match` · Line items `5 of 5 overlap` · File `Differs · image sim 0.83` (accent-800). [from `duplicate_candidates.evidence`]
  - Actions: `Merge, keep the PDF as source` (ink) · `Reject the second copy` (outline) · right note `Merging blocks the second payment permanently`.
  - **Fraud callout** (RiskCallout, margin 18px 24px 0) when the org has an open new-vendor screen: title `New vendor screen — Unlisted Supplier, first invoice, $2,214.85` + chip `Held` + right `Routed to the controller`; signals row: `Bank details differ from the W-9 on file` · `No purchase order` · `Vendor record 4 days old` · `Signals: rules plus anomaly model, conf 0.89` (→ implement label as `Signal score 0.90`). Clicking it opens that exception's detail.
  - Audit trail (pinned bottom, 2px top rule): label `Audit trail · PR-2201 · append-only`; single-line chronological summary joined with ` · ` [from `audit_log`]; `View full trail` link → invoice detail.
- **Detail — other types (derived):** price/qty variance → compact version of the Match screen's table + decision rail, with a link `Open full match`; no PO → PO search/link control (combobox of open POs for vendor+location) + actions; new vendor → the fraud callout expanded with vendor record comparison table (on file vs. on invoice: legal name, tax ID last 4, bank routing/account last 4, remit address, created date) + actions `Request W-9 re-verification`, `Release hold` (controller, Dialog with comment + checkbox "I verified the bank details with the vendor by phone"), `Reject invoice`; posting failed → error message, ERP response excerpt, `Retry posting`.
- Status bar per `02` §5.3.
- **Realtime:** `exceptions`, `approvals` for the org.

---

## 6. Operations — `/o/[org]/operations` (design: `05-operations.png`)

**Purpose:** the controller's view — money, rates, trends, sync health.

- Top bar: title `Operations`; context `July 2026, month to date · 3,120 invoices · 34 locations · 3 entities` [period selector: click context → menu: Month to date, Quarter to date, Last 30 days, Custom]; avatar `TI` in design.
- **Disclosure bar** (10px 24px, `neutral-200` fill, 2px bottom rule): chip `Computed` (1px ink border) + text. **Copy changes from the design** because figures are now real: for demo orgs — `These figures are computed from pipeline runs over the synthetic demo corpus, not a client account. The manual comparison ($12–30 per invoice) is a published industry benchmark for hand-keyed accounts payable, not a figure produced by this system.` For non-demo orgs, show only the benchmark sentence. (The design's chip read `Modeled` — replace with `Computed`.)
- **Headline metrics** (4 MetricCells, 2px bottom rule): `Cost per invoice` $3.10 / `Industry benchmark for manual: $12–30` (info icon → popover with formula and current loaded-rate assumption) · `Touchless rate` 71% / `Up from 54% at dataset start` [first-week value] · `Median cycle` 24h / `Receipt to posted` · `Held back this quarter` (accent-800 label) `$6,084` (accent) / `$4,860 variances · $1,224 duplicates`.
- **Body grid** `490px 1fr 400px`:
  - `Largest catches this quarter`: 3 rows (amount 16px 800 accent-700, right-aligned in 78px; text 12.5px) [top 3 by held amount]; footer (2px top rule): `61 short-pays accepted` · `9m average decision time` · `100% decisions logged` [the last one = share of decisions with an audit entry — must be 100%; if not, show in accent].
  - `By location` / `Top 8 of 34 · volume and exception rate`: rows grid `104px 1fr 46px 56px`: name · 11px bar (track neutral-300, fill neutral-700; top row fill ink) · volume · exception rate (top/over-threshold in accent-800 700 when > 2× org median). Footnote: an automatic note for the highest-exception location — derive from data: if that location has vendors without contract prices, `"<Location> runs high because <n> suppliers there have no contract pricing on file."`; otherwise `"<Location> has the highest exception rate this period."`.
  - `Extraction accuracy · 12 weeks`: SparkLine (352×140), floor at 95.0%, version markers from `prompt_versions.deployed_at`, labels `wk 1 · x%` / `wk 12 · y%`; note `Sampled weekly against hand-keyed values from the demo dataset.` (non-demo: `…against human-verified corrections.`). ERP sync block: `QuickBooks 2,118 · 09:41:23`, `NetSuite 1,002 · 09:38:51`, note `Every posted invoice carries entity, location and GL coding.`
- **Realtime:** refresh every 60s (materialized views) — see `05` §9.

---

## 7. Derived screens (not designed — build strictly in the system)

### 7.1 Login — `/login`
Split: left 50% ink (`--color-text`) panel with the wordmark (bg-colored bars, **red middle bar**) at 58px and one sentence `Accounts-payable automation for multi-location operators.` in bg color 20px; right 50% ground with form: section label `Sign in`, `.input` email, `Send sign-in link` (ink button), 12px note `We'll email you a one-time link.` For the public demo: a second block below a 2px rule: `Explore the demo` / `Read-only access to a synthetic tenant.` / button `Open the demo` (signs in as the demo viewer via a server action — no password shown). Mobile: stacked, ink panel 180px tall.

### 7.2 Invoices — `/o/[org]/invoices` and `/o/[org]/invoices/[id]`
List: filter bar (status seg control: All · Touchless · Exceptions · Posted · Held; vendor, location, date range), DataTable (Received, Vendor, Invoice, Location, Entity, Amount, Status, Posted to). Detail: header like Match trio, tabs (seg control): `Lines` (the match table), `Document` (source viewer), `Timeline` (run events), `Audit` (full audit trail table: Time, Actor, Action, Before → After, Hash (first 8 chars, mono), with a `Verify chain` button that calls the verify endpoint and shows `Chain verified · <n> entries` or the first broken link in accent).

### 7.3 Vendors — `/o/[org]/vendors` and `/[id]`
List table: Vendor, Category, Match mode, Contract on file (yes/no), Invoices (90d), Exception rate. Detail: vendor master fields (with bank details masked to last 4 and a `Bank change requests` list), contracts table (effective dates, clause refs, open PDF), contract price table (item, UoM, unit price, clause), recent invoices.

### 7.4 Settings — `/o/[org]/settings/{policy|approvals|integrations|team|org}`
Left sub-nav (list with 1px rules, active = ink left rule 3px). Policy: tolerance pct & abs inputs, over-receipt allowance, confidence gate and field floor, duplicate thresholds — each with a live "Preview on last 30 days" line (e.g., "Would have held 19 instead of 24"). Approvals: manager limit, controller-notify threshold, SLA hours. Integrations: cards (square, 1px border) for QuickBooks, NetSuite, Slack, Email inbox, Vendor portals, EDI — status chip, last sync, Connect/Disconnect (OAuth for QBO/Slack). Team: members table, invite by email, role select. Org: entities & locations tables, timezone, loaded hourly rate and monthly infra cost assumptions (labeled as assumptions used in KPIs).

### 7.5 Capture — `/capture` (mobile-first PWA)
For receiving staff photographing paper invoices. Ink top bar 48px with logo; location select (remembered); big `Take photo` button (full width, ink, 56px); file input `accept="image/*" capture="environment"`; preview with crop handles; `Send` (ink) → uploads to storage via signed URL, triggers intake webhook; success state: `Sent · PR-2214 will appear in the pipeline in about a minute.` Min hit target 44px. Works offline-first: queue uploads in IndexedDB and retry.

### 7.6 Mock vendor portal — `/demo/vendor-portal` (demo only, public, no Ledgic chrome)
A deliberately plain supplier-style page (system fonts, no Ledgic styling) with a login form (demo credentials in env) and a table of downloadable invoice PDFs. Exists so the portal-sync connector has something real to log into and scrape. Excluded from `robots.txt`.

### 7.7 States for every screen
- Loading: Skeleton rows in the exact layout.
- Empty: EmptyState in place (e.g., Pipeline before first run today: `No documents yet today` / `The first delivery usually lands around 06:00.`).
- Error: RiskCallout variant using neutral (ink border, no accent) — errors are not "money at risk" — with `Retry`.
- Degraded: if n8n or core health checks fail, status bar shows `Pipeline paused — <reason>` in accent-700 and the running indicator square turns outline-only.
