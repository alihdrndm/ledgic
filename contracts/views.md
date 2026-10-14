# Read-model views (frozen contract)

Owner of implementation: workstream B (migration `0002+`). Consumers: `apps/web/lib/queries/*`,
core (`/v1/runs/{id}`, copilot `get_kpis`), MCP tools.

Rules for every view:
- Plain views: `with (security_invoker = true)` so the caller's RLS applies (`is_member(org_id)`).
- Materialized views (`mv_ops_period`, `mv_location_period`, `mv_eval_weekly`) cannot use RLS, so
  they are **revoked from anon/authenticated** and exposed through wrapper views `v_ops_period`,
  `v_location_period`, `v_eval_weekly` (same columns, `where is_member(org_id)`). The web always
  reads the `v_*` wrappers; core (service role) may read `mv_*` directly. Each MV has a unique
  index for `refresh materialized view concurrently` (pg_cron every minute; core scheduler fallback).
- Every view has an `org_id uuid` column; callers always filter `org_id = $org` explicitly as well.
- "Today" = org-local calendar day: `(ts at time zone orgs.timezone)::date = (now() at time zone orgs.timezone)::date`.
- Money columns are `numeric(12,2)`; percentages are fractions (`0.120`), formatted by the UI.
- Column names below are exact. Types in parentheses. Adding columns later is allowed; renaming/removing is not.

---

## v_pipeline_today — Pipeline attrition bars (01 §5)
One row per org (zeros when no runs today).
| column | type | meaning |
|---|---|---|
| org_id | uuid | |
| day | date | org-local today |
| received | int | runs started today |
| extracted_above_gate | int | runs today whose extraction `succeeded` event has `detail.gate_passed = true` |
| enriched_po_linked | int | runs today whose invoice has `po_id` and status past review |
| matched_clean | int | runs today with `match_results.verdict = 'clean'` |
| routed_to_people | int | runs today whose invoice has ≥ 1 exception |

## v_stage_today — Pipeline stage columns 02–05 (+ status bar)
One row per org.
| column | type |
|---|---|
| org_id | uuid |
| extraction_auto_passed | int — gate passed without review |
| extraction_below_gate | int — `extraction_review` exceptions opened today |
| extraction_median_seconds | numeric(8,1) — median extraction-stage `duration_ms`/1000 today |
| vendor_resolved | int — invoices today with vendor_id |
| po_linked | int |
| gl_predicted | int — invoices today whose every line has gl_account_id |
| duplicate_screened | int — runs today with a screening `succeeded` event |
| match_clean | int |
| match_price_variance | int — exceptions today of type price_variance |
| match_qty_mismatch | int |
| match_no_po | int |
| awaiting_person | int — open exceptions (any day) |
| posted_quickbooks | int — erp_postings posted today, system quickbooks |
| posted_netsuite | int |
| tolerance_pct | numeric(6,5) — current policy |
| tolerance_abs | numeric(12,2) |
| confidence_gate | numeric(4,3) |
| field_floor | numeric(4,3) |

## v_channel_today — Pipeline column 01 Intake
One row per (org, channel) for all 5 channels (zero-filled).
| org_id uuid | channel channel | count int |

## v_recent_runs — Pipeline "Recent runs" table + Invoices list
All runs (not just today); clients `order by started_at desc limit n`.
| column | type |
|---|---|
| org_id | uuid |
| run_id | uuid |
| run_number | bigint |
| started_at | timestamptz |
| finished_at | timestamptz null |
| run_status | text — running/waiting/succeeded/failed/cancelled |
| current_stage | stage |
| invoice_id | uuid null |
| invoice_number | text null |
| vendor_id | uuid null |
| vendor_name | text null — vendors.display_name |
| location_id | uuid null |
| location_name | text null |
| location_code | text null |
| entity_short_code | text null |
| total | numeric(12,2) null |
| invoice_status | invoice_status null |
| channel | channel |
| touchless | boolean null |
| open_exception_id | uuid null — oldest open exception for the invoice |
| open_exception_type | exception_type null |
| status_label | text — UI string: `Touchless`, `Posted`, `Below gate`, `Price variance`, `Quantity mismatch`, `No PO found`, `Unmatched line`, `Duplicate`, `New vendor screen`, `Posting failed`, `Rejected`, `In progress`, `Failed` |
| is_exception | boolean — true when status_label is an exception label (rendered accent) |
| end_to_end_seconds | numeric null — finished_at − started_at |
| erp_system | erp_system null — from erp_postings (posted) |
| erp_external_id | text null |

## v_run_timeline — Run inspector + invoice Timeline tab
One row per pipeline_event.
| column | type |
|---|---|
| org_id | uuid |
| run_id | uuid |
| event_id | bigint |
| at | timestamptz |
| stage | stage |
| status | event_status |
| duration_ms | int null |
| summary | text null — inspector line, e.g. `Received — email PDF, 2 pages` |
| detail | jsonb — includes `sub` (second line text) when the producer sets it |
| actor_name | text null — profiles.full_name when `detail.actor_id` is a user |

## v_review_queue — Extraction review queue
Open `extraction_review` exceptions, oldest first.
| column | type |
|---|---|
| org_id | uuid |
| exception_id | uuid |
| invoice_id | uuid |
| run_id | uuid null |
| queue_position | int — row_number() over (partition by org order by opened_at) |
| queue_size | int |
| opened_at | timestamptz |
| vendor_name | text null |
| invoice_number | text null |
| location_name | text null |
| channel | channel |
| original_filename | text null |
| doc_confidence | numeric(4,3) |
| flagged_count | int — latest-version fields + line cells below field_floor |

## v_invoice_detail — header for Extraction / Match / Invoice detail
One row per invoice.
| column | type |
|---|---|
| org_id, invoice_id, document_id | uuid |
| invoice_number, terms, currency | text |
| invoice_date, due_date | date |
| subtotal, tax, freight, total | numeric(12,2) |
| status | invoice_status |
| doc_confidence | numeric(4,3) |
| gate_passed, touchless | boolean |
| human_touches | int |
| extraction_mode | text — live/recorded/simulated |
| received_at, posted_at | timestamptz |
| duplicate_of | uuid null |
| vendor_id, vendor_name, vendor_legal_name, vendor_category | |
| entity_id, entity_name, entity_short_code | |
| location_id, location_name, location_code | |
| po_id, po_number, po_total, po_source | |
| grn_numbers | text[] — GRNs on the PO |
| grn_received_at | timestamptz null — latest |
| grn_in_full | boolean null — every PO line fully received |
| channel | channel |
| storage_path, original_filename, mime | text |
| page_count | int |
| preprocessing | jsonb — `{skew_deg, perspective, pages[]}` |
| source_meta | jsonb |
| run_id | uuid null — latest run |
| run_number | bigint null |
| workflow_version | text null |
| fields | jsonb — latest version per field: `{field: {value, confidence, raw_confidence, bbox, source, version, set_by, set_at}}` |
| lines | jsonb — array ordered by line_no: `{id, line_no, description, qty, uom, unit_price, amount, confidences, bboxes, gl_number, gl_name, gl_confidence, po_line_id}` |
| erp_system, erp_external_id, erp_status | from erp_postings |

## v_match_detail — Three-way match
One row per **invoice line** (join match_line_results), plus header columns repeated.
| column | type |
|---|---|
| org_id, invoice_id, match_result_id | uuid |
| verdict | invoice_verdict |
| tolerance_pct | numeric(6,5) |
| tolerance_abs | numeric(12,2) |
| expected_total, total_delta | numeric(12,2) |
| lines_verified, lines_total, duration_ms | int |
| computed_at | timestamptz |
| invoice_line_id | uuid |
| line_no | int |
| description, uom | text |
| inv_qty | numeric(12,3) |
| inv_unit_price | numeric(12,4) |
| inv_amount | numeric(12,2) |
| po_line_id | uuid null |
| po_qty | numeric(12,3) null |
| po_unit_price | numeric(12,4) null |
| po_amount | numeric(12,2) null |
| grn_qty | numeric(12,3) null |
| expected_unit_price | numeric(12,4) null |
| expected_source | text null — contract/po |
| expected_amount, delta_amount, allowed_amount | numeric(12,2) null |
| delta_pct | numeric(8,5) null |
| line_verdict | line_verdict |
| note | text null |
| contract_id | uuid null |
| contract_title | text null |
| contract_document_path | text null |
| contract_effective_to | date null |
| clause_ref | text null |
| exception_id | uuid null — open/most-recent exception for the invoice |
| recommendation | jsonb null — `{action, pay_amount, hold_amount, confidence, reasons}` |
| decision | jsonb null — latest approval `{approval_id, action, actor_id, actor_name, decided_at, pay_amount, hold_amount, comment}` |

## exceptions_public / v_exception_queue — Exceptions queue + detail
`exceptions_public` = all columns of `exceptions` (no secret columns remain; kept as the only web read path).
`v_exception_queue` one row per exception (open and closed; UI filters `status <> 'resolved'`).
| column | type |
|---|---|
| org_id, exception_id, invoice_id | uuid |
| run_id | uuid null |
| type | exception_type |
| group_label | text — `Price variance`, `Quantity mismatch`, `No purchase order`, `Unmatched line`, `Suspected duplicate`, `New vendor screen`, `Posting failed`, `Extraction review` |
| is_risk_group | boolean — duplicate / new_vendor_screen |
| status | exception_status |
| amount_at_risk | numeric(12,2) |
| reason | text |
| assigned_role | member_role |
| assigned_to | uuid null |
| assigned_to_name | text null |
| escalated | boolean |
| opened_at, sla_due_at, first_viewed_at, resolved_at | timestamptz |
| age_seconds | int — now() − opened_at |
| vendor_id, vendor_name | |
| invoice_number | text |
| invoice_total | numeric(12,2) |
| location_name | text |
| payment_blocked | boolean — type in (duplicate, new_vendor_screen) and status <> resolved |
| similarity | numeric(4,3) null — max duplicate_candidates.similarity |
| duplicate_evidence | jsonb null — evidence of the top candidate + `candidate_invoice_id` |
| signal_score | numeric(4,3) null — `least(1, Σ fraud_signals.weight)` |
| signals | jsonb null — `[{signal, weight, detail}]` |
| recommendation | jsonb null |
| latest_decision | jsonb null — same shape as v_match_detail.decision |
| has_draft | boolean — exception_drafts exist |

Header counts (Exceptions top bar `14 open · 41 raised today · 38 cleared`) and status bar come from **v_status_bar**.

## v_ops_period (wrapper of mv_ops_period) — Operations headline + catches footer
One row per (org, period_key ∈ `mtd`, `qtd`, `l30`). Refreshed every minute (pg_cron, else core scheduler).
| column | type |
|---|---|
| org_id | uuid |
| period_key | text |
| period_start, period_end | date |
| invoices | int — invoices received in period |
| locations, entities | int |
| cost_llm, cost_ocr, cost_infra, cost_human, cost_total | numeric(12,2) |
| cost_per_invoice | numeric(12,4) |
| touchless_rate | numeric(5,4) |
| touchless_rate_first_week | numeric(5,4) null — "Up from 54% at dataset start" |
| median_cycle_seconds | numeric |
| held_variances | numeric(12,2) — Σ approvals.hold_amount for short_pay |
| held_duplicates | numeric(12,2) |
| held_fraud | numeric(12,2) |
| held_total | numeric(12,2) |
| short_pays_accepted | int |
| avg_decision_seconds | numeric |
| decisions_logged_pct | numeric(5,4) — approvals with matching audit row ÷ approvals |
| top_catches | jsonb — top 3 `[{exception_id, invoice_number, vendor_name, amount, text}]` |
| erp_sync | jsonb — `[{system, posted_count, last_posted_at, failing boolean, mock boolean}]` |
| refreshed_at | timestamptz |

## v_location_period (wrapper of mv_location_period) — Operations "By location"
One row per (org, period_key, location).
| org_id uuid | period_key text | location_id uuid | location_name text | location_code text | volume int | exception_rate numeric(5,4) | rank int (by volume) | locations_total int | org_median_exception_rate numeric(5,4) | vendors_without_contract int |

## v_eval_weekly (wrapper of mv_eval_weekly) — Operations sparkline, Extraction "Field accuracy"
One row per (org, week_start), last 12 weeks.
| org_id uuid | week_start date | week_index int (1..12, oldest = 1) | accuracy numeric(6,4) | sample_size int | prompt_version text | prompt_deployed_at timestamptz null — set when a prompt version was deployed that week (version marker) |

## v_ai_budget_today — status / copilot budget notice (global, not org-scoped; readable by any authenticated user)
| day date (UTC) | cap_usd numeric | reserved_usd numeric | spent_usd numeric | remaining_usd numeric | exhausted boolean |

## v_status_bar — status bar on every screen (02 §5.3) + Exceptions header
One row per org.
| column | type |
|---|---|
| org_id | uuid |
| last_run_at | timestamptz null |
| runs_today | int |
| dead_letters_open | int |
| workflow_version | text — of the latest run |
| review_queue_size | int |
| exceptions_open | int — status not in (resolved) |
| exceptions_raised_today | int |
| exceptions_cleared_today | int |
| payments_blocked | int |
| avg_decision_seconds_today | numeric null |
| last_autosave_at | timestamptz null — latest human invoice_fields.set_at |
| erp_failing | jsonb — `[system]` with an open posting_failed exception or last posting failed |
| mv_refreshed_at | timestamptz null |
| pipeline_paused_reason | text null — non-null when no run advanced in 15 min while runnable runs exist |

---

## Implementation notes (workstream B, migration 0004) — additive clarifications
- **Scope of KPI MVs**: `mv_ops_period` / `mv_location_period` count only invoices that have a `pipeline_runs`
  row (processed by Ledgic). Seeded GL back-history invoices (no run, `documents.source_meta.history = true`)
  never inflate operational figures.
- **Costs**: `cost_llm/cost_ocr` = Σ `cost_ledger` by kind in period; `cost_infra` = Σ `cost_ledger` kind `infra`
  + `org_settings.infra_monthly_usd × period_days / days_in_current_month` (apportioned by days);
  `cost_human` = Σ `approvals.time_spent_seconds` / 3600 × `loaded_hourly_rate_usd` (cost_ledger kind `human`
  is **not** read — do not write human costs there). `cost_per_invoice = cost_total / invoices`.
- `held_duplicates` = Σ `exceptions.amount_at_risk` of `merge`/`reject_copy` approvals; `held_fraud` = Σ
  amount_at_risk of `reject_invoice` approvals on `new_vendor_screen`; `avg_decision_seconds` = mean
  `decided_at − exceptions.opened_at`; `decisions_logged_pct` = approvals with an `audit_log` row
  (`entity_type='approval'`, `entity_id=approval id`) ÷ approvals (null when none).
- `top_catches[].text` = `Short-paid · <reason>` / `Duplicate payment blocked · <reason>` /
  `New-vendor invoice rejected · <reason>`. `erp_sync` lists systems of the org's entities (enum order).
- MVs refresh every minute via pg_cron job `ledgic-refresh-kpis` (`select refresh_kpis()`); the wrappers also
  return all rows to service-side callers (service role / direct DB connection).
- `v_recent_runs.status_label` `Failed` also covers `cancelled` runs; `is_exception` is true for the exception
  labels and `Failed`.
- `v_status_bar.last_autosave_at` = latest `confirm_fields` approval (same instant as the human field rows);
  `erp_failing` = systems with an open `posting_failed` exception or a `failed` posting on an invoice still in
  `posting`; `pipeline_paused_reason` = `No run advanced in 15 minutes` when a run has been runnable > 15 min
  and no event was written in 15 min.
- `v_review_queue.flagged_count` ignores fields whose latest value is null.

### Added views
- **v_org_today** `(org_id, timezone, day, t0, t1)` — org-local today and its `[t0, t1)` timestamptz bounds.
- **v_kpi_periods** `(org_id, timezone, period_key, period_start, period_end, ts0, ts1, days, month_days)`.
- **v_invoice_audit** — audit rows that concern one invoice (entity `invoice` itself, or any row whose
  `after.invoice_id` names it). Columns: `org_id, invoice_key text, audit_id bigint, at, actor_type, actor_id,
  actor_name, action, entity_type, entity_id, before, after, prev_hash, hash`. Filter
  `invoice_key = '<invoice uuid>'` (indexed) and order by `audit_id`.
