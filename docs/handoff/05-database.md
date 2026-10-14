# 05 — Database (Supabase Postgres)

Migrations live in `packages/db/supabase/migrations/` as timestamped SQL, applied with the Supabase CLI. Generate TypeScript types to `packages/db/src/types.ts` (`supabase gen types typescript`) and Python models in `services/core/app/db/models.py` (hand-written pydantic, checked by a test against `information_schema`).

## 1. Extensions
```sql
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists vector;
create extension if not exists pg_cron;
create extension if not exists citext;
```

## 2. Enums
```sql
create type member_role     as enum ('viewer','ap_clerk','ap_manager','controller','admin');
create type erp_system      as enum ('quickbooks','netsuite','none');
create type channel         as enum ('email','photo','portal','edi','upload');
create type match_mode      as enum ('three_way','two_way');
create type invoice_status  as enum ('received','extracted','in_review','enriched','screened','matched',
                                     'awaiting_decision','approved','posting','posted','rejected','duplicate','failed');
create type field_source    as enum ('llm','ocr','edi','human','rule');
create type stage           as enum ('intake','extraction','review','enrichment','screening','match','approval','posting','notify','close');
create type event_status    as enum ('started','succeeded','failed','skipped','waiting','resumed');
create type line_verdict    as enum ('matched','price_variance','qty_over_receipt','qty_over_order','unmatched_line','favorable');
create type invoice_verdict as enum ('clean','price_variance','qty_mismatch','no_po','unmatched_line','mixed');
create type exception_type  as enum ('extraction_review','price_variance','qty_mismatch','no_po','unmatched_line',
                                     'duplicate','new_vendor_screen','posting_failed');
create type exception_status as enum ('open','awaiting_vendor','disputed','resolved','escalated');
create type decision_action as enum ('confirm_fields','short_pay','approve_as_is','dispute','link_po','approve_without_po',
                                     'merge','reject_copy','not_duplicate','request_w9','release_hold','reject_invoice','retry_posting');
create type actor_type      as enum ('system','user','n8n','core');
create type cost_kind       as enum ('llm','ocr','infra','human');
```

## 3. Tenancy & identity
```sql
create table orgs (
  id uuid primary key default gen_random_uuid(),
  slug citext unique not null,
  name text not null,
  is_demo boolean not null default false,
  timezone text not null default 'America/New_York',
  created_at timestamptz not null default now()
);

create table org_settings (
  org_id uuid primary key references orgs on delete cascade,
  confidence_gate numeric(4,3) not null default 0.900,
  field_floor numeric(4,3) not null default 0.750,
  dup_hold_threshold numeric(4,3) not null default 0.900,
  dup_suggest_threshold numeric(4,3) not null default 0.750,
  fraud_hold_threshold numeric(4,3) not null default 0.700,
  over_receipt_allowance numeric(5,4) not null default 0,
  manager_limit numeric(12,2) not null default 5000.00,
  controller_notify_threshold numeric(12,2) not null default 500.00,
  sla_hours int not null default 24,
  loaded_hourly_rate_usd numeric(8,2) not null default 35.00,
  infra_monthly_usd numeric(10,2) not null default 55.00,
  slack_digest_local_time time not null default '09:30',
  updated_at timestamptz not null default now()
);

create table tolerance_policies (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  pct numeric(6,5) not null default 0.02,
  abs_amount numeric(12,2) not null default 25.00,
  effective_from timestamptz not null default now(),
  created_by uuid references auth.users,
  created_at timestamptz not null default now()
);
create index on tolerance_policies (org_id, effective_from desc);

create table profiles (
  user_id uuid primary key references auth.users on delete cascade,
  full_name text not null,
  initials text not null check (char_length(initials) between 1 and 3),
  created_at timestamptz not null default now()
);

create table memberships (
  org_id uuid references orgs on delete cascade,
  user_id uuid references auth.users on delete cascade,
  role member_role not null,
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);

create table entities (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  name text not null,
  short_code text not null,                 -- e.g. 'Entity 2' label source
  erp erp_system not null,
  erp_company_ref text,                     -- QBO realmId / NetSuite subsidiary id
  unique (org_id, short_code)
);

create table locations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  entity_id uuid not null references entities,
  code text not null,                       -- 'RS', 'BS', …  used in PO-RS-1873
  name text not null,                       -- 'Riverside'
  erp_class_ref text,                       -- QBO Class / NetSuite location id
  unique (org_id, code)
);
```

## 4. Master data
```sql
create table vendors (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  display_name text not null,               -- demo: category names, e.g. 'Protein Supplier'
  legal_name text,
  category text,
  match_mode match_mode not null default 'three_way',
  tax_id_last4 text,
  tax_id_hash text,                         -- sha256(org_salt || normalized tax id)
  remit_address jsonb,
  remit_address_changed_at timestamptz,
  bank_fingerprint text,                    -- sha256(org_salt || routing || account)
  bank_last4 text,
  w9_on_file boolean not null default false,
  w9_bank_fingerprint text,
  contact_email citext,
  erp_vendor_ref jsonb,                     -- {quickbooks: '123', netsuite: '456'}
  created_by uuid references auth.users,
  created_at timestamptz not null default now()
);
create index vendors_name_trgm on vendors using gin (display_name gin_trgm_ops);

create table vendor_aliases (
  vendor_id uuid references vendors on delete cascade,
  alias text not null,
  primary key (vendor_id, alias)
);
create index vendor_alias_trgm on vendor_aliases using gin (alias gin_trgm_ops);

create table items (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  item_key text not null,                   -- normalized key, e.g. 'shrimp-16-20-iqf'
  description text not null,
  uom text not null,                        -- lb, cs, ea, gal
  default_gl text,
  embedding vector(1024),
  unique (org_id, item_key)
);

create table gl_accounts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  entity_id uuid references entities,
  number text not null,                     -- '5000'
  name text not null,                       -- 'COGS-Food'
  erp_ref text,
  unique (org_id, entity_id, number)
);

create table contracts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  vendor_id uuid not null references vendors,
  title text not null,                      -- 'Vendor agreement 2026'
  document_path text,                       -- storage path of the PDF
  effective_from date not null,
  effective_to date not null,
  countersigned_at date
);

create table contract_prices (
  id uuid primary key default gen_random_uuid(),
  contract_id uuid not null references contracts on delete cascade,
  item_id uuid not null references items,
  uom text not null,
  unit_price numeric(12,4) not null,
  clause_ref text not null,                 -- '4.2'
  unique (contract_id, item_id)
);

create table purchase_orders (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  entity_id uuid not null references entities,
  location_id uuid not null references locations,
  vendor_id uuid not null references vendors,
  po_number text not null,                  -- 'PO-RS-1873'
  status text not null default 'open',
  ordered_at timestamptz not null,
  source text not null default 'quickbooks',
  erp_ref text,
  total numeric(12,2) not null,
  unique (org_id, po_number)
);

create table po_lines (
  id uuid primary key default gen_random_uuid(),
  po_id uuid not null references purchase_orders on delete cascade,
  line_no int not null,
  item_id uuid references items,
  description text not null,
  qty numeric(12,3) not null,
  uom text not null,
  unit_price numeric(12,4) not null,
  amount numeric(12,2) not null,
  unique (po_id, line_no)
);

create table goods_receipts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  po_id uuid not null references purchase_orders,
  grn_number text not null,                 -- 'GRN-RS-4410'
  received_at timestamptz not null,
  received_by text,
  source text not null default 'receiving_app',
  unique (org_id, grn_number)
);

create table grn_lines (
  id uuid primary key default gen_random_uuid(),
  grn_id uuid not null references goods_receipts on delete cascade,
  po_line_id uuid not null references po_lines,
  qty_received numeric(12,3) not null,
  uom text not null
);
```

## 5. Documents, invoices, extraction
```sql
create table documents (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  channel channel not null,
  storage_path text not null,
  sha256 text not null,
  mime text not null,
  page_count int,
  phash text,                               -- 64-bit perceptual hash (hex) of page 1
  original_filename text,
  source_meta jsonb not null default '{}',  -- {from, subject, message_id} | {location_id, uploaded_by} | {portal} | {isa_control}
  preprocessing jsonb,                      -- {skew_deg: 2.0, perspective: true, pages: [...image paths]}
  received_at timestamptz not null default now(),
  unique (org_id, sha256)
);

create table invoices (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  document_id uuid not null references documents,
  vendor_id uuid references vendors,
  entity_id uuid references entities,
  location_id uuid references locations,
  po_id uuid references purchase_orders,
  invoice_number text,
  invoice_number_norm text generated always as (upper(regexp_replace(coalesce(invoice_number,''), '[^A-Za-z0-9]', '', 'g'))) stored,
  invoice_date date,
  due_date date,
  terms text,
  currency char(3) not null default 'USD',
  subtotal numeric(12,2),
  tax numeric(12,2) default 0,
  freight numeric(12,2) default 0,
  total numeric(12,2),
  status invoice_status not null default 'received',
  doc_confidence numeric(4,3),
  gate_passed boolean,
  duplicate_of uuid references invoices,
  touchless boolean,
  human_touches int not null default 0,
  received_at timestamptz not null,
  posted_at timestamptz,
  created_at timestamptz not null default now()
);
create index on invoices (org_id, received_at desc);
create index on invoices (org_id, vendor_id, invoice_number_norm);
create index on invoices (org_id, status);

create table invoice_fields (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references invoices on delete cascade,
  field text not null,                      -- vendor|invoice_number|invoice_date|terms|po_ref|total|subtotal|tax|freight|bank_routing|bank_account|remit_address
  value text,
  confidence numeric(4,3) not null,
  raw_confidence numeric(4,3),              -- pre-calibration model value
  bbox jsonb,                               -- {page, x, y, w, h} normalized 0..1
  source field_source not null,
  version int not null default 1,
  set_by uuid references auth.users,
  set_at timestamptz not null default now(),
  unique (invoice_id, field, version)
);

create table invoice_lines (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references invoices on delete cascade,
  line_no int not null,
  description text not null,
  item_id uuid references items,
  qty numeric(12,3),
  uom text,
  unit_price numeric(12,4),
  amount numeric(12,2),
  confidences jsonb not null,               -- {description, qty, unit_price, amount}
  bboxes jsonb,                             -- same keys → bbox
  gl_account_id uuid references gl_accounts,
  gl_confidence numeric(4,3),
  po_line_id uuid references po_lines,
  unique (invoice_id, line_no)
);
```

## 6. Screening, matching, exceptions, decisions
```sql
create table duplicate_candidates (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  invoice_id uuid not null references invoices,
  candidate_invoice_id uuid not null references invoices,
  similarity numeric(4,3) not null,
  evidence jsonb not null,                  -- {invoice_no:'exact', amount:'exact', date:'exact', lines:'5/5', file:{differs:true, image_sim:0.83}}
  created_at timestamptz not null default now()
);

create table fraud_signals (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  invoice_id uuid not null references invoices,
  vendor_id uuid references vendors,
  signal text not null,                     -- bank_mismatch_w9 | vendor_age_lt_14d | no_po | remit_address_new | amount_anomaly
  weight numeric(4,3) not null,
  detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table match_results (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references invoices on delete cascade,
  verdict invoice_verdict not null,
  tolerance_pct numeric(6,5) not null,
  tolerance_abs numeric(12,2) not null,
  expected_total numeric(12,2) not null,
  total_delta numeric(12,2) not null,
  lines_verified int not null,
  lines_total int not null,
  duration_ms int not null,
  computed_at timestamptz not null default now(),
  unique (invoice_id)                       -- latest result; history kept in audit_log
);

create table match_line_results (
  id uuid primary key default gen_random_uuid(),
  match_result_id uuid not null references match_results on delete cascade,
  invoice_line_id uuid not null references invoice_lines,
  po_line_id uuid references po_lines,
  grn_qty numeric(12,3),
  expected_unit_price numeric(12,4),
  expected_source text,                     -- 'contract' | 'po'
  contract_price_id uuid references contract_prices,
  expected_amount numeric(12,2),
  delta_amount numeric(12,2),
  delta_pct numeric(8,5),
  allowed_amount numeric(12,2),
  verdict line_verdict not null,
  note text
);

create table exceptions (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  invoice_id uuid not null references invoices,
  type exception_type not null,
  status exception_status not null default 'open',
  amount_at_risk numeric(12,2) not null default 0,
  reason text not null,                     -- one-line queue reason, e.g. 'shrimp 12% over contract'
  assigned_role member_role not null default 'ap_manager',
  assigned_to uuid references auth.users,
  escalated boolean not null default false,
  resume_url text,                          -- n8n Wait resume webhook (secret-bearing; never sent to client)
  opened_at timestamptz not null default now(),
  first_viewed_at timestamptz,
  sla_due_at timestamptz not null,
  resolved_at timestamptz
);
create index on exceptions (org_id, status, opened_at);

create table recommendations (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid not null unique references exceptions on delete cascade,
  action decision_action not null,
  pay_amount numeric(12,2),
  hold_amount numeric(12,2),
  confidence numeric(4,3) not null,
  reasons jsonb not null                    -- array of {template_id, text, facts}
);

create table approvals (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  exception_id uuid not null references exceptions,
  actor_id uuid not null references auth.users,
  action decision_action not null,
  pay_amount numeric(12,2),
  hold_amount numeric(12,2),
  comment text,
  decided_at timestamptz not null default now(),
  time_spent_seconds int                    -- from UI telemetry (capped 1800)
);

create table pending_resumes (
  id uuid primary key default gen_random_uuid(),
  approval_id uuid not null references approvals,
  attempts int not null default 0,
  last_error text,
  next_attempt_at timestamptz not null default now()
);
```

## 7. Pipeline, posting, cost, eval
```sql
create table pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  run_number bigserial unique,               -- displayed 'run 88,412'
  org_id uuid not null references orgs on delete cascade,
  document_id uuid not null references documents,
  invoice_id uuid references invoices,
  n8n_execution_id text,
  workflow_version text not null,            -- 'v14'
  status text not null default 'running',    -- running|waiting|succeeded|failed
  current_stage stage not null default 'intake',
  started_at timestamptz not null default now(),
  finished_at timestamptz
);
create index on pipeline_runs (org_id, started_at desc);

create table pipeline_events (
  id bigserial primary key,
  org_id uuid not null references orgs on delete cascade,
  run_id uuid not null references pipeline_runs on delete cascade,
  stage stage not null,
  status event_status not null,
  at timestamptz not null default now(),
  duration_ms int,
  summary text,                              -- human line for inspector, e.g. 'email PDF, 2 pages'
  detail jsonb not null default '{}'
);
create index on pipeline_events (org_id, at desc);
create index on pipeline_events (run_id, at);

create table dead_letters (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references orgs,
  run_id uuid references pipeline_runs,
  workflow text not null,
  node text,
  error text not null,
  payload jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table erp_postings (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  invoice_id uuid not null references invoices,
  system erp_system not null,
  status text not null,                      -- pending|posted|failed
  external_id text,                          -- QBO Bill Id / JE number shown as 'JE 18,240'
  request jsonb not null,
  response jsonb,
  attempts int not null default 0,
  posted_at timestamptz,
  error text,
  unique (invoice_id, system)
);

create table cost_ledger (
  id bigserial primary key,
  org_id uuid not null references orgs on delete cascade,
  run_id uuid references pipeline_runs,
  kind cost_kind not null,
  amount_usd numeric(12,6) not null,
  meta jsonb not null default '{}',          -- {model, input_tokens, output_tokens} | {pages} | {minutes}
  at timestamptz not null default now()
);

create table prompt_versions (
  id text primary key,                       -- 'p-38'
  model text not null,
  deployed_at timestamptz not null,
  notes text
);

create table eval_runs (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references orgs,
  week_start date not null,
  prompt_version text references prompt_versions,
  sample_size int not null,
  fields_labeled int not null,
  fields_correct int not null,
  accuracy numeric(6,4) generated always as (fields_correct::numeric / nullif(fields_labeled,0)) stored,
  by_field jsonb not null,
  created_at timestamptz not null default now(),
  unique (org_id, week_start)
);

create table integrations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs on delete cascade,
  provider text not null,                    -- quickbooks|netsuite|slack|email|portal|edi
  entity_id uuid references entities,
  status text not null default 'disconnected',
  config jsonb not null default '{}',        -- non-secret settings
  vault_secret_id uuid,                      -- Supabase Vault reference for tokens
  last_sync_at timestamptz,
  last_error text,
  unique (org_id, provider, entity_id)
);

create table inbound_addresses (             -- email intake routing (08 §1)
  address citext primary key,                -- 'invoices@ap.<domain>'
  org_id uuid not null references orgs on delete cascade,
  sender_rate_limit_per_hour int not null default 10
);

create table ui_events (                     -- telemetry for human_minutes
  id bigserial primary key,
  org_id uuid not null references orgs,
  user_id uuid not null references auth.users,
  exception_id uuid references exceptions,
  kind text not null,                        -- opened|focused|blurred|decided
  at timestamptz not null default now()
);
```

## 8. Audit log (append-only, hash-chained)
```sql
create table audit_log (
  id bigserial primary key,
  org_id uuid not null references orgs,
  at timestamptz not null default clock_timestamp(),
  actor_type actor_type not null,
  actor_id text,                             -- user uuid or 'core'/'n8n'
  action text not null,                      -- e.g. 'exception.opened', 'field.corrected', 'decision.short_pay', 'erp.posted'
  entity_type text not null,
  entity_id text not null,
  before jsonb,
  after jsonb,
  prev_hash text,
  hash text not null
);
create index on audit_log (org_id, entity_type, entity_id, id);

create or replace function audit_chain() returns trigger language plpgsql as $$
declare p text;
begin
  perform pg_advisory_xact_lock(hashtext('audit:' || new.org_id::text));
  select hash into p from audit_log where org_id = new.org_id order by id desc limit 1;
  new.prev_hash := coalesce(p, repeat('0',64));
  new.hash := encode(digest(
      new.prev_hash || '|' || new.org_id || '|' || new.at || '|' || new.actor_type || '|' || coalesce(new.actor_id,'') || '|' ||
      new.action || '|' || new.entity_type || '|' || new.entity_id || '|' || coalesce(new.before::text,'') || '|' || coalesce(new.after::text,''),
      'sha256'), 'hex');
  return new;
end $$;
create trigger audit_chain_bi before insert on audit_log for each row execute function audit_chain();

create or replace function audit_immutable() returns trigger language plpgsql as $$
begin raise exception 'audit_log is append-only'; end $$;
create trigger audit_no_update before update or delete on audit_log for each row execute function audit_immutable();
revoke update, delete, truncate on audit_log from public, anon, authenticated, service_role;

-- verification (returns first broken id or null)
create or replace function audit_verify(p_org uuid) returns bigint language plpgsql stable as $$
declare r record; prev text := repeat('0',64); h text;
begin
  for r in select * from audit_log where org_id = p_org order by id loop
    h := encode(digest(prev || '|' || r.org_id || '|' || r.at || '|' || r.actor_type || '|' || coalesce(r.actor_id,'') || '|' ||
         r.action || '|' || r.entity_type || '|' || r.entity_id || '|' || coalesce(r.before::text,'') || '|' || coalesce(r.after::text,''),'sha256'),'hex');
    if r.prev_hash <> prev or r.hash <> h then return r.id; end if;
    prev := r.hash;
  end loop;
  return null;
end $$;
```
Rule: **every** state change to invoices, fields, exceptions, approvals, erp_postings, vendors (bank/remit), settings and policies writes an `audit_log` row in the same transaction. Implement via explicit inserts in core and server actions (not generic triggers) so `action` names are meaningful; add a test that fails if any of those tables changes without a matching audit row.

## 9. KPI views
```sql
-- today's counts per org (org-local day)
create view v_pipeline_today as
with d as (select o.id org_id, (now() at time zone o.timezone)::date as day, o.timezone from orgs o)
select d.org_id,
  count(distinct r.id) filter (where true)                                             as received,
  count(distinct r.id) filter (where e_ex.passed)                                      as extracted_above_gate,
  count(distinct r.id) filter (where i.po_id is not null and i.status not in ('received','extracted','in_review')) as enriched_po_linked,
  count(distinct r.id) filter (where m.verdict = 'clean')                              as matched_clean,
  count(distinct r.id) filter (where x.invoice_id is not null)                         as routed_to_people
from d
join pipeline_runs r on r.org_id = d.org_id and (r.started_at at time zone d.timezone)::date = d.day
left join invoices i on i.id = r.invoice_id
left join lateral (select bool_or((detail->>'gate_passed')::boolean) passed from pipeline_events pe
                   where pe.run_id = r.id and pe.stage='extraction' and pe.status='succeeded') e_ex on true
left join match_results m on m.invoice_id = r.invoice_id
left join (select distinct invoice_id from exceptions) x on x.invoice_id = r.invoice_id
group by d.org_id;
```
Also create (as **materialized** views refreshed each minute by `pg_cron`, with unique indexes for `refresh … concurrently`):
- `mv_channel_today(org_id, channel, count)`
- `mv_stage_today(org_id, …)` — every number in the five stage columns
- `mv_ops_period(org_id, period_key, invoices, cost_total, cost_per_invoice, touchless_rate, median_cycle_seconds, held_variances, held_duplicates, held_fraud, short_pays_accepted, avg_decision_seconds, decisions_logged_pct)` for `mtd`, `qtd`, `l30`
- `mv_location_period(org_id, period_key, location_id, volume, exception_rate)`
- `mv_eval_weekly(org_id, week_start, accuracy, prompt_version)`
Expose all KPI reads through these views only (`01` §5 is the spec for each column).

## 10. Row-level security
```sql
create or replace function is_member(p_org uuid) returns boolean language sql stable security definer set search_path = public as
$$ select exists (select 1 from memberships where org_id = p_org and user_id = auth.uid()) $$;

create or replace function has_role(p_org uuid, roles member_role[]) returns boolean language sql stable security definer set search_path = public as
$$ select exists (select 1 from memberships where org_id = p_org and user_id = auth.uid() and role = any(roles)) $$;
```
- Enable RLS on **every** table. For each table with `org_id`: `select` policy `using (is_member(org_id))`. Child tables without `org_id` (e.g., `po_lines`, `invoice_lines`, `match_line_results`) use `exists` through their parent.
- **No insert/update/delete policies for `authenticated`** on pipeline tables — writes from the web go through `security definer` RPC functions that check role, SoD and limits and write the audit row (`rpc_confirm_fields`, `rpc_decide_exception`, `rpc_update_policy`, `rpc_invite_member`…). Core and n8n use the service role.
- `exceptions.resume_url`, `integrations.vault_secret_id` are excluded from client reads via a view `exceptions_public` (the web selects from the view; the base table's select policy is restricted to service role).
- Storage bucket `documents`: private; object path `org/<org_id>/…`; policy allows `select` when `is_member(split_part(name,'/',2)::uuid)`; the web serves pages with signed URLs (5 min).
- The public demo viewer is a normal user with `viewer` role on the demo org only.

## 11. Realtime
Enable Realtime publication for: `pipeline_events`, `exceptions`, `approvals`, `erp_postings`. The client filters by `org_id=eq.<id>`; RLS applies.
