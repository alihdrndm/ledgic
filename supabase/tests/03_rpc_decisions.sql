-- Decision RPCs: role limits, comments, amounts, SoD, run wake-up (contracts/rpc.md, 12-testing-qa §2).
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

select plan(38);

-- ids
-- E1 hero price variance ($88 at risk, run R1) · E2 $6,000 at risk · E3 fraud screen (vendor created by controller2)
-- E4 / E5 extraction reviews · E6 price variance on the invoice whose amounts the manager will edit

-- 1. role limits
select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000001');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'short_pay')$q$,
  '42501', 'LEDGIC_FORBIDDEN: Read-only access', 'viewer cannot decide');
select throws_ok($q$select public.rpc_confirm_fields('0a000000-0000-0000-0007-000000000004',
                    '[{"line_id":"0a000000-0000-0000-0008-000000000004","key":"qty","value":"4"}]')$q$,
  '42501', 'LEDGIC_FORBIDDEN: Read-only access', 'viewer cannot confirm fields');
select lives_ok($q$select public.rpc_mark_exception_viewed('0a000000-0000-0000-000a-000000000001')$q$, 'viewer can mark viewed');
select pg_temp.logout();

select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000002');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'short_pay')$q$,
  '42501', 'LEDGIC_FORBIDDEN: Needs AP manager', 'clerk cannot short-pay');
select pg_temp.logout();

select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000003');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000002', 'short_pay', 4000, 6000)$q$,
  '42501', 'LEDGIC_FORBIDDEN: Above your approval limit of $5,000.00', 'manager over limit forbidden');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000002', 'short_pay', 9999.99, 0.01)$q$,
  '42501', 'LEDGIC_FORBIDDEN: Above your approval limit of $5,000.00', 'a token hold cannot slip a large variance under the limit');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'merge')$q$,
  '22023', 'LEDGIC_INVALID: Action not allowed for this exception', 'action must fit the exception type');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'approve_as_is')$q$,
  '22023', 'LEDGIC_INVALID: A comment is required for this decision', 'approve as-is needs a comment');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'dispute', p_comment => '  ')$q$,
  '22023', 'LEDGIC_INVALID: A comment is required for this decision', 'blank comment rejected');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'short_pay', 2700, 100)$q$,
  '22023', 'LEDGIC_INVALID: Pay and hold must add up to the invoice total of $2,847.60', 'short-pay amounts must add up');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000003', 'release_hold',
                    p_comment => 'called them', p_extra => '{"verified_by_phone":true}')$q$,
  '42501', 'LEDGIC_FORBIDDEN: Needs controller', 'manager cannot release a fraud hold');
select throws_ok($q$select public.rpc_decide_exception('0b000000-0000-0000-000a-000000000001', 'short_pay')$q$,
  'P0002', 'LEDGIC_NOT_FOUND: Exception not found', 'other org exception is not found');

-- 2. happy path: short-pay at the recommendation wakes the parked run
select is(
  (public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'short_pay', p_time_spent => 4000) ->> 'run_id')::uuid,
  '0a000000-0000-0000-0009-000000000001'::uuid, 'short-pay returns the woken run');
select pg_temp.logout();

select results_eq(
  $q$select status, next_stage::text, wait_exception_id is null, next_attempt_at <= now(),
            context -> 'decision' ->> 'action', (context -> 'decision' ->> 'hold_amount')::numeric
       from public.pipeline_runs where id = '0a000000-0000-0000-0009-000000000001'$q$,
  $q$values ('running'::text, 'posting'::text, true, true, 'short_pay'::text, 88.00::numeric)$q$,
  'run is running again at posting with the decision in context');
select results_eq(
  $q$select action::text, pay_amount, hold_amount, time_spent_seconds, actor_id
       from public.approvals where exception_id = '0a000000-0000-0000-000a-000000000001'$q$,
  $q$values ('short_pay'::text, 2759.60::numeric(12,2), 88.00::numeric(12,2), 1800, 'aaaaaaaa-0000-0000-0000-000000000003'::uuid)$q$,
  'approval row: recommendation amounts, time capped at 30 min');
select is((select status::text from public.exceptions where id = '0a000000-0000-0000-000a-000000000001'), 'resolved', 'exception resolved');
select is((select status::text || '/' || touchless::text || '/' || human_touches from public.invoices
            where id = '0a000000-0000-0000-0007-000000000001'), 'approved/false/1', 'invoice approved and touched');
select is((select summary from public.pipeline_events where run_id = '0a000000-0000-0000-0009-000000000001'
            and status = 'resumed'), 'Short-pay by Elena Marsh', 'resumed event names the actor');
select is((select count(*) from public.audit_log where org_id = '0a000000-0000-0000-0000-000000000000'
            and action in ('decision.short_pay', 'exception.resolved', 'invoice.updated')), 3::bigint, 'decision audited');
select is((select first_viewed_at is not null from public.exceptions where id = '0a000000-0000-0000-000a-000000000001'),
  true, 'first_viewed_at recorded');

select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000004');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000001', 'short_pay')$q$,
  'P0001', 'LEDGIC_CONFLICT: This exception is already resolved', 'cannot decide twice');

-- 3. fraud hold: verification, vendor-creator SoD, controller release
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000003', 'release_hold', p_comment => 'ok')$q$,
  '22023', 'LEDGIC_INVALID: Confirm you verified the bank details with the vendor by phone', 'release needs phone verification');
select pg_temp.logout();
select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000005');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000003', 'release_hold',
                    p_comment => 'verified', p_extra => '{"verified_by_phone":true}')$q$,
  '42501', 'LEDGIC_FORBIDDEN: You created this vendor record', 'vendor creator cannot release the hold');
select pg_temp.logout();
select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000004');
select is(public.rpc_decide_exception('0a000000-0000-0000-000a-000000000003', 'release_hold',
            p_comment => 'Called the vendor on the number from the W-9', p_extra => '{"verified_by_phone":true}') ->> 'exception_status',
  'resolved', 'controller releases the fraud hold');

-- 4. dispute keeps the run parked
select is(public.rpc_decide_exception('0a000000-0000-0000-000a-000000000002', 'dispute', p_comment => 'Asked for credit') ->> 'exception_status',
  'disputed', 'dispute sets disputed');
select pg_temp.logout();
select is((select status from public.pipeline_runs where id = '0a000000-0000-0000-0009-000000000002'), 'waiting',
  'disputed run stays waiting');
select is((select status::text from public.exceptions where id = '0a000000-0000-0000-000a-000000000002'), 'disputed',
  'exception status disputed');

-- 5. extraction review confirm/correct + SoD on the same invoice
select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000002');
select is((public.rpc_confirm_fields('0a000000-0000-0000-0007-000000000004',
           '[{"line_id":"0a000000-0000-0000-0008-000000000004","key":"qty","value":"4"}]') ->> 'changed')::int,
  0, 'clerk confirms an unchanged value');
select throws_ok($q$select public.rpc_confirm_fields('0a000000-0000-0000-0007-000000000004', '[]')$q$,
  'P0001', 'LEDGIC_CONFLICT: No open extraction review for this invoice', 'review already closed');
select pg_temp.logout();
select results_eq(
  $q$select status, next_stage::text from public.pipeline_runs where id = '0a000000-0000-0000-0009-000000000004'$q$,
  $q$values ('running'::text, 'enrichment'::text)$q$, 'confirmed review resumes at enrichment');
select is((select (confidences ->> 'qty')::numeric from public.invoice_lines where id = '0a000000-0000-0000-0008-000000000004'),
  1.0, 'confirmed cell confidence is 1.0');

select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000003');
select throws_ok($q$select public.rpc_confirm_fields('0a000000-0000-0000-0007-000000000005',
                    '[{"field":"total","value":"-3"}]')$q$,
  '22023', 'LEDGIC_INVALID: total must be greater than 0', 'invalid amount rejected');
select is((public.rpc_confirm_fields('0a000000-0000-0000-0007-000000000005',
           '[{"field":"total","value":"1,100.00"},{"line_id":"0a000000-0000-0000-0008-000000000005","key":"qty","value":"11"}]') ->> 'changed')::int,
  2, 'manager corrects total and a quantity');
select is((select total from public.invoices where id = '0a000000-0000-0000-0007-000000000005'), 1100.00::numeric(12,2),
  'header correction mirrored into invoices.total');
select is((select count(*) from public.invoice_fields where invoice_id = '0a000000-0000-0000-0007-000000000005'
            and field = 'total' and source = 'human' and version = 2), 1::bigint, 'new human field version');
select throws_ok($q$select public.rpc_decide_exception('0a000000-0000-0000-000a-000000000006', 'short_pay', 1050, 50)$q$,
  '42501', 'LEDGIC_FORBIDDEN: You edited this invoice''s amounts, so someone else must approve it',
  'SoD: editor of monetary fields cannot decide');
select pg_temp.logout();
select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000004');
select is(public.rpc_decide_exception('0a000000-0000-0000-000a-000000000006', 'short_pay', 1050, 50) ->> 'exception_status',
  'resolved', 'another approver can decide');
select is((public.audit_verify_org('0a000000-0000-0000-0000-000000000000') ->> 'ok')::boolean, true,
  'audit chain intact after all decisions');
select pg_temp.logout();

select * from finish();
rollback;
