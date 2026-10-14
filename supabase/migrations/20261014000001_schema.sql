-- Ledgic schema 0001: extensions, enums, tables, indexes, audit log (hash chain + immutability).
-- Source of truth: docs/handoff/05-database.md, with the departures listed in docs/DECISIONS.md
-- and contracts/*.md (orchestrator columns, RAG/MCP/budget tables, vector(512)).
-- RLS policies, RPCs, views, realtime and storage live in later migrations (0002+).

------------------------------------------------------------------------------------------------
-- 1. Extensions (Supabase installs these into schema "extensions"; types are referenced qualified)
------------------------------------------------------------------------------------------------
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create extension if not exists pg_trgm  with schema extensions;
create extension if not exists vector   with schema extensions;
create extension if not exists citext   with schema extensions;

do $$
begin
  if exists (select 1 from pg_available_extensions where name = 'pg_cron') then
    execute 'create extension if not exists pg_cron';
  else
    raise notice 'pg_cron not available; KPI materialized-view refresh must be scheduled by core';
  end if;
end $$;

------------------------------------------------------------------------------------------------
-- 2. Enums
------------------------------------------------------------------------------------------------
create type public.member_role     as enum ('viewer','ap_clerk','ap_manager','controller','admin');
create type public.erp_system      as enum ('quickbooks','netsuite','none');
create type public.channel         as enum ('email','photo','portal','edi','upload');
create type public.match_mode      as enum ('three_way','two_way');
create type public.invoice_status  as enum ('received','extracted','in_review','enriched','screened','matched',
                                            'awaiting_decision','approved','posting','posted','rejected','duplicate','failed');
create type public.field_source    as enum ('llm','ocr','edi','human','rule');
create type public.stage           as enum ('intake','extraction','review','enrichment','screening','match','approval','posting','notify','close');
create type public.event_status    as enum ('started','succeeded','failed','skipped','waiting','resumed');
create type public.line_verdict    as enum ('matched','price_variance','qty_over_receipt','qty_over_order','unmatched_line','favorable');
create type public.invoice_verdict as enum ('clean','price_variance','qty_mismatch','no_po','unmatched_line','mixed');
create type public.exception_type  as enum ('extraction_review','price_variance','qty_mismatch','no_po','unmatched_line',
                                            'duplicate','new_vendor_screen','posting_failed');
create type public.exception_status as enum ('open','awaiting_vendor','disputed','resolved','escalated');
create type public.decision_action as enum ('confirm_fields','short_pay','approve_as_is','dispute','link_po','approve_without_po',
                                            'merge','reject_copy','not_duplicate','request_w9','release_hold','reject_invoice','retry_posting');
-- departure: 'n8n' replaced by 'agent' (AI agents) and 'mcp' (MCP tool calls); core = orchestrator
create type public.actor_type      as enum ('system','user','core','agent','mcp');
create type public.cost_kind       as enum ('llm','ocr','infra','human');

------------------------------------------------------------------------------------------------
-- 3. Tenancy & identity
------------------------------------------------------------------------------------------------
create table public.orgs (
  id uuid primary key default gen_random_uuid(),
  slug extensions.citext unique not null,
  name text not null,
  is_demo boolean not null default false,
  timezone text not null default 'America/New_York',
  created_at timestamptz not null default now()
);

create table public.org_settings (
  org_id uuid primary key references public.orgs on delete cascade,
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

create table public.tolerance_policies (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  pct numeric(6,5) not null default 0.02,
  abs_amount numeric(12,2) not null default 25.00,
  effective_from timestamptz not null default now(),
  created_by uuid references auth.users on delete set null,
  created_at timestamptz not null default now()
);
create index on public.tolerance_policies (org_id, effective_from desc);

create table public.profiles (
  user_id uuid primary key references auth.users on delete cascade,
  full_name text not null,
  initials text not null check (char_length(initials) between 1 and 3),
  created_at timestamptz not null default now()
);

create table public.memberships (
  org_id uuid references public.orgs on delete cascade,
  user_id uuid references auth.users on delete cascade,
  role public.member_role not null,
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);
create index on public.memberships (user_id);

create table public.entities (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  name text not null,
  short_code text not null,
  erp public.erp_system not null,
  erp_company_ref text,
  unique (org_id, short_code)
);

create table public.locations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  entity_id uuid not null references public.entities on delete cascade,
  code text not null,
  name text not null,
  erp_class_ref text,
  unique (org_id, code)
);

------------------------------------------------------------------------------------------------
-- 4. Master data
------------------------------------------------------------------------------------------------
create table public.vendors (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  display_name text not null,
  legal_name text,
  category text,
  match_mode public.match_mode not null default 'three_way',
  tax_id_last4 text,
  tax_id_hash text,
  remit_address jsonb,
  remit_address_changed_at timestamptz,
  bank_fingerprint text,
  bank_last4 text,
  w9_on_file boolean not null default false,
  w9_bank_fingerprint text,
  contact_email extensions.citext,
  erp_vendor_ref jsonb,
  created_by uuid references auth.users on delete set null,
  created_at timestamptz not null default now()
);
create index vendors_org_idx on public.vendors (org_id);
create index vendors_name_trgm on public.vendors using gin (display_name extensions.gin_trgm_ops);

create table public.vendor_aliases (
  vendor_id uuid references public.vendors on delete cascade,
  alias text not null,
  primary key (vendor_id, alias)
);
create index vendor_alias_trgm on public.vendor_aliases using gin (alias extensions.gin_trgm_ops);

create table public.items (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  item_key text not null,
  description text not null,
  uom text not null,
  default_gl text,
  embedding extensions.vector(512),          -- departure: text-embedding-3-small @ 512 dims
  unique (org_id, item_key)
);

create table public.gl_accounts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  entity_id uuid references public.entities on delete cascade,
  number text not null,
  name text not null,
  erp_ref text,
  unique (org_id, entity_id, number)
);

create table public.contracts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  vendor_id uuid not null references public.vendors on delete cascade,
  title text not null,
  document_path text,
  effective_from date not null,
  effective_to date not null,
  countersigned_at date
);
create index on public.contracts (org_id, vendor_id);

create table public.contract_prices (
  id uuid primary key default gen_random_uuid(),
  contract_id uuid not null references public.contracts on delete cascade,
  item_id uuid not null references public.items on delete cascade,
  uom text not null,
  unit_price numeric(12,4) not null,
  clause_ref text not null,
  unique (contract_id, item_id)
);

create table public.purchase_orders (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  entity_id uuid not null references public.entities on delete cascade,
  location_id uuid not null references public.locations on delete cascade,
  vendor_id uuid not null references public.vendors on delete cascade,
  po_number text not null,
  status text not null default 'open',
  ordered_at timestamptz not null,
  source text not null default 'quickbooks',
  erp_ref text,
  total numeric(12,2) not null,
  unique (org_id, po_number)
);
create index on public.purchase_orders (org_id, vendor_id, location_id, ordered_at desc);

create table public.po_lines (
  id uuid primary key default gen_random_uuid(),
  po_id uuid not null references public.purchase_orders on delete cascade,
  line_no int not null,
  item_id uuid references public.items on delete set null,
  description text not null,
  qty numeric(12,3) not null,
  uom text not null,
  unit_price numeric(12,4) not null,
  amount numeric(12,2) not null,
  unique (po_id, line_no)
);

create table public.goods_receipts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  po_id uuid not null references public.purchase_orders on delete cascade,
  grn_number text not null,
  received_at timestamptz not null,
  received_by text,
  source text not null default 'receiving_app',
  unique (org_id, grn_number)
);
create index on public.goods_receipts (po_id);

create table public.grn_lines (
  id uuid primary key default gen_random_uuid(),
  grn_id uuid not null references public.goods_receipts on delete cascade,
  po_line_id uuid not null references public.po_lines on delete cascade,
  qty_received numeric(12,3) not null,
  uom text not null
);
create index on public.grn_lines (po_line_id);

------------------------------------------------------------------------------------------------
-- 5. Documents, invoices, extraction
------------------------------------------------------------------------------------------------
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  channel public.channel not null,
  storage_path text not null,
  sha256 text not null,
  mime text not null,
  page_count int,
  phash text,
  original_filename text,
  source_meta jsonb not null default '{}',
  preprocessing jsonb,
  received_at timestamptz not null default now(),
  unique (org_id, sha256)
);
create index on public.documents (org_id, received_at desc);

create table public.invoices (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  document_id uuid not null references public.documents on delete cascade,
  vendor_id uuid references public.vendors on delete set null,
  entity_id uuid references public.entities on delete set null,
  location_id uuid references public.locations on delete set null,
  po_id uuid references public.purchase_orders on delete set null,
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
  status public.invoice_status not null default 'received',
  doc_confidence numeric(4,3),
  gate_passed boolean,
  duplicate_of uuid references public.invoices on delete set null,
  touchless boolean,
  human_touches int not null default 0,
  extraction_mode text check (extraction_mode in ('live','recorded','simulated')),
  received_at timestamptz not null,
  posted_at timestamptz,
  created_at timestamptz not null default now()
);
create index on public.invoices (org_id, received_at desc);
create index on public.invoices (org_id, vendor_id, invoice_number_norm);
create index on public.invoices (org_id, status);
create index on public.invoices (document_id);

create table public.invoice_fields (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices on delete cascade,
  field text not null,
  value text,
  confidence numeric(4,3) not null,
  raw_confidence numeric(4,3),
  bbox jsonb,
  source public.field_source not null,
  version int not null default 1,
  set_by uuid references auth.users on delete set null,
  set_at timestamptz not null default now(),
  unique (invoice_id, field, version)
);

create table public.invoice_lines (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices on delete cascade,
  line_no int not null,
  description text not null,
  item_id uuid references public.items on delete set null,
  qty numeric(12,3),
  uom text,
  unit_price numeric(12,4),
  amount numeric(12,2),
  confidences jsonb not null,
  bboxes jsonb,
  gl_account_id uuid references public.gl_accounts on delete set null,
  gl_confidence numeric(4,3),
  po_line_id uuid references public.po_lines on delete set null,
  unique (invoice_id, line_no)
);

------------------------------------------------------------------------------------------------
-- 6. Screening, matching, exceptions, decisions
------------------------------------------------------------------------------------------------
create table public.duplicate_candidates (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  invoice_id uuid not null references public.invoices on delete cascade,
  candidate_invoice_id uuid not null references public.invoices on delete cascade,
  similarity numeric(4,3) not null,
  evidence jsonb not null,
  created_at timestamptz not null default now()
);
create index on public.duplicate_candidates (invoice_id);

create table public.fraud_signals (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  invoice_id uuid not null references public.invoices on delete cascade,
  vendor_id uuid references public.vendors on delete cascade,
  signal text not null,
  weight numeric(4,3) not null,
  detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index on public.fraud_signals (invoice_id);

create table public.match_results (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices on delete cascade,
  verdict public.invoice_verdict not null,
  tolerance_pct numeric(6,5) not null,
  tolerance_abs numeric(12,2) not null,
  expected_total numeric(12,2) not null,
  total_delta numeric(12,2) not null,
  lines_verified int not null,
  lines_total int not null,
  duration_ms int not null,
  computed_at timestamptz not null default now(),
  unique (invoice_id)
);

create table public.match_line_results (
  id uuid primary key default gen_random_uuid(),
  match_result_id uuid not null references public.match_results on delete cascade,
  invoice_line_id uuid not null references public.invoice_lines on delete cascade,
  po_line_id uuid references public.po_lines on delete set null,
  grn_qty numeric(12,3),
  expected_unit_price numeric(12,4),
  expected_source text,
  contract_price_id uuid references public.contract_prices on delete set null,
  expected_amount numeric(12,2),
  delta_amount numeric(12,2),
  delta_pct numeric(8,5),
  allowed_amount numeric(12,2),
  verdict public.line_verdict not null,
  note text
);
create index on public.match_line_results (match_result_id);

create table public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  run_number bigserial unique,
  org_id uuid not null references public.orgs on delete cascade,
  document_id uuid not null references public.documents on delete cascade,
  invoice_id uuid references public.invoices on delete set null,
  workflow_version text not null default 'v1',           -- displayed in status bar (e.g. 'v14')
  orchestrator_version text,                             -- code version (git sha) that last advanced the run
  status text not null default 'running'
    check (status in ('running','waiting','succeeded','failed','cancelled')),
  current_stage public.stage not null default 'intake',
  -- durable orchestrator state (departure D1)
  next_stage public.stage,
  attempt int not null default 0,
  next_attempt_at timestamptz default now(),
  lease_owner text,
  lease_until timestamptz,
  wait_exception_id uuid,                                -- FK added after exceptions
  context jsonb not null default '{}',
  last_error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);
create index on public.pipeline_runs (org_id, started_at desc);
create index pipeline_runs_runnable_idx on public.pipeline_runs (next_attempt_at)
  where status = 'running';
create index on public.pipeline_runs (invoice_id);

create table public.exceptions (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  invoice_id uuid not null references public.invoices on delete cascade,
  run_id uuid references public.pipeline_runs on delete set null,   -- run parked on this exception
  type public.exception_type not null,
  status public.exception_status not null default 'open',
  amount_at_risk numeric(12,2) not null default 0,
  reason text not null,
  assigned_role public.member_role not null default 'ap_manager',
  assigned_to uuid references auth.users on delete set null,
  escalated boolean not null default false,
  opened_at timestamptz not null default now(),
  first_viewed_at timestamptz,
  sla_due_at timestamptz not null,
  resolved_at timestamptz
);
create index on public.exceptions (org_id, status, opened_at);
create index on public.exceptions (invoice_id);

alter table public.pipeline_runs
  add constraint pipeline_runs_wait_exception_fk
  foreign key (wait_exception_id) references public.exceptions on delete set null;

create table public.recommendations (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid not null unique references public.exceptions on delete cascade,
  action public.decision_action not null,
  pay_amount numeric(12,2),
  hold_amount numeric(12,2),
  confidence numeric(4,3) not null,
  reasons jsonb not null
);

create table public.approvals (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  exception_id uuid not null references public.exceptions on delete cascade,
  actor_id uuid not null references auth.users,
  action public.decision_action not null,
  pay_amount numeric(12,2),
  hold_amount numeric(12,2),
  comment text,
  decided_at timestamptz not null default now(),
  time_spent_seconds int check (time_spent_seconds is null or time_spent_seconds between 0 and 1800)
);
create index on public.approvals (org_id, decided_at desc);
create index on public.approvals (exception_id);

create table public.exception_drafts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  exception_id uuid not null references public.exceptions on delete cascade,
  kind text not null check (kind in ('vendor_notice','explanation')),
  body_md text not null,
  citations jsonb not null default '[]',      -- [{chunk_id, document_id, title, clause_ref, quote}]
  model text,
  prompt_version text,
  mode text not null check (mode in ('live','recorded')),
  cost_usd numeric(12,6) not null default 0,
  created_at timestamptz not null default now()
);
create index on public.exception_drafts (exception_id, kind, created_at desc);

------------------------------------------------------------------------------------------------
-- 7. Pipeline, posting, cost, eval
------------------------------------------------------------------------------------------------
create table public.pipeline_events (
  id bigserial primary key,
  org_id uuid not null references public.orgs on delete cascade,
  run_id uuid not null references public.pipeline_runs on delete cascade,
  stage public.stage not null,
  status public.event_status not null,
  at timestamptz not null default now(),
  duration_ms int,
  summary text,
  detail jsonb not null default '{}'
);
create index on public.pipeline_events (org_id, at desc);
create index on public.pipeline_events (run_id, at);

-- Runs that exhausted retries (status bar "Dead-letter queue N").
create table public.dead_letters (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references public.orgs on delete cascade,
  run_id uuid references public.pipeline_runs on delete cascade,
  stage public.stage,
  error text not null,
  payload jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index on public.dead_letters (org_id) where resolved_at is null;

create table public.erp_postings (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  invoice_id uuid not null references public.invoices on delete cascade,
  system public.erp_system not null,
  status text not null check (status in ('pending','posted','failed')),
  external_id text,
  request jsonb not null,
  response jsonb,
  attempts int not null default 0,
  posted_at timestamptz,
  error text,
  unique (invoice_id, system)
);
create index on public.erp_postings (org_id, posted_at desc);

create table public.cost_ledger (
  id bigserial primary key,
  org_id uuid not null references public.orgs on delete cascade,
  run_id uuid references public.pipeline_runs on delete set null,
  kind public.cost_kind not null,
  amount_usd numeric(12,6) not null,
  meta jsonb not null default '{}',
  at timestamptz not null default now()
);
create index on public.cost_ledger (org_id, at desc);

create table public.prompt_versions (
  id text primary key,
  model text not null,
  deployed_at timestamptz not null,
  notes text
);

create table public.eval_runs (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references public.orgs on delete cascade,
  week_start date not null,
  prompt_version text references public.prompt_versions,
  sample_size int not null,
  fields_labeled int not null,
  fields_correct int not null,
  accuracy numeric(6,4) generated always as (fields_correct::numeric / nullif(fields_labeled,0)) stored,
  by_field jsonb not null,
  created_at timestamptz not null default now(),
  unique (org_id, week_start)
);

create table public.integrations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  provider text not null,
  entity_id uuid references public.entities on delete cascade,
  status text not null default 'disconnected',
  config jsonb not null default '{}',
  vault_secret_id uuid,
  last_sync_at timestamptz,
  last_error text,
  unique nulls not distinct (org_id, provider, entity_id)
);

create table public.ui_events (
  id bigserial primary key,
  org_id uuid not null references public.orgs on delete cascade,
  user_id uuid not null references auth.users on delete cascade,
  exception_id uuid references public.exceptions on delete cascade,
  kind text not null,
  at timestamptz not null default now()
);
create index on public.ui_events (org_id, at desc);

------------------------------------------------------------------------------------------------
-- 8. RAG knowledge base, AI budget, MCP, copilot cache, rate limits (departures D9-D12)
------------------------------------------------------------------------------------------------
create table public.kb_documents (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.orgs on delete cascade,
  kind text not null check (kind in ('contract','policy','vendor_note')),
  title text not null,
  contract_id uuid references public.contracts on delete cascade,
  vendor_id uuid references public.vendors on delete cascade,
  source_path text,
  created_at timestamptz not null default now()
);
create index on public.kb_documents (org_id, kind);

create table public.kb_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.kb_documents on delete cascade,
  org_id uuid not null references public.orgs on delete cascade,
  ord int not null,
  heading_path text,
  clause_ref text,
  content text not null,
  embedding extensions.vector(512),
  tsv tsvector generated always as (to_tsvector('english'::regconfig, coalesce(heading_path,'') || ' ' || content)) stored,
  unique (document_id, ord)
);
create index kb_chunks_embedding_hnsw on public.kb_chunks using hnsw (embedding extensions.vector_cosine_ops);
create index kb_chunks_tsv_gin on public.kb_chunks using gin (tsv);
create index on public.kb_chunks (org_id);

create table public.mcp_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  org_id uuid not null references public.orgs on delete cascade,
  name text not null,
  token_hash text not null unique,             -- sha256 hex of the raw token; raw token never stored
  scopes text[] not null default '{read}',
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  last_used_at timestamptz
);

-- Global (not per-org) daily LLM spend cap. Day is UTC.
create table public.llm_budget (
  day date primary key,
  cap_usd numeric(10,4) not null,
  reserved_usd numeric(12,6) not null default 0,
  spent_usd numeric(12,6) not null default 0
);

create table public.llm_budget_reservations (
  id uuid primary key default gen_random_uuid(),
  day date not null references public.llm_budget on delete cascade,
  est_usd numeric(12,6) not null,
  actual_usd numeric(12,6),
  status text not null default 'reserved' check (status in ('reserved','settled','released')),
  created_at timestamptz not null default now(),
  settled_at timestamptz
);
create index on public.llm_budget_reservations (status, created_at) where status = 'reserved';

create table public.copilot_cache (
  org_id uuid not null references public.orgs on delete cascade,
  q_hash text not null,
  question text not null,
  answer jsonb not null,                        -- {answer_md, citations[], mode, model}
  created_at timestamptz not null default now(),
  primary key (org_id, q_hash)
);

create table public.rate_limits (
  key text primary key,
  window_start timestamptz not null,
  count int not null default 0
);

------------------------------------------------------------------------------------------------
-- 9. Audit log (append-only, hash-chained)
------------------------------------------------------------------------------------------------
create table public.audit_log (
  id bigserial primary key,
  org_id uuid not null references public.orgs,
  at timestamptz not null default clock_timestamp(),
  actor_type public.actor_type not null,
  actor_id text,
  action text not null,
  entity_type text not null,
  entity_id text not null,
  before jsonb,
  after jsonb,
  prev_hash text,
  hash text not null
);
create index on public.audit_log (org_id, entity_type, entity_id, id);
create index on public.audit_log (org_id, id);

-- Canonical row serialization. Timestamp is rendered in UTC with microseconds so the hash
-- does not depend on the session TimeZone (departure from 05 §8, which used at::text).
create or replace function public.audit_row_digest(
  p_prev text, p_org uuid, p_at timestamptz, p_actor_type public.actor_type, p_actor_id text,
  p_action text, p_entity_type text, p_entity_id text, p_before jsonb, p_after jsonb)
returns text language sql immutable set search_path = '' as $$
  select encode(extensions.digest(
    p_prev || '|' || p_org::text || '|' || to_char(p_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') || '|' ||
    p_actor_type::text || '|' || coalesce(p_actor_id,'') || '|' || p_action || '|' || p_entity_type || '|' || p_entity_id || '|' ||
    coalesce(p_before::text,'') || '|' || coalesce(p_after::text,''), 'sha256'), 'hex')
$$;

create or replace function public.audit_chain() returns trigger language plpgsql
security definer set search_path = '' as $$
declare p text;
begin
  perform pg_advisory_xact_lock(hashtext('audit:' || new.org_id::text));
  select hash into p from public.audit_log where org_id = new.org_id order by id desc limit 1;
  new.at := coalesce(new.at, clock_timestamp());
  new.prev_hash := coalesce(p, repeat('0',64));
  new.hash := public.audit_row_digest(new.prev_hash, new.org_id, new.at, new.actor_type, new.actor_id,
                                      new.action, new.entity_type, new.entity_id, new.before, new.after);
  return new;
end $$;
create trigger audit_chain_bi before insert on public.audit_log for each row execute function public.audit_chain();

-- Append-only. The single escape hatch is the nightly demo reset: a security-definer function
-- owned by postgres may `set local ledgic.allow_audit_purge = 'on'` and delete ALL audit rows
-- of a demo org (whole chain, so verification of the new chain still starts at 000…0).
create or replace function public.audit_immutable() returns trigger language plpgsql
set search_path = '' as $$
begin
  if tg_op = 'DELETE'
     and current_setting('ledgic.allow_audit_purge', true) = 'on'
     and exists (select 1 from public.orgs o where o.id = old.org_id and o.is_demo) then
    return old;
  end if;
  raise exception 'audit_log is append-only' using errcode = 'P0001';
end $$;
create trigger audit_no_update before update or delete on public.audit_log
  for each row execute function public.audit_immutable();

create or replace function public.audit_no_truncate() returns trigger language plpgsql as $$
begin raise exception 'audit_log is append-only' using errcode = 'P0001'; end $$;
create trigger audit_no_truncate before truncate on public.audit_log
  for each statement execute function public.audit_no_truncate();

revoke update, delete, truncate on public.audit_log from public, anon, authenticated, service_role;

-- Verification: returns the first broken id, or null when the whole chain for the org is intact.
-- Security invoker: callers only see rows RLS lets them see (members see their own org's full chain).
create or replace function public.audit_verify(p_org uuid) returns bigint
language plpgsql stable set search_path = '' as $$
declare r record; prev text := repeat('0',64);
begin
  for r in select * from public.audit_log where org_id = p_org order by id loop
    if r.prev_hash is distinct from prev
       or r.hash <> public.audit_row_digest(prev, r.org_id, r.at, r.actor_type, r.actor_id,
                                            r.action, r.entity_type, r.entity_id, r.before, r.after) then
      return r.id;
    end if;
    prev := r.hash;
  end loop;
  return null;
end $$;

------------------------------------------------------------------------------------------------
-- 10. Lock everything down by default; policies are added in 0002 (RLS migration).
------------------------------------------------------------------------------------------------
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
  end loop;
end $$;
