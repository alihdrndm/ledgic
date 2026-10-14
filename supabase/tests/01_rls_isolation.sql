-- Row-level security, isolation, browser write lockout, storage policy (contracts/rpc.md, 12-testing-qa §2).
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

-- ---------------------------------------------------------------------------------------------
-- Fixture (duplicated in each test file on purpose: every file runs in its own rolled-back txn)
--   org A (demo): viewer, clerk, manager, controller, controller2 (created the new vendor)
--   org B: outsider (ap_manager of B only)
-- ---------------------------------------------------------------------------------------------
insert into auth.users (id, aud, role, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'authenticated', 'authenticated', 'viewer@a.test'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'authenticated', 'authenticated', 'clerk@a.test'),
  ('aaaaaaaa-0000-0000-0000-000000000003', 'authenticated', 'authenticated', 'manager@a.test'),
  ('aaaaaaaa-0000-0000-0000-000000000004', 'authenticated', 'authenticated', 'controller@a.test'),
  ('aaaaaaaa-0000-0000-0000-000000000005', 'authenticated', 'authenticated', 'controller2@a.test'),
  ('bbbbbbbb-0000-0000-0000-000000000001', 'authenticated', 'authenticated', 'outsider@b.test');

insert into public.orgs (id, slug, name, is_demo, timezone) values
  ('0a000000-0000-0000-0000-000000000000', 'org-a', 'Org A', true, 'America/New_York'),
  ('0b000000-0000-0000-0000-000000000000', 'org-b', 'Org B', false, 'Europe/London');
insert into public.org_settings (org_id) values
  ('0a000000-0000-0000-0000-000000000000'), ('0b000000-0000-0000-0000-000000000000');
insert into public.tolerance_policies (org_id, pct, abs_amount, effective_from) values
  ('0a000000-0000-0000-0000-000000000000', 0.02, 25.00, now() - interval '1 day');
insert into public.profiles (user_id, full_name, initials) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'Vera Viewer', 'VV'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'Carl Clerk', 'CC'),
  ('aaaaaaaa-0000-0000-0000-000000000003', 'Elena Marsh', 'EM'),
  ('aaaaaaaa-0000-0000-0000-000000000004', 'Tom Iwu', 'TI'),
  ('aaaaaaaa-0000-0000-0000-000000000005', 'Ola Other', 'OO'),
  ('bbbbbbbb-0000-0000-0000-000000000001', 'Bob Outsider', 'BO');
insert into public.memberships (org_id, user_id, role) values
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000001', 'viewer'),
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000002', 'ap_clerk'),
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000003', 'ap_manager'),
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000004', 'controller'),
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000005', 'controller'),
  ('0b000000-0000-0000-0000-000000000000', 'bbbbbbbb-0000-0000-0000-000000000001', 'ap_manager');

insert into public.entities (id, org_id, name, short_code, erp) values
  ('0a000000-0000-0000-0001-000000000001', '0a000000-0000-0000-0000-000000000000', 'Entity 1', 'E1', 'quickbooks'),
  ('0b000000-0000-0000-0001-000000000001', '0b000000-0000-0000-0000-000000000000', 'Entity B', 'EB', 'netsuite');
insert into public.locations (id, org_id, entity_id, code, name) values
  ('0a000000-0000-0000-0002-000000000001', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0001-000000000001', 'RS', 'Riverside'),
  ('0b000000-0000-0000-0002-000000000001', '0b000000-0000-0000-0000-000000000000', '0b000000-0000-0000-0001-000000000001', 'XX', 'Elsewhere');
insert into public.vendors (id, org_id, display_name, created_by) values
  ('0a000000-0000-0000-0003-000000000001', '0a000000-0000-0000-0000-000000000000', 'Protein Supplier', null),
  ('0a000000-0000-0000-0003-000000000002', '0a000000-0000-0000-0000-000000000000', 'Unlisted Supplier', 'aaaaaaaa-0000-0000-0000-000000000005'),
  ('0b000000-0000-0000-0003-000000000001', '0b000000-0000-0000-0000-000000000000', 'B Vendor', null);
insert into public.vendor_aliases (vendor_id, alias) values
  ('0a000000-0000-0000-0003-000000000001', 'PROTEIN SUPPLIER'), ('0b000000-0000-0000-0003-000000000001', 'B VENDOR');
insert into public.items (id, org_id, item_key, description, uom) values
  ('0a000000-0000-0000-0004-000000000001', '0a000000-0000-0000-0000-000000000000', 'PS-0001', 'Shrimp', 'lb'),
  ('0b000000-0000-0000-0004-000000000001', '0b000000-0000-0000-0000-000000000000', 'B-0001', 'Widget', 'ea');
insert into public.purchase_orders (id, org_id, entity_id, location_id, vendor_id, po_number, ordered_at, total) values
  ('0a000000-0000-0000-0005-000000000001', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0001-000000000001',
   '0a000000-0000-0000-0002-000000000001', '0a000000-0000-0000-0003-000000000001', 'PO-1', now(), 2759.60),
  ('0b000000-0000-0000-0005-000000000001', '0b000000-0000-0000-0000-000000000000', '0b000000-0000-0000-0001-000000000001',
   '0b000000-0000-0000-0002-000000000001', '0b000000-0000-0000-0003-000000000001', 'PO-B', now(), 10.00);
insert into public.po_lines (po_id, line_no, description, qty, uom, unit_price, amount) values
  ('0a000000-0000-0000-0005-000000000001', 1, 'Shrimp', 200, 'lb', 3.68, 736.00),
  ('0b000000-0000-0000-0005-000000000001', 1, 'Widget', 1, 'ea', 10, 10.00);

insert into public.documents (id, org_id, channel, storage_path, sha256, mime) values
  ('0a000000-0000-0000-0006-000000000001', '0a000000-0000-0000-0000-000000000000', 'email', 'org/0a000000-0000-0000-0000-000000000000/d1.pdf', 'sha-a1', 'application/pdf'),
  ('0a000000-0000-0000-0006-000000000002', '0a000000-0000-0000-0000-000000000000', 'email', 'org/0a000000-0000-0000-0000-000000000000/d2.pdf', 'sha-a2', 'application/pdf'),
  ('0a000000-0000-0000-0006-000000000003', '0a000000-0000-0000-0000-000000000000', 'email', 'org/0a000000-0000-0000-0000-000000000000/d3.pdf', 'sha-a3', 'application/pdf'),
  ('0a000000-0000-0000-0006-000000000004', '0a000000-0000-0000-0000-000000000000', 'photo', 'org/0a000000-0000-0000-0000-000000000000/d4.jpg', 'sha-a4', 'image/jpeg'),
  ('0a000000-0000-0000-0006-000000000005', '0a000000-0000-0000-0000-000000000000', 'photo', 'org/0a000000-0000-0000-0000-000000000000/d5.jpg', 'sha-a5', 'image/jpeg'),
  ('0b000000-0000-0000-0006-000000000001', '0b000000-0000-0000-0000-000000000000', 'email', 'org/0b000000-0000-0000-0000-000000000000/d1.pdf', 'sha-b1', 'application/pdf');

-- I1 hero price variance, I2 above the manager limit, I3 fraud screen, I4 review, I5 review then variance (SoD)
insert into public.invoices (id, org_id, document_id, vendor_id, entity_id, location_id, po_id, invoice_number, total, status, received_at) values
  ('0a000000-0000-0000-0007-000000000001', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000001', '0a000000-0000-0000-0003-000000000001', '0a000000-0000-0000-0001-000000000001', '0a000000-0000-0000-0002-000000000001', '0a000000-0000-0000-0005-000000000001', 'PS-88214', 2847.60, 'awaiting_decision', now()),
  ('0a000000-0000-0000-0007-000000000002', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000002', '0a000000-0000-0000-0003-000000000001', '0a000000-0000-0000-0001-000000000001', '0a000000-0000-0000-0002-000000000001', null, 'PS-90000', 10000.00, 'awaiting_decision', now()),
  ('0a000000-0000-0000-0007-000000000003', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000003', '0a000000-0000-0000-0003-000000000002', '0a000000-0000-0000-0001-000000000001', '0a000000-0000-0000-0002-000000000001', null, 'NV-0001', 2214.85, 'awaiting_decision', now()),
  ('0a000000-0000-0000-0007-000000000004', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000004', '0a000000-0000-0000-0003-000000000001', '0a000000-0000-0000-0001-000000000001', '0a000000-0000-0000-0002-000000000001', null, 'PR-2214', 491.60, 'in_review', now()),
  ('0a000000-0000-0000-0007-000000000005', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000005', '0a000000-0000-0000-0003-000000000001', '0a000000-0000-0000-0001-000000000001', '0a000000-0000-0000-0002-000000000001', null, 'PS-77777', 1000.00, 'in_review', now()),
  ('0b000000-0000-0000-0007-000000000001', '0b000000-0000-0000-0000-000000000000', '0b000000-0000-0000-0006-000000000001', '0b000000-0000-0000-0003-000000000001', '0b000000-0000-0000-0001-000000000001', '0b000000-0000-0000-0002-000000000001', '0b000000-0000-0000-0005-000000000001', 'B-1', 10.00, 'awaiting_decision', now());

insert into public.invoice_lines (id, invoice_id, line_no, description, qty, uom, unit_price, amount, confidences) values
  ('0a000000-0000-0000-0008-000000000001', '0a000000-0000-0000-0007-000000000001', 1, 'Shrimp', 200, 'lb', 4.12, 824.00, '{"qty":0.99,"unit_price":0.99,"amount":0.99}'),
  ('0a000000-0000-0000-0008-000000000004', '0a000000-0000-0000-0007-000000000004', 1, 'Heirloom tomato 10lb', 4, 'cs', 31.25, 125.00, '{"qty":0.71,"unit_price":0.80,"amount":0.86}'),
  ('0a000000-0000-0000-0008-000000000005', '0a000000-0000-0000-0007-000000000005', 1, 'Shrimp', 10, 'lb', 100, 1000.00, '{"qty":0.70,"unit_price":0.95,"amount":0.95}'),
  ('0b000000-0000-0000-0008-000000000001', '0b000000-0000-0000-0007-000000000001', 1, 'Widget', 1, 'ea', 10, 10.00, '{"qty":1}');
insert into public.invoice_fields (invoice_id, field, value, confidence, source, version) values
  ('0a000000-0000-0000-0007-000000000004', 'total', '491.60', 0.99, 'llm', 1),
  ('0a000000-0000-0000-0007-000000000005', 'total', '1000.00', 0.70, 'llm', 1),
  ('0b000000-0000-0000-0007-000000000001', 'total', '10.00', 0.99, 'llm', 1);

insert into public.pipeline_runs (id, org_id, document_id, invoice_id, status, current_stage, next_attempt_at) values
  ('0a000000-0000-0000-0009-000000000001', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000001', '0a000000-0000-0000-0007-000000000001', 'waiting', 'approval', null),
  ('0a000000-0000-0000-0009-000000000002', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000002', '0a000000-0000-0000-0007-000000000002', 'waiting', 'approval', null),
  ('0a000000-0000-0000-0009-000000000003', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000003', '0a000000-0000-0000-0007-000000000003', 'waiting', 'screening', null),
  ('0a000000-0000-0000-0009-000000000004', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000004', '0a000000-0000-0000-0007-000000000004', 'waiting', 'review', null),
  ('0a000000-0000-0000-0009-000000000005', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000005', '0a000000-0000-0000-0007-000000000005', 'waiting', 'review', null),
  ('0b000000-0000-0000-0009-000000000001', '0b000000-0000-0000-0000-000000000000', '0b000000-0000-0000-0006-000000000001', '0b000000-0000-0000-0007-000000000001', 'waiting', 'approval', null);

insert into public.exceptions (id, org_id, invoice_id, run_id, type, amount_at_risk, reason, assigned_role, sla_due_at) values
  ('0a000000-0000-0000-000a-000000000001', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0007-000000000001', '0a000000-0000-0000-0009-000000000001', 'price_variance', 88.00, 'Shrimp billed $4.12/lb against $3.68 contract', 'ap_manager', now() + interval '1 day'),
  ('0a000000-0000-0000-000a-000000000002', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0007-000000000002', '0a000000-0000-0000-0009-000000000002', 'price_variance', 6000.00, 'Big variance', 'controller', now() + interval '1 day'),
  ('0a000000-0000-0000-000a-000000000003', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0007-000000000003', '0a000000-0000-0000-0009-000000000003', 'new_vendor_screen', 2214.85, 'Bank details differ from W-9', 'controller', now() + interval '1 day'),
  ('0a000000-0000-0000-000a-000000000004', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0007-000000000004', '0a000000-0000-0000-0009-000000000004', 'extraction_review', 0, 'Quantity unclear', 'ap_clerk', now() + interval '1 day'),
  ('0a000000-0000-0000-000a-000000000005', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0007-000000000005', '0a000000-0000-0000-0009-000000000005', 'extraction_review', 0, 'Total unclear', 'ap_clerk', now() + interval '1 day'),
  ('0a000000-0000-0000-000a-000000000006', '0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0007-000000000005', null, 'price_variance', 50.00, 'Shrimp over contract', 'ap_manager', now() + interval '1 day'),
  ('0b000000-0000-0000-000a-000000000001', '0b000000-0000-0000-0000-000000000000', '0b000000-0000-0000-0007-000000000001', '0b000000-0000-0000-0009-000000000001', 'price_variance', 1.00, 'B variance', 'ap_manager', now() + interval '1 day');

update public.pipeline_runs r set wait_exception_id = e.id
  from public.exceptions e where e.run_id = r.id;

insert into public.recommendations (exception_id, action, pay_amount, hold_amount, confidence, reasons) values
  ('0a000000-0000-0000-000a-000000000001', 'short_pay', 2759.60, 88.00, 0.94, '["Contract clause 4.2 fixes shrimp at $3.68/lb"]');

insert into public.pipeline_events (org_id, run_id, stage, status, summary) values
  ('0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0009-000000000001', 'intake', 'succeeded', 'Received'),
  ('0b000000-0000-0000-0000-000000000000', '0b000000-0000-0000-0009-000000000001', 'intake', 'succeeded', 'Received');
insert into public.audit_log (org_id, actor_type, actor_id, action, entity_type, entity_id, after) values
  ('0a000000-0000-0000-0000-000000000000', 'core', 'core', 'invoice.created', 'invoice', '0a000000-0000-0000-0007-000000000001', '{"total":"2847.60"}'),
  ('0b000000-0000-0000-0000-000000000000', 'core', 'core', 'invoice.created', 'invoice', '0b000000-0000-0000-0007-000000000001', '{"total":"10.00"}');
insert into public.cost_ledger (org_id, kind, amount_usd) values
  ('0a000000-0000-0000-0000-000000000000', 'llm', 0.01), ('0b000000-0000-0000-0000-000000000000', 'llm', 0.02);
insert into public.integrations (org_id, provider, status, vault_secret_id) values
  ('0a000000-0000-0000-0000-000000000000', 'quickbooks', 'connected', gen_random_uuid());

-- Act as a Supabase user for the rest of the transaction (reset role to go back to postgres).
create function pg_temp.login(p_uid uuid) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', p_uid, 'role', 'authenticated')::text, true);
  execute 'set local role authenticated';
end $$;
create function pg_temp.logout() returns void language plpgsql as $$
begin
  execute 'reset role';
  perform set_config('request.jwt.claims', '', true);
end $$;
-- ---------------------------------------------------------------------------------------------

-- Every org-scoped table this fixture populates, for the cross-org sweep.
create function pg_temp.rows_of_org(p_org uuid) returns bigint language plpgsql as $$
declare t text; n bigint := 0; c bigint;
begin
  foreach t in array array['orgs','org_settings','tolerance_policies','memberships','entities','locations','vendors',
    'items','purchase_orders','documents','invoices','pipeline_runs','exceptions','pipeline_events','audit_log',
    'cost_ledger','integrations'] loop
    if t = 'orgs' then
      execute 'select count(*) from public.orgs where id = $1' into c using p_org;
    elsif t = 'integrations' then
      execute 'select count(id) from public.integrations where org_id = $1' into c using p_org;
    else
      execute format('select count(*) from public.%I where org_id = $1', t) into c using p_org;
    end if;
    n := n + c;
  end loop;
  -- child tables through their parents
  select n + (select count(*) from public.vendor_aliases a join public.vendors v on v.id = a.vendor_id where v.org_id = p_org)
           + (select count(*) from public.po_lines l join public.purchase_orders p on p.id = l.po_id where p.org_id = p_org)
           + (select count(*) from public.invoice_lines l join public.invoices i on i.id = l.invoice_id where i.org_id = p_org)
           + (select count(*) from public.invoice_fields f join public.invoices i on i.id = f.invoice_id where i.org_id = p_org)
    into n;
  return n;
end $$;

select plan(23);

-- 1. RLS on every table
select is(
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity),
  0::bigint, 'RLS is enabled on every public table');
select is(
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r'
      and not exists (select 1 from pg_policies p where p.schemaname = 'public' and p.tablename = c.relname)
      and c.relname not in ('llm_budget_reservations', 'rate_limits')),
  0::bigint, 'every public table except server-only ones has a select policy');
select is(
  (select count(*) from pg_policies where schemaname = 'public' and cmd <> 'SELECT'),
  0::bigint, 'no insert/update/delete policies exist for browser roles');

-- 2. isolation
select pg_temp.login('bbbbbbbb-0000-0000-0000-000000000001');
select is(pg_temp.rows_of_org('0a000000-0000-0000-0000-000000000000'), 0::bigint, 'org B member sees no org A rows');
select cmp_ok(pg_temp.rows_of_org('0b000000-0000-0000-0000-000000000000'), '>', 10::bigint, 'org B member sees own rows');
select is((select count(*) from public.exceptions_public where org_id = '0a000000-0000-0000-0000-000000000000'), 0::bigint,
  'exceptions_public is isolated');
select is((select count(*) from public.v_exception_queue), 1::bigint, 'v_exception_queue only shows own org');
select is((select count(*) from public.v_ops_period where org_id = '0a000000-0000-0000-0000-000000000000'), 0::bigint,
  'MV wrapper filters other orgs');
select is((select count(*) from public.profiles), 1::bigint, 'profiles: only people sharing an org');
select pg_temp.logout();

select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000001');
select is(pg_temp.rows_of_org('0b000000-0000-0000-0000-000000000000'), 0::bigint, 'org A viewer sees no org B rows');
select cmp_ok(pg_temp.rows_of_org('0a000000-0000-0000-0000-000000000000'), '>', 20::bigint, 'org A viewer sees own rows');
select is((select count(*) from public.profiles), 5::bigint, 'profiles of co-members are visible');

-- 3. browser roles cannot write pipeline tables
select throws_ok($q$insert into public.invoices (org_id, document_id, received_at)
                   values ('0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-0006-000000000001', now())$q$,
  '42501', null, 'authenticated cannot insert invoices');
select throws_ok($q$update public.invoices set total = 1$q$, '42501', null, 'authenticated cannot update invoices');
select throws_ok($q$delete from public.exceptions$q$, '42501', null, 'authenticated cannot delete exceptions');
select throws_ok($q$insert into public.approvals (org_id, exception_id, actor_id, action)
                   values ('0a000000-0000-0000-0000-000000000000', '0a000000-0000-0000-000a-000000000001',
                           'aaaaaaaa-0000-0000-0000-000000000001', 'approve_as_is')$q$,
  '42501', null, 'authenticated cannot insert approvals');
select throws_ok($q$update public.pipeline_runs set status = 'running'$q$, '42501', null, 'authenticated cannot wake runs directly');
select throws_ok($q$truncate public.pipeline_events$q$, '42501', null, 'authenticated cannot truncate');
select throws_ok($q$select vault_secret_id from public.integrations$q$, '42501', null, 'vault_secret_id is not readable');
select throws_ok($q$select public.demo_purge_org('0a000000-0000-0000-0000-000000000000')$q$, '42501', null,
  'authenticated cannot purge');
select throws_ok($q$select * from public.mv_ops_period$q$, '42501', null, 'materialized views are not readable directly');
select pg_temp.logout();

-- 4. anon has nothing
set local role anon;
select throws_ok($q$select count(*) from public.invoices$q$, '42501', null, 'anon cannot read tables');
reset role;

-- 5. storage: members read their org's objects only
insert into storage.objects (bucket_id, name) values
  ('documents', 'org/0a000000-0000-0000-0000-000000000000/docs/a.pdf'),
  ('documents', 'org/0b000000-0000-0000-0000-000000000000/docs/b.pdf');
select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000003');
select results_eq($q$select name from storage.objects where bucket_id = 'documents' order by name$q$,
  $q$values ('org/0a000000-0000-0000-0000-000000000000/docs/a.pdf'::text)$q$, 'storage: member sees only own org objects');
select pg_temp.logout();

select * from finish();
rollback;
