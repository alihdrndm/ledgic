# Database RPCs (frozen contract)

Owner of implementation: workstream B (migrations `0002+`, pgTAP in `supabase/tests`).
Callers: web server actions (`supabase.rpc(...)` with the user's session), core / MCP / replay
(acting **as a user**: `set local role authenticated; select set_config('request.jwt.claims', '{"sub":"<uuid>","role":"authenticated"}', true)` inside the transaction), so role limits and
segregation of duties live only in the database.

All user-facing RPCs are `security definer`, `set search_path = ''`, fully schema-qualified, and
`grant execute ... to authenticated` (plus `service_role`). Budget / rate-limit RPCs are granted to
`service_role` only (core calls them) unless noted.

## Error convention
Errors are raised with a fixed SQLSTATE and a message that starts with a stable code prefix:

| SQLSTATE | Prefix | Meaning | HTTP mapping (core/web) |
|---|---|---|---|
| `42501` | `LEDGIC_FORBIDDEN:` | role / limit / SoD violation. Message after the prefix is UI copy, e.g. `LEDGIC_FORBIDDEN: Needs controller`, `LEDGIC_FORBIDDEN: Needs AP manager`, `LEDGIC_FORBIDDEN: Read-only access`, `LEDGIC_FORBIDDEN: Above your approval limit of $5,000.00`, `LEDGIC_FORBIDDEN: You edited this invoice's amounts, so someone else must approve it`, `LEDGIC_FORBIDDEN: You created this vendor record` | 403 |
| `P0002` | `LEDGIC_NOT_FOUND:` | entity missing or not in caller's org | 404 |
| `P0001` | `LEDGIC_CONFLICT:` | exception already resolved / invoice not in reviewable state | 409 |
| `22023` | `LEDGIC_INVALID:` | bad input: action not valid for exception type, missing comment, amounts inconsistent, bad field value | 422 |

Clients parse `error.message.split(':')[0]`.

Roles ranking: `viewer < ap_clerk < ap_manager < controller`; `admin` counts as controller.

---

## rpc_confirm_fields(p_invoice_id uuid, p_fields jsonb, p_time_spent int default null) returns jsonb
Extraction review confirm/correct.
- `p_fields`: array of `{"field": "<header field>", "value": "<string>"}` or
  `{"line_id": "<uuid>", "key": "qty|unit_price|amount|description|uom", "value": "<string>"}`.
  Confirming without change = send the current value. Money/qty values are decimal strings.
- Checks: caller role ≥ `ap_clerk` in invoice's org; an `open` `extraction_review` exception exists
  for the invoice (else `LEDGIC_CONFLICT`); numeric values parse and are > 0 (else `LEDGIC_INVALID`).
- Effects (one transaction):
  - header field → new `invoice_fields` row with `version = max+1`, `source='human'`, `confidence=1.000`,
    `set_by=auth.uid()`; mirrors value into the `invoices` column (invoice_number, invoice_date,
    terms, subtotal, tax, freight, total, due_date) when applicable.
  - line cell → updates `invoice_lines.<key>` and sets `confidences.<key> = 1.0`.
  - `audit_log` per changed value: action `field.confirmed` (value unchanged) or `field.corrected`,
    actor_type `user`, entity `invoice_field` / `invoice_line`, before/after `{field, value, confidence}`.
  - invoice: `gate_passed = true`, `human_touches += 1`, `touchless = false`, `status = 'extracted'`.
    Monetary edits (`total, subtotal, tax, freight, qty, unit_price, amount` with a changed value) are
    recorded with `after.monetary = true` — this is what SoD checks look at.
  - exception → `status='resolved'`, `resolved_at=now()`; `approvals` row with
    `action='confirm_fields'`, `time_spent_seconds = least(p_time_spent,1800)`; audit `exception.resolved`.
  - waiting run (`pipeline_runs.wait_exception_id = exception`) → `status='running'`,
    `next_stage='enrichment'`, `next_attempt_at=now()`, `wait_exception_id=null`,
    `context = context || {"decision": {...}}`; `pipeline_events` row (stage `review`, status `resumed`,
    summary `Confirmed by <full_name>`); `pg_notify('ledgic_runs', run_id::text)`.
- Returns `{"approval_id": uuid, "run_id": uuid|null, "changed": int}`.

## rpc_decide_exception(p_exception_id uuid, p_action decision_action, p_pay_amount numeric default null, p_hold_amount numeric default null, p_comment text default null, p_time_spent int default null, p_extra jsonb default '{}') returns jsonb
Every money/duplicate/fraud/posting decision.

Allowed actions per type (else `LEDGIC_INVALID: Action not allowed for this exception`):
| exception_type | actions |
|---|---|
| price_variance, qty_mismatch, unmatched_line | short_pay, approve_as_is, dispute, reject_invoice |
| no_po | link_po (`p_extra.po_id` required, same vendor+org), approve_without_po, reject_invoice |
| duplicate | merge (`p_extra.keep_invoice_id` optional, default the earlier invoice), reject_copy, not_duplicate |
| new_vendor_screen | request_w9, release_hold, reject_invoice |
| posting_failed | retry_posting, reject_invoice |
| extraction_review | — (use rpc_confirm_fields) |

Checks, in order:
1. Exception exists in an org where caller is a member (`LEDGIC_NOT_FOUND`); status not `resolved` (`LEDGIC_CONFLICT`). `disputed`/`awaiting_vendor` may be decided again.
2. Role: viewer → `Read-only access`; ap_clerk may only `link_po`; `new_vendor_screen` any action except `request_w9` → controller; `not_duplicate` → controller; others → ap_manager+.
3. Limit: impact = `amount_at_risk` (for short_pay: `p_hold_amount`; for approve_as_is: amount_at_risk). ap_manager requires impact ≤ `org_settings.manager_limit` else `LEDGIC_FORBIDDEN: Above your approval limit of $X`.
4. Comment required (non-blank) for: approve_as_is, approve_without_po, not_duplicate, release_hold, dispute. `release_hold` also requires `p_extra.verified_by_phone = true`.
5. Amounts: short_pay requires both amounts, `pay + hold = invoices.total` (±0.01) and `hold > 0`; defaults to the recommendation's amounts when both null.
6. SoD: caller must not be `set_by` of any `invoice_fields` row with source `human` whose audit `after.monetary = true` on the same invoice (and not the editor of any line money cell); `release_hold` additionally: caller ≠ `vendors.created_by`.

Effects (one transaction):
- `approvals` row (actor = `auth.uid()`, `time_spent_seconds = least(p_time_spent,1800)`); audit `decision.<action>`.
- exception status: `dispute` → `disputed`; `request_w9` → `awaiting_vendor`; everything else → `resolved` + `resolved_at`. Audit `exception.<status>`.
- invoice side effects (audited): `merge`/`reject_copy` → the copy gets `status='duplicate'`, `duplicate_of`; `reject_invoice` → `status='rejected'`; `link_po` → `po_id = p_extra.po_id`; `short_pay`/`approve_*`/`release_hold`/`not_duplicate` → `status='approved'`; invoice `human_touches += 1`, `touchless=false`.
- waiting run: `status='running'`, `next_attempt_at=now()`, `wait_exception_id=null` (except dispute / request_w9: run stays `waiting`), `context = context || jsonb_build_object('decision', {action, pay_amount, hold_amount, approval_id, actor_id, extra})`, `next_stage` = `match` for link_po, `posting` for retry_posting/short_pay/approve_*, `match` for release_hold/not_duplicate, `close` for reject_*/merge. `pipeline_events` (stage `approval`, status `resumed`, summary `<Action label> by <full_name>`). `pg_notify('ledgic_runs', run_id::text)`.
- Returns `{"approval_id": uuid, "run_id": uuid|null, "exception_status": exception_status}`.

## rpc_mark_exception_viewed(p_exception_id uuid) returns void
Sets `first_viewed_at` if null; inserts `ui_events(kind='opened')`. Any member.

## audit_verify(p_org uuid) returns bigint  (in 0001)
First broken `audit_log.id` for the org, or null. Security invoker.

## audit_verify_org(p_org uuid) returns jsonb
Wrapper for UI/core: checks `is_member(p_org)` (else `LEDGIC_FORBIDDEN`), runs `audit_verify` with definer rights.
Returns `{"ok": bool, "entries": bigint, "first_broken_id": bigint|null, "head_hash": text}`.

## llm_budget_reserve(p_est numeric) returns uuid  (service_role)
Atomic: upserts `llm_budget(day = (now() at time zone 'utc')::date, cap_usd = current_setting('ledgic.llm_daily_cap_usd', true)::numeric or 0.50)`, then
`update llm_budget set reserved_usd = reserved_usd + p_est where day = today and spent_usd + reserved_usd + p_est <= cap_usd returning ...`.
On success inserts `llm_budget_reservations` and returns its id; when the cap would be exceeded returns **null** (caller falls back to recorded/retrieval-only).
Core may also pass the cap: `llm_budget_reserve(p_est numeric, p_cap numeric default null)` — when non-null it updates today's `cap_usd`.

## llm_budget_settle(p_reservation uuid, p_actual numeric) returns void  (service_role)
`reserved_usd -= est`, `spent_usd += p_actual`, reservation `status='settled'`. `p_actual = 0` with status `released` when the call failed before spending. Idempotent (second settle is a no-op). Stale reservations (> 10 min, status reserved) are released by the scheduler via `llm_budget_release_stale()`.

## kb_search(p_org uuid, p_query_embedding vector(512), p_query_text text, p_k int default 8, p_kinds text[] default null) returns table(...)
Hybrid retrieval with reciprocal-rank fusion. Security invoker (RLS on kb_chunks applies) — core calls it as service role.
```
returns table (chunk_id uuid, document_id uuid, title text, kind text, contract_id uuid, vendor_id uuid,
               heading_path text, clause_ref text, content text,
               vector_rank int, text_rank int, rrf_score double precision)
```
- vector arm: top 40 by `embedding <=> p_query_embedding` within org (and kinds).
- text arm: top 40 by `ts_rank_cd(tsv, websearch_to_tsquery('english', p_query_text))` where matches.
- `rrf_score = coalesce(1/(60+vector_rank),0) + coalesce(1/(60+text_rank),0)`; order desc, limit `p_k`.

## rate_limit_hit(p_key text, p_limit int, p_window_seconds int) returns boolean  (service_role + authenticated)
Fixed window. Upsert `rate_limits(key)`: if `window_start < now() - window` reset to `(now(), 1)`, else `count += 1`.
Returns **true when the request is over the limit** (count > p_limit). Keys: `upload:ip:<ip>` (10/day),
`copilot:ip:<ip>`, `copilot:user:<uuid>`, `mcp:token:<id>`.

## Helpers (0002, used by policies)
- `is_member(p_org uuid) returns boolean`, `has_role(p_org uuid, roles member_role[]) returns boolean` — per 05 §10.
- `member_role_of(p_org uuid) returns member_role` — caller's role or null.
- `demo_purge_org(p_org uuid)` (service_role, security definer, refuses non-demo orgs) — deletes all org data incl. audit rows via `set local ledgic.allow_audit_purge = 'on'` (see audit_immutable in 0001).
