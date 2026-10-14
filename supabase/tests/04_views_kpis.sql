-- KPI / read-model views on a small fixture with known counts (12-testing-qa §2).
-- Timestamps are offsets from the org-local midnight (t0) so "today" is stable at any hour.
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(41);
delete from public.llm_budget where day = (now() at time zone 'utc')::date;

insert into auth.users (id, aud, role, email) values
  ('cccccccc-0000-0000-0000-000000000001', 'authenticated', 'authenticated', 'm@k.test'),
  ('cccccccc-0000-0000-0000-000000000002', 'authenticated', 'authenticated', 'x@other.test');
insert into public.orgs (id, slug, name, is_demo, timezone) values
  ('0c000000-0000-0000-0000-000000000000', 'org-k', 'Org K', true, 'America/New_York'),
  ('0d000000-0000-0000-0000-000000000000', 'org-x', 'Org X', false, 'UTC');
insert into public.org_settings (org_id) values ('0c000000-0000-0000-0000-000000000000');
insert into public.tolerance_policies (org_id, pct, abs_amount, effective_from) values
  ('0c000000-0000-0000-0000-000000000000', 0.02, 25.00, now() - interval '1 day');
insert into public.profiles (user_id, full_name, initials) values
  ('cccccccc-0000-0000-0000-000000000001', 'Kim Manager', 'KM'), ('cccccccc-0000-0000-0000-000000000002', 'Xavier', 'XX');
insert into public.memberships (org_id, user_id, role) values
  ('0c000000-0000-0000-0000-000000000000', 'cccccccc-0000-0000-0000-000000000001', 'ap_manager'),
  ('0d000000-0000-0000-0000-000000000000', 'cccccccc-0000-0000-0000-000000000002', 'admin');

create function pg_temp.t(p interval) returns timestamptz language sql as $$
  select t0 + p from public.v_org_today where org_id = '0c000000-0000-0000-0000-000000000000'
$$;
create function pg_temp.login(p_uid uuid) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', p_uid, 'role', 'authenticated')::text, true);
  execute 'set local role authenticated';
end $$;

insert into public.entities (id, org_id, name, short_code, erp) values
  ('0c000000-0000-0000-0001-000000000001', '0c000000-0000-0000-0000-000000000000', 'Entity 1', 'E1', 'quickbooks'),
  ('0c000000-0000-0000-0001-000000000002', '0c000000-0000-0000-0000-000000000000', 'Entity 3', 'E3', 'netsuite');
insert into public.locations (id, org_id, entity_id, code, name) values
  ('0c000000-0000-0000-0002-000000000001', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0001-000000000001', 'RS', 'Riverside'),
  ('0c000000-0000-0000-0002-000000000002', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0001-000000000002', 'CM', 'Commissary');
insert into public.vendors (id, org_id, display_name) values
  ('0c000000-0000-0000-0003-000000000001', '0c000000-0000-0000-0000-000000000000', 'Produce Supplier');
insert into public.gl_accounts (id, org_id, entity_id, number, name) values
  ('0c000000-0000-0000-000b-000000000001', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0001-000000000001', '5000', 'COGS-Food');
insert into public.purchase_orders (id, org_id, entity_id, location_id, vendor_id, po_number, ordered_at, total) values
  ('0c000000-0000-0000-0005-000000000001', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0001-000000000001',
   '0c000000-0000-0000-0002-000000000001', '0c000000-0000-0000-0003-000000000001', 'PO-K1', now() - interval '2 days', 100.00);
insert into public.po_lines (id, po_id, line_no, description, qty, uom, unit_price, amount) values
  ('0c000000-0000-0000-000c-000000000001', '0c000000-0000-0000-0005-000000000001', 1, 'Lemons', 10, 'cs', 10, 100.00);
insert into public.goods_receipts (id, org_id, po_id, grn_number, received_at) values
  ('0c000000-0000-0000-000d-000000000001', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0005-000000000001', 'GRN-K1', now() - interval '1 day');
insert into public.grn_lines (grn_id, po_line_id, qty_received, uom) values
  ('0c000000-0000-0000-000d-000000000001', '0c000000-0000-0000-000c-000000000001', 10, 'cs');

-- documents: 3 email, 1 photo, 1 portal received today
insert into public.documents (id, org_id, channel, storage_path, sha256, mime, received_at) values
  ('0c000000-0000-0000-0006-000000000001', '0c000000-0000-0000-0000-000000000000', 'email', 'org/k/1.pdf', 'k1', 'application/pdf', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0006-000000000002', '0c000000-0000-0000-0000-000000000000', 'email', 'org/k/2.pdf', 'k2', 'application/pdf', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0006-000000000003', '0c000000-0000-0000-0000-000000000000', 'photo', 'org/k/3.jpg', 'k3', 'image/jpeg', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0006-000000000004', '0c000000-0000-0000-0000-000000000000', 'portal', 'org/k/4.pdf', 'k4', 'application/pdf', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0006-000000000005', '0c000000-0000-0000-0000-000000000000', 'email', 'org/k/5.pdf', 'k5', 'application/pdf', pg_temp.t('1 hour'));

-- I1 touchless posted · I2 open price variance · I3 below gate · I4 seeded history (no run) · I5 short-paid, posted
insert into public.invoices (id, org_id, document_id, vendor_id, entity_id, location_id, po_id, invoice_number, total,
                             status, touchless, received_at, posted_at) values
  ('0c000000-0000-0000-0007-000000000001', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000001', '0c000000-0000-0000-0003-000000000001', '0c000000-0000-0000-0001-000000000001', '0c000000-0000-0000-0002-000000000001', '0c000000-0000-0000-0005-000000000001', 'K-1', 100.00, 'posted', true, pg_temp.t('1 hour'), pg_temp.t('2 hours')),
  ('0c000000-0000-0000-0007-000000000002', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000002', '0c000000-0000-0000-0003-000000000001', '0c000000-0000-0000-0001-000000000001', '0c000000-0000-0000-0002-000000000001', '0c000000-0000-0000-0005-000000000001', 'K-2', 188.00, 'awaiting_decision', null, pg_temp.t('1 hour'), null),
  ('0c000000-0000-0000-0007-000000000003', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000003', '0c000000-0000-0000-0003-000000000001', '0c000000-0000-0000-0001-000000000002', '0c000000-0000-0000-0002-000000000002', null, 'K-3', 50.00, 'in_review', null, pg_temp.t('1 hour'), null),
  ('0c000000-0000-0000-0007-000000000004', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000004', '0c000000-0000-0000-0003-000000000001', '0c000000-0000-0000-0001-000000000001', '0c000000-0000-0000-0002-000000000001', null, 'K-H', 70.00, 'posted', true, pg_temp.t('1 hour'), pg_temp.t('2 hours')),
  ('0c000000-0000-0000-0007-000000000005', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000005', '0c000000-0000-0000-0003-000000000001', '0c000000-0000-0000-0001-000000000001', '0c000000-0000-0000-0002-000000000001', '0c000000-0000-0000-0005-000000000001', 'K-5', 161.60, 'posted', false, pg_temp.t('1 hour'), pg_temp.t('3 hours'));

insert into public.invoice_lines (id, invoice_id, line_no, description, qty, uom, unit_price, amount, confidences, gl_account_id, po_line_id) values
  ('0c000000-0000-0000-0008-000000000001', '0c000000-0000-0000-0007-000000000001', 1, 'Lemons', 10, 'cs', 10, 100.00, '{"qty":0.99,"amount":0.99}', '0c000000-0000-0000-000b-000000000001', '0c000000-0000-0000-000c-000000000001'),
  ('0c000000-0000-0000-0008-000000000002', '0c000000-0000-0000-0007-000000000002', 1, 'Lemons', 10, 'cs', 18.80, 188.00, '{"qty":0.99,"amount":0.99}', null, '0c000000-0000-0000-000c-000000000001'),
  ('0c000000-0000-0000-0008-000000000003', '0c000000-0000-0000-0007-000000000003', 1, 'Tomato', 4, 'cs', 12.50, 50.00, '{"qty":0.71,"amount":0.90}', null, null),
  ('0c000000-0000-0000-0008-000000000004', '0c000000-0000-0000-0007-000000000004', 1, 'Lemons', 7, 'cs', 10, 70.00, '{"qty":1}', '0c000000-0000-0000-000b-000000000001', null),
  ('0c000000-0000-0000-0008-000000000005', '0c000000-0000-0000-0007-000000000005', 1, 'Lemons', 10, 'cs', 16.16, 161.60, '{"qty":1}', '0c000000-0000-0000-000b-000000000001', null);
insert into public.invoice_fields (invoice_id, field, value, confidence, source, version) values
  ('0c000000-0000-0000-0007-000000000003', 'total', '50.00', 0.60, 'llm', 1),
  ('0c000000-0000-0000-0007-000000000003', 'vendor_name', 'Produce Supplier', 0.99, 'llm', 1),
  ('0c000000-0000-0000-0007-000000000003', 'bank_details', null, 0.00, 'llm', 1),
  ('0c000000-0000-0000-0007-000000000001', 'total', '100.00', 0.99, 'llm', 1);

insert into public.pipeline_runs (id, org_id, document_id, invoice_id, status, current_stage, started_at, finished_at, workflow_version) values
  ('0c000000-0000-0000-0009-000000000001', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000001', '0c000000-0000-0000-0007-000000000001', 'succeeded', 'close', pg_temp.t('1 hour'), pg_temp.t('1 hour 16 seconds'), 'v14'),
  ('0c000000-0000-0000-0009-000000000002', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000002', '0c000000-0000-0000-0007-000000000002', 'waiting', 'approval', pg_temp.t('1 hour 1 minute'), null, 'v14'),
  ('0c000000-0000-0000-0009-000000000003', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000003', '0c000000-0000-0000-0007-000000000003', 'waiting', 'review', pg_temp.t('1 hour 2 minutes'), null, 'v14'),
  ('0c000000-0000-0000-0009-000000000005', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0006-000000000005', '0c000000-0000-0000-0007-000000000005', 'succeeded', 'close', pg_temp.t('1 hour 3 minutes'), pg_temp.t('3 hours'), 'v15');

insert into public.pipeline_events (org_id, run_id, stage, status, duration_ms, summary, detail, at) values
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000001', 'extraction', 'succeeded', 10000, 'Extracted', '{"gate_passed":true}', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000001', 'screening', 'succeeded', 100, 'Screened', '{}', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000002', 'extraction', 'succeeded', 12000, 'Extracted', '{"gate_passed":true}', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000003', 'extraction', 'succeeded', 20000, 'Extracted', '{"gate_passed":false}', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000005', 'extraction', 'succeeded', 14000, 'Extracted', '{"gate_passed":true}', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000005', 'screening', 'succeeded', 100, 'Screened', '{}', pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0009-000000000005', 'approval', 'resumed', null, 'Short-pay by Kim Manager',
   '{"actor_id":"cccccccc-0000-0000-0000-000000000001"}', pg_temp.t('1 hour 13 minutes'));

insert into public.match_results (id, invoice_id, verdict, tolerance_pct, tolerance_abs, expected_total, total_delta, lines_verified, lines_total, duration_ms) values
  ('0c000000-0000-0000-000e-000000000001', '0c000000-0000-0000-0007-000000000001', 'clean', 0.02, 25, 100, 0, 1, 1, 40),
  ('0c000000-0000-0000-000e-000000000002', '0c000000-0000-0000-0007-000000000002', 'price_variance', 0.02, 25, 100, 88, 0, 1, 40),
  ('0c000000-0000-0000-000e-000000000005', '0c000000-0000-0000-0007-000000000005', 'price_variance', 0.02, 25, 100, 61.60, 0, 1, 40);
insert into public.match_line_results (match_result_id, invoice_line_id, po_line_id, grn_qty, expected_unit_price, expected_source,
                                       expected_amount, delta_amount, delta_pct, allowed_amount, verdict) values
  ('0c000000-0000-0000-000e-000000000002', '0c000000-0000-0000-0008-000000000002', '0c000000-0000-0000-000c-000000000001', 10, 10, 'po', 100, 88, 0.88, 2, 'price_variance');

insert into public.exceptions (id, org_id, invoice_id, run_id, type, status, amount_at_risk, reason, sla_due_at, opened_at, resolved_at) values
  ('0c000000-0000-0000-000a-000000000002', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0007-000000000002', '0c000000-0000-0000-0009-000000000002', 'price_variance', 'open', 88.00, 'Lemons billed $18.80 vs PO $10.00', now() + interval '1 day', pg_temp.t('1 hour'), null),
  ('0c000000-0000-0000-000a-000000000003', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0007-000000000003', '0c000000-0000-0000-0009-000000000003', 'extraction_review', 'open', 0, 'Quantity unclear', now() + interval '1 day', pg_temp.t('1 hour'), null),
  ('0c000000-0000-0000-000a-000000000005', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0007-000000000005', '0c000000-0000-0000-0009-000000000005', 'price_variance', 'resolved', 61.60, 'Lemons billed $16.16 vs contract $10.00', now() + interval '1 day', pg_temp.t('1 hour'), pg_temp.t('1 hour 10 minutes'));
insert into public.recommendations (exception_id, action, pay_amount, hold_amount, confidence, reasons) values
  ('0c000000-0000-0000-000a-000000000002', 'short_pay', 100.00, 88.00, 0.80, '["PO price $10.00"]');
insert into public.approvals (id, org_id, exception_id, actor_id, action, pay_amount, hold_amount, decided_at, time_spent_seconds) values
  ('0c000000-0000-0000-000f-000000000005', '0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-000a-000000000005',
   'cccccccc-0000-0000-0000-000000000001', 'short_pay', 100.00, 61.60, pg_temp.t('1 hour 10 minutes'), 600);
insert into public.audit_log (org_id, actor_type, actor_id, action, entity_type, entity_id, after) values
  ('0c000000-0000-0000-0000-000000000000', 'user', 'cccccccc-0000-0000-0000-000000000001', 'decision.short_pay', 'approval',
   '0c000000-0000-0000-000f-000000000005', '{"invoice_id":"0c000000-0000-0000-0007-000000000005"}');
insert into public.erp_postings (org_id, invoice_id, system, status, external_id, request, posted_at) values
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0007-000000000001', 'quickbooks', 'posted', 'JE-1', '{}', pg_temp.t('2 hours')),
  ('0c000000-0000-0000-0000-000000000000', '0c000000-0000-0000-0007-000000000005', 'quickbooks', 'posted', 'JE-2', '{}', pg_temp.t('3 hours'));
insert into public.cost_ledger (org_id, kind, amount_usd, at) values
  ('0c000000-0000-0000-0000-000000000000', 'llm', 0.20, pg_temp.t('1 hour')),
  ('0c000000-0000-0000-0000-000000000000', 'llm', 0.10, pg_temp.t('1 hour'));

insert into public.prompt_versions (id, model, deployed_at) values ('p-test', 'gpt-4.1-mini', date_trunc('week', now()) - interval '10 weeks' + interval '1 day');
insert into public.eval_runs (org_id, week_start, prompt_version, sample_size, fields_labeled, fields_correct, by_field)
select '0c000000-0000-0000-0000-000000000000', (date_trunc('week', now()) - make_interval(weeks => k))::date, 'p-test', 200, 1000, 950 + k, '{}'
from generate_series(1, 13) k;

-- ------------------------------------------------------------------ plain views (service context)
select results_eq(
  $q$select received, extracted_above_gate, enriched_po_linked, matched_clean, routed_to_people
       from v_pipeline_today where org_id = '0c000000-0000-0000-0000-000000000000'$q$,
  $q$values (4, 3, 3, 1, 3)$q$, 'v_pipeline_today attrition');
select results_eq(
  $q$select received from v_pipeline_today where org_id = '0d000000-0000-0000-0000-000000000000'$q$,
  $q$values (0)$q$, 'v_pipeline_today zero row for an idle org');
select results_eq(
  $q$select v.channel::text, v.count from v_channel_today v where v.org_id = '0c000000-0000-0000-0000-000000000000' order by v.channel$q$,
  $q$values ('email', 3), ('photo', 1), ('portal', 1), ('edi', 0), ('upload', 0)$q$, 'v_channel_today zero-filled');
select results_eq(
  $q$select extraction_auto_passed, extraction_below_gate, extraction_median_seconds, vendor_resolved, po_linked, gl_predicted,
            duplicate_screened, match_clean, match_price_variance, match_qty_mismatch, match_no_po, awaiting_person,
            posted_quickbooks, posted_netsuite
       from v_stage_today where org_id = '0c000000-0000-0000-0000-000000000000'$q$,
  $q$values (3, 1, 13.0::numeric(8,1), 5, 3, 3, 2, 1, 2, 0, 0, 2, 2, 0)$q$, 'v_stage_today counts');
select results_eq(
  $q$select tolerance_pct, tolerance_abs, confidence_gate, field_floor from v_stage_today
      where org_id = '0c000000-0000-0000-0000-000000000000'$q$,
  $q$values (0.02::numeric(6,5), 25.00::numeric(12,2), 0.900::numeric(4,3), 0.750::numeric(4,3))$q$, 'v_stage_today policy');
select results_eq(
  $q$select invoice_number, status_label, is_exception from v_recent_runs
      where org_id = '0c000000-0000-0000-0000-000000000000' order by started_at$q$,
  $q$values ('K-1'::text, 'Touchless'::text, false), ('K-2', 'Price variance', true), ('K-3', 'Below gate', true), ('K-5', 'Posted', false)$q$,
  'v_recent_runs status labels');
select is((select end_to_end_seconds from v_recent_runs where run_id = '0c000000-0000-0000-0009-000000000001'), 16::numeric,
  'end to end seconds');
select is((select erp_external_id from v_recent_runs where run_id = '0c000000-0000-0000-0009-000000000001'), 'JE-1', 'erp ref');
select is((select open_exception_type::text from v_recent_runs where run_id = '0c000000-0000-0000-0009-000000000002'),
  'price_variance', 'open exception on the run');
select is((select actor_name from v_run_timeline where run_id = '0c000000-0000-0000-0009-000000000005' and stage = 'approval'),
  'Kim Manager', 'timeline actor name');
select results_eq(
  $q$select queue_position, queue_size, flagged_count, invoice_number from v_review_queue
      where org_id = '0c000000-0000-0000-0000-000000000000'$q$,
  $q$values (1, 1, 2, 'K-3'::text)$q$, 'v_review_queue with flagged fields');
select results_eq(
  $q$select grn_in_full, grn_numbers, po_number, jsonb_array_length(lines), fields -> 'total' ->> 'value', entity_short_code
       from v_invoice_detail where invoice_id = '0c000000-0000-0000-0007-000000000001'$q$,
  $q$values (true, array['GRN-K1']::text[], 'PO-K1'::text, 1, '100.00'::text, 'E1'::text)$q$, 'v_invoice_detail header');
select is((select lines -> 0 ->> 'gl_number' from v_invoice_detail where invoice_id = '0c000000-0000-0000-0007-000000000001'),
  '5000', 'lines carry GL');
select results_eq(
  $q$select line_verdict::text, delta_amount, po_qty, recommendation ->> 'action', decision is null
       from v_match_detail where invoice_id = '0c000000-0000-0000-0007-000000000002'$q$,
  $q$values ('price_variance'::text, 88.00::numeric(12,2), 10::numeric(12,3), 'short_pay'::text, true)$q$, 'v_match_detail line');
select is((select decision ->> 'actor_name' from v_match_detail where invoice_id = '0c000000-0000-0000-0007-000000000005'),
  'Kim Manager', 'v_match_detail decision for a decided invoice');
select results_eq(
  $q$select group_label, is_risk_group, payment_blocked, recommendation ->> 'action', signal_score is null
       from v_exception_queue where exception_id = '0c000000-0000-0000-000a-000000000002'$q$,
  $q$values ('Price variance'::text, false, false, 'short_pay'::text, true)$q$, 'v_exception_queue row');
select is((select latest_decision ->> 'action' from v_exception_queue where exception_id = '0c000000-0000-0000-000a-000000000005'),
  'short_pay', 'latest decision');
select results_eq(
  $q$select runs_today, exceptions_open, exceptions_raised_today, exceptions_cleared_today, payments_blocked,
            review_queue_size, avg_decision_seconds_today, workflow_version, dead_letters_open
       from v_status_bar where org_id = '0c000000-0000-0000-0000-000000000000'$q$,
  $q$values (4, 2, 3, 1, 0, 1, 600.0::numeric, 'v15'::text, 0)$q$, 'v_status_bar');
select is((select erp_failing from v_status_bar where org_id = '0c000000-0000-0000-0000-000000000000'), '[]'::jsonb, 'no ERP failing');
select is((select pipeline_paused_reason from v_status_bar where org_id = '0c000000-0000-0000-0000-000000000000'), null, 'not paused');
select is((select count(*) from v_invoice_audit where invoice_key = '0c000000-0000-0000-0007-000000000005'), 1::bigint,
  'v_invoice_audit by invoice');

-- ------------------------------------------------------------------ materialized KPIs
select lives_ok($q$select public.refresh_kpis()$q$, 'refresh_kpis runs');
select results_eq(
  $q$select invoices, locations, entities, touchless_rate, median_cycle_seconds, held_variances, held_total,
            short_pays_accepted, avg_decision_seconds, decisions_logged_pct
       from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'mtd'$q$,
  $q$values (4, 2, 2, 0.5000::numeric(5,4), 5400::numeric, 61.60::numeric(12,2), 61.60::numeric(12,2), 1, 600.0::numeric, 1.0000::numeric(5,4))$q$,
  'mv_ops_period mtd (seeded history without a run is excluded)');
select results_eq(
  $q$select cost_llm, cost_human, cost_ocr from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'l30'$q$,
  $q$values (0.30::numeric(12,2), 5.83::numeric(12,2), 0.00::numeric(12,2))$q$, 'costs from cost_ledger and approval time');
select ok((select abs(cost_total - (cost_llm + cost_ocr + cost_infra + cost_human)) <= 0.02 and cost_infra > 0
             and abs(cost_per_invoice * invoices - cost_total) <= 0.01
           from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'l30'),
  'cost_total = sum of parts; per-invoice derived');
select is((select touchless_rate_first_week from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'qtd'),
  0.5000::numeric(5,4), 'first-week touchless rate');
select is((select top_catches -> 0 ->> 'invoice_number' from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'mtd'),
  'K-5', 'top catch');
select is((select (erp_sync -> 0 ->> 'posted_count')::int from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'mtd'),
  2, 'erp sync posted count (quickbooks)');
select is((select count(*) from mv_ops_period where org_id = '0c000000-0000-0000-0000-000000000000'), 3::bigint, 'three periods');
select results_eq(
  $q$select location_code, volume, exception_rate, rank, locations_total, vendors_without_contract
       from mv_location_period where org_id = '0c000000-0000-0000-0000-000000000000' and period_key = 'mtd' order by rank$q$,
  $q$values ('RS'::text, 3, 0.6667::numeric(5,4), 1, 2, 1), ('CM', 1, 1.0000::numeric(5,4), 2, 2, 1)$q$, 'mv_location_period');
select results_eq(
  $q$select count(*)::int, min(week_index), max(week_index) from mv_eval_weekly where org_id = '0c000000-0000-0000-0000-000000000000'$q$,
  $q$values (12, 1, 12)$q$, 'mv_eval_weekly keeps the last 12 weeks');
select is((select accuracy from mv_eval_weekly where org_id = '0c000000-0000-0000-0000-000000000000' and week_index = 12),
  0.9510::numeric(6,4), 'latest week accuracy');
select is((select count(*) from mv_eval_weekly where org_id = '0c000000-0000-0000-0000-000000000000' and prompt_deployed_at is not null),
  1::bigint, 'prompt version marker in one week');

-- ------------------------------------------------------------------ budget / rate limit / kb_search
select isnt(public.llm_budget_reserve(0.30), null, 'reserve within cap');
select is(public.llm_budget_reserve(0.30), null, 'reserve over cap returns null');
select is((select remaining_usd from v_ai_budget_today), 0.20::numeric, 'budget remaining');
select results_eq($q$select public.rate_limit_hit('t:k', 2, 60) union all select public.rate_limit_hit('t:k', 2, 60)
                     union all select public.rate_limit_hit('t:k', 2, 60)$q$,
  $q$values (false), (false), (true)$q$, 'rate limit trips on the third hit');

insert into public.kb_documents (id, org_id, kind, title) values
  ('0c000000-0000-0000-0010-000000000001', '0c000000-0000-0000-0000-000000000000', 'contract', 'Vendor agreement 2026');
insert into public.kb_chunks (document_id, org_id, ord, heading_path, clause_ref, content, embedding)
select '0c000000-0000-0000-0010-000000000001', '0c000000-0000-0000-0000-000000000000', n, 'Pricing', c, txt,
       (select ('[' || string_agg(case when g = n then '1' else '0.01' end, ',') || ']') from generate_series(1, 512) g)::extensions.vector
from (values (1, '4.2', 'Shrimp 16/20 IQF is fixed at $3.68 per pound for the term.'),
             (2, '7.1', 'Payment terms are net 14 days from delivery.')) v(n, c, txt);
select results_eq(
  $q$select clause_ref, vector_rank, text_rank from public.kb_search('0c000000-0000-0000-0000-000000000000',
       (select ('[' || string_agg(case when g = 1 then '1' else '0.01' end, ',') || ']') from generate_series(1, 512) g)::extensions.vector,
       'shrimp price', 1)$q$,
  $q$values ('4.2'::text, 1, 1)$q$, 'kb_search fuses vector and text ranks');

-- ------------------------------------------------------------------ wrappers as a member / non-member
create function pg_temp.read_all_views() returns void language plpgsql as $f$
declare v text; n bigint;
begin
  foreach v in array array['v_org_today','v_pipeline_today','v_stage_today','v_channel_today','v_recent_runs',
    'v_run_timeline','v_review_queue','v_invoice_detail','v_match_detail','v_exception_queue','exceptions_public',
    'v_invoice_audit','v_kpi_periods','v_ops_period','v_location_period','v_eval_weekly','v_ai_budget_today',
    'v_status_bar'] loop
    execute format('select count(*) from public.%I', v) into n;
  end loop;
end $f$;
select pg_temp.login('cccccccc-0000-0000-0000-000000000001');
select lives_ok($q$select pg_temp.read_all_views()$q$, 'a member can read every read-model view');
select is((select count(*) from v_ops_period), 3::bigint, 'member reads own KPI periods');
select pg_temp.login('cccccccc-0000-0000-0000-000000000002');
select is((select count(*) from v_location_period where org_id = '0c000000-0000-0000-0000-000000000000'), 0::bigint,
  'non-member reads no KPI rows');

select * from finish();
rollback;
