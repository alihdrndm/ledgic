-- Ledgic 0002: row-level security, membership helpers, privileges, storage bucket.
-- Spec: docs/handoff/05-database.md §10, 11-security.md, contracts/rpc.md "Helpers".
--
-- Model
--   * Every table has RLS enabled (0001). Members of an org can SELECT that org's rows.
--   * Child tables without org_id are visible through their parent (exists ... is_member()).
--   * authenticated/anon have NO insert/update/delete policies on any table and the table
--     privileges are revoked as well (defence in depth; truncate is not covered by RLS).
--     All browser writes go through security-definer RPCs (0003) that check role, limits, SoD.
--   * Core, MCP and the demo replay use the service role (bypasses RLS) or act "as a user"
--     (set local role authenticated + request.jwt.claims) to call the RPCs.

------------------------------------------------------------------------------------------------
-- 1. Helpers (security definer so policies can read memberships without recursion)
------------------------------------------------------------------------------------------------
create or replace function public.is_member(p_org uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.memberships m where m.org_id = p_org and m.user_id = auth.uid())
$$;

create or replace function public.has_role(p_org uuid, roles public.member_role[]) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.memberships m
                 where m.org_id = p_org and m.user_id = auth.uid() and m.role = any(roles))
$$;

create or replace function public.member_role_of(p_org uuid) returns public.member_role
language sql stable security definer set search_path = '' as $$
  select m.role from public.memberships m where m.org_id = p_org and m.user_id = auth.uid()
$$;

-- Numeric rank for comparisons: viewer 0 < ap_clerk 1 < ap_manager 2 < controller 3; admin counts as controller.
create or replace function public.role_rank(p_role public.member_role) returns int
language sql immutable set search_path = '' as $$
  select case p_role when 'viewer' then 0 when 'ap_clerk' then 1 when 'ap_manager' then 2
                     when 'controller' then 3 when 'admin' then 3 else -1 end
$$;

-- True when the caller shares at least one org with p_user (profiles visibility).
create or replace function public.shares_org(p_user uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select p_user = auth.uid() or exists (
    select 1 from public.memberships a join public.memberships b on a.org_id = b.org_id
    where a.user_id = auth.uid() and b.user_id = p_user)
$$;

-- Lenient uuid parse (null on garbage) for storage paths and jsonb ids.
create or replace function public.try_uuid(p text) returns uuid
language plpgsql immutable set search_path = '' as $$
begin
  return p::uuid;
exception when others then
  return null;
end $$;

revoke execute on function public.is_member(uuid), public.has_role(uuid, public.member_role[]),
  public.member_role_of(uuid), public.shares_org(uuid), public.role_rank(public.member_role),
  public.try_uuid(text) from public, anon;
grant execute on function public.is_member(uuid), public.has_role(uuid, public.member_role[]),
  public.member_role_of(uuid), public.shares_org(uuid), public.role_rank(public.member_role),
  public.try_uuid(text) to authenticated, service_role;

------------------------------------------------------------------------------------------------
-- 2. Privileges: browser roles are read-only on every table (writes only via RPCs)
------------------------------------------------------------------------------------------------
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
    execute format('revoke insert, update, delete, truncate, references, trigger on public.%I from anon, authenticated', t.tablename);
    execute format('revoke all on public.%I from anon', t.tablename);
  end loop;
end $$;
revoke usage, select, update on all sequences in schema public from anon, authenticated;

-- Future tables created by migrations get the same default (others must grant explicitly).
alter default privileges in schema public revoke insert, update, delete, truncate on tables from anon, authenticated;

------------------------------------------------------------------------------------------------
-- 3. Select policies
------------------------------------------------------------------------------------------------
-- Tables keyed by org_id
do $$
declare t text;
begin
  foreach t in array array[
    'org_settings','tolerance_policies','memberships','entities','locations','vendors','items','gl_accounts',
    'contracts','purchase_orders','goods_receipts','documents','invoices','duplicate_candidates','fraud_signals',
    'pipeline_runs','exceptions','approvals','exception_drafts','pipeline_events','dead_letters','erp_postings',
    'cost_ledger','eval_runs','integrations','ui_events','kb_documents','kb_chunks','copilot_cache','audit_log'
  ] loop
    execute format('create policy %I on public.%I for select to authenticated using (public.is_member(org_id))',
                   t || '_member_select', t);
  end loop;
end $$;

create policy orgs_member_select on public.orgs for select to authenticated using (public.is_member(id));

-- Child tables through their parent
create policy vendor_aliases_member_select on public.vendor_aliases for select to authenticated
  using (exists (select 1 from public.vendors v where v.id = vendor_id and public.is_member(v.org_id)));
create policy contract_prices_member_select on public.contract_prices for select to authenticated
  using (exists (select 1 from public.contracts c where c.id = contract_id and public.is_member(c.org_id)));
create policy po_lines_member_select on public.po_lines for select to authenticated
  using (exists (select 1 from public.purchase_orders p where p.id = po_id and public.is_member(p.org_id)));
create policy grn_lines_member_select on public.grn_lines for select to authenticated
  using (exists (select 1 from public.goods_receipts g where g.id = grn_id and public.is_member(g.org_id)));
create policy invoice_fields_member_select on public.invoice_fields for select to authenticated
  using (exists (select 1 from public.invoices i where i.id = invoice_id and public.is_member(i.org_id)));
create policy invoice_lines_member_select on public.invoice_lines for select to authenticated
  using (exists (select 1 from public.invoices i where i.id = invoice_id and public.is_member(i.org_id)));
create policy match_results_member_select on public.match_results for select to authenticated
  using (exists (select 1 from public.invoices i where i.id = invoice_id and public.is_member(i.org_id)));
create policy match_line_results_member_select on public.match_line_results for select to authenticated
  using (exists (select 1 from public.match_results m join public.invoices i on i.id = m.invoice_id
                 where m.id = match_result_id and public.is_member(i.org_id)));
create policy recommendations_member_select on public.recommendations for select to authenticated
  using (exists (select 1 from public.exceptions e where e.id = exception_id and public.is_member(e.org_id)));

-- Identity
create policy profiles_shared_select on public.profiles for select to authenticated
  using (public.shares_org(user_id));
create policy mcp_tokens_own_select on public.mcp_tokens for select to authenticated
  using (user_id = auth.uid() and public.is_member(org_id));

-- Global, non-sensitive
create policy prompt_versions_read on public.prompt_versions for select to authenticated using (true);
create policy llm_budget_read on public.llm_budget for select to authenticated using (true);
-- llm_budget_reservations, rate_limits: no policies (service role only).

-- integrations.vault_secret_id is never readable by browser roles (column privilege).
revoke select on public.integrations from authenticated;
grant select (id, org_id, provider, entity_id, status, config, last_sync_at, last_error)
  on public.integrations to authenticated;
-- mcp_tokens.token_hash stays server-side.
revoke select on public.mcp_tokens from authenticated;
grant select (id, user_id, org_id, name, scopes, created_at, revoked_at, last_used_at)
  on public.mcp_tokens to authenticated;

------------------------------------------------------------------------------------------------
-- 4. exceptions_public — the web's read path for exceptions (no secret columns remain in the
--    Ledgic schema; resume_url from the spec does not exist because there is no n8n).
------------------------------------------------------------------------------------------------
create or replace view public.exceptions_public with (security_invoker = true) as
  select e.id, e.org_id, e.invoice_id, e.run_id, e.type, e.status, e.amount_at_risk, e.reason,
         e.assigned_role, e.assigned_to, e.escalated, e.opened_at, e.first_viewed_at, e.sla_due_at, e.resolved_at
  from public.exceptions e;
revoke all on public.exceptions_public from anon;
grant select on public.exceptions_public to authenticated, service_role;

------------------------------------------------------------------------------------------------
-- 5. Storage: private bucket "documents", object path org/<org_id>/...
------------------------------------------------------------------------------------------------
do $$
begin
  if to_regclass('storage.buckets') is null then
    raise notice 'storage schema missing; skipping bucket setup';
    return;
  end if;

  insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  values ('documents', 'documents', false, 26214400,
          array['application/pdf','image/jpeg','image/png','image/webp','image/heic','image/heif','image/tiff'])
  on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
                                 allowed_mime_types = excluded.allowed_mime_types;

  execute $p$drop policy if exists ledgic_documents_member_read on storage.objects$p$;
  execute $p$create policy ledgic_documents_member_read on storage.objects for select to authenticated
    using (bucket_id = 'documents' and split_part(name, '/', 1) = 'org'
           and public.is_member(public.try_uuid(split_part(name, '/', 2))))$p$;

  execute $p$drop policy if exists ledgic_documents_member_upload on storage.objects$p$;
  execute $p$create policy ledgic_documents_member_upload on storage.objects for insert to authenticated
    with check (bucket_id = 'documents' and split_part(name, '/', 1) = 'org'
                and split_part(name, '/', 3) = 'uploads'
                and public.is_member(public.try_uuid(split_part(name, '/', 2))))$p$;
end $$;
