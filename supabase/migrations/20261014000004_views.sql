-- Ledgic 0004: read-model views (contracts/views.md) + KPI materialized views + refresh.
-- Every number on screen comes from these views; nothing is hard-coded.
--   * plain views are security_invoker (caller's RLS applies)
--   * mv_* are not RLS-capable: revoked from browser roles, exposed via v_* wrappers filtered by is_member()
--   * "today" = org-local calendar day, expressed as a [t0, t1) timestamptz range so indexes apply

------------------------------------------------------------------------------------------------
-- 0. Helpers
------------------------------------------------------------------------------------------------
create or replace function public.exception_status_label(p public.exception_type) returns text
language sql immutable set search_path = '' as $$
  select case p
    when 'extraction_review' then 'Below gate'      when 'price_variance' then 'Price variance'
    when 'qty_mismatch' then 'Quantity mismatch'    when 'no_po' then 'No PO found'
    when 'unmatched_line' then 'Unmatched line'     when 'duplicate' then 'Duplicate'
    when 'new_vendor_screen' then 'New vendor screen' when 'posting_failed' then 'Posting failed' end
$$;

create or replace function public.exception_group_label(p public.exception_type) returns text
language sql immutable set search_path = '' as $$
  select case p
    when 'price_variance' then 'Price variance'     when 'qty_mismatch' then 'Quantity mismatch'
    when 'no_po' then 'No purchase order'           when 'unmatched_line' then 'Unmatched line'
    when 'duplicate' then 'Suspected duplicate'     when 'new_vendor_screen' then 'New vendor screen'
    when 'posting_failed' then 'Posting failed'     when 'extraction_review' then 'Extraction review' end
$$;

grant execute on function public.exception_status_label(public.exception_type),
  public.exception_group_label(public.exception_type) to authenticated, service_role;

-- Org-local "today" per org (also handy for clients).
create or replace view public.v_org_today with (security_invoker = true) as
select o.id as org_id, o.timezone, x.day,
       (x.day::timestamp at time zone o.timezone)       as t0,
       ((x.day + 1)::timestamp at time zone o.timezone) as t1
from public.orgs o
cross join lateral (select (now() at time zone o.timezone)::date as day) x;

------------------------------------------------------------------------------------------------
-- 1. v_pipeline_today — attrition bars
------------------------------------------------------------------------------------------------
create or replace view public.v_pipeline_today with (security_invoker = true) as
select d.org_id, d.day,
  count(r.id)::int                                                                     as received,
  count(r.id) filter (where ext.passed)::int                                           as extracted_above_gate,
  count(r.id) filter (where i.po_id is not null
                        and i.status not in ('received', 'extracted', 'in_review'))::int as enriched_po_linked,
  count(r.id) filter (where m.verdict = 'clean')::int                                  as matched_clean,
  count(r.id) filter (where x.has_exception)::int                                      as routed_to_people
from public.v_org_today d
left join public.pipeline_runs r on r.org_id = d.org_id and r.started_at >= d.t0 and r.started_at < d.t1
left join public.invoices i on i.id = r.invoice_id
left join public.match_results m on m.invoice_id = r.invoice_id
left join lateral (
  select coalesce(bool_or(pe.detail -> 'gate_passed' = 'true'::jsonb), false) as passed
  from public.pipeline_events pe
  where pe.run_id = r.id and pe.stage = 'extraction' and pe.status = 'succeeded') ext on true
left join lateral (
  select exists (select 1 from public.exceptions e where e.invoice_id = r.invoice_id) as has_exception) x on true
group by d.org_id, d.day;

------------------------------------------------------------------------------------------------
-- 2. v_stage_today — stage columns 02–05 + status-bar policy values
------------------------------------------------------------------------------------------------
create or replace view public.v_stage_today with (security_invoker = true) as
with d as (select * from public.v_org_today),
runs as (
  select r.org_id, r.id, r.invoice_id from public.pipeline_runs r join d on d.org_id = r.org_id
  where r.started_at >= d.t0 and r.started_at < d.t1),
inv as (
  select i.* from public.invoices i join d on d.org_id = i.org_id
  where i.received_at >= d.t0 and i.received_at < d.t1),
exc as (
  select e.org_id, e.type from public.exceptions e join d on d.org_id = e.org_id
  where e.opened_at >= d.t0 and e.opened_at < d.t1)
select d.org_id,
  (select count(*) from runs r where r.org_id = d.org_id and exists (
     select 1 from public.pipeline_events pe where pe.run_id = r.id and pe.stage = 'extraction'
       and pe.status = 'succeeded' and pe.detail -> 'gate_passed' = 'true'::jsonb))::int          as extraction_auto_passed,
  (select count(*) from exc where exc.org_id = d.org_id and exc.type = 'extraction_review')::int  as extraction_below_gate,
  (select round((percentile_cont(0.5) within group (order by pe.duration_ms))::numeric / 1000, 1)
     from public.pipeline_events pe
    where pe.org_id = d.org_id and pe.stage = 'extraction' and pe.status = 'succeeded'
      and pe.duration_ms is not null and pe.at >= d.t0 and pe.at < d.t1)::numeric(8,1)           as extraction_median_seconds,
  (select count(*) from inv where inv.org_id = d.org_id and inv.vendor_id is not null)::int         as vendor_resolved,
  (select count(*) from inv where inv.org_id = d.org_id and inv.po_id is not null)::int             as po_linked,
  (select count(*) from inv where inv.org_id = d.org_id
      and exists (select 1 from public.invoice_lines l where l.invoice_id = inv.id)
      and not exists (select 1 from public.invoice_lines l where l.invoice_id = inv.id and l.gl_account_id is null))::int
                                                                                                   as gl_predicted,
  (select count(*) from runs r where r.org_id = d.org_id and exists (
     select 1 from public.pipeline_events pe where pe.run_id = r.id and pe.stage = 'screening'
       and pe.status = 'succeeded'))::int                                                          as duplicate_screened,
  (select count(*) from inv join public.match_results m on m.invoice_id = inv.id
    where inv.org_id = d.org_id and m.verdict = 'clean')::int                                       as match_clean,
  (select count(*) from exc where exc.org_id = d.org_id and exc.type = 'price_variance')::int     as match_price_variance,
  (select count(*) from exc where exc.org_id = d.org_id and exc.type = 'qty_mismatch')::int       as match_qty_mismatch,
  (select count(*) from exc where exc.org_id = d.org_id and exc.type = 'no_po')::int              as match_no_po,
  (select count(*) from public.exceptions e where e.org_id = d.org_id and e.status <> 'resolved')::int as awaiting_person,
  (select count(*) from public.erp_postings p where p.org_id = d.org_id and p.status = 'posted'
      and p.system = 'quickbooks' and p.posted_at >= d.t0 and p.posted_at < d.t1)::int             as posted_quickbooks,
  (select count(*) from public.erp_postings p where p.org_id = d.org_id and p.status = 'posted'
      and p.system = 'netsuite' and p.posted_at >= d.t0 and p.posted_at < d.t1)::int               as posted_netsuite,
  coalesce(tp.pct, 0.02)::numeric(6,5)             as tolerance_pct,
  coalesce(tp.abs_amount, 25.00)::numeric(12,2)    as tolerance_abs,
  coalesce(s.confidence_gate, 0.900)::numeric(4,3) as confidence_gate,
  coalesce(s.field_floor, 0.750)::numeric(4,3)     as field_floor
from d
left join public.org_settings s on s.org_id = d.org_id
left join lateral (
  select t.pct, t.abs_amount from public.tolerance_policies t
  where t.org_id = d.org_id and t.effective_from <= now() order by t.effective_from desc limit 1) tp on true;

------------------------------------------------------------------------------------------------
-- 3. v_channel_today — intake counts, all 5 channels zero-filled
------------------------------------------------------------------------------------------------
create or replace view public.v_channel_today with (security_invoker = true) as
select d.org_id, ch.channel, count(doc.id)::int as count
from public.v_org_today d
cross join unnest(enum_range(null::public.channel)) as ch(channel)
left join public.documents doc
  on doc.org_id = d.org_id and doc.channel = ch.channel and doc.received_at >= d.t0 and doc.received_at < d.t1
group by d.org_id, ch.channel;

------------------------------------------------------------------------------------------------
-- 4. v_recent_runs — Recent runs table + Invoices list
------------------------------------------------------------------------------------------------
create or replace view public.v_recent_runs with (security_invoker = true) as
select r.org_id, r.id as run_id, r.run_number, r.started_at, r.finished_at, r.status as run_status, r.current_stage,
       i.id as invoice_id, i.invoice_number, i.vendor_id, v.display_name as vendor_name,
       i.location_id, l.name as location_name, l.code as location_code, en.short_code as entity_short_code,
       i.total, i.status as invoice_status, doc.channel, i.touchless,
       oe.id as open_exception_id, oe.type as open_exception_type,
       lbl.status_label,
       lbl.status_label in ('Below gate', 'Price variance', 'Quantity mismatch', 'No PO found', 'Unmatched line',
                            'Duplicate', 'New vendor screen', 'Posting failed', 'Failed') as is_exception,
       extract(epoch from (r.finished_at - r.started_at))::numeric as end_to_end_seconds,
       ep.system as erp_system, ep.external_id as erp_external_id
from public.pipeline_runs r
join public.documents doc on doc.id = r.document_id
left join public.invoices i on i.id = r.invoice_id
left join public.vendors v on v.id = i.vendor_id
left join public.locations l on l.id = i.location_id
left join public.entities en on en.id = coalesce(i.entity_id, l.entity_id)
left join lateral (
  select e.id, e.type from public.exceptions e
  where e.invoice_id = i.id and e.status <> 'resolved' order by e.opened_at, e.id limit 1) oe on true
left join lateral (
  select p.system, p.external_id from public.erp_postings p
  where p.invoice_id = i.id and p.status = 'posted' order by p.posted_at desc nulls last limit 1) ep on true
cross join lateral (
  select case
    when r.status in ('failed', 'cancelled') then 'Failed'
    when i.status = 'rejected' then 'Rejected'
    when i.status = 'duplicate' then 'Duplicate'
    when oe.type is not null then public.exception_status_label(oe.type)
    when i.status = 'posted' and i.touchless then 'Touchless'
    when i.status = 'posted' then 'Posted'
    else 'In progress' end as status_label) lbl;

------------------------------------------------------------------------------------------------
-- 5. v_run_timeline — run inspector / invoice timeline
------------------------------------------------------------------------------------------------
create or replace view public.v_run_timeline with (security_invoker = true) as
select pe.org_id, pe.run_id, pe.id as event_id, pe.at, pe.stage, pe.status, pe.duration_ms, pe.summary, pe.detail,
       p.full_name as actor_name
from public.pipeline_events pe
left join public.profiles p on p.user_id = public.try_uuid(pe.detail ->> 'actor_id');

------------------------------------------------------------------------------------------------
-- 6. v_review_queue — open extraction reviews, oldest first
------------------------------------------------------------------------------------------------
create or replace view public.v_review_queue with (security_invoker = true) as
select e.org_id, e.id as exception_id, e.invoice_id, e.run_id,
       (row_number() over (partition by e.org_id order by e.opened_at, e.id))::int as queue_position,
       (count(*) over (partition by e.org_id))::int                               as queue_size,
       e.opened_at, v.display_name as vendor_name, i.invoice_number, l.name as location_name,
       doc.channel, doc.original_filename, i.doc_confidence, fl.flagged_count
from public.exceptions e
join public.invoices i on i.id = e.invoice_id
join public.documents doc on doc.id = i.document_id
left join public.vendors v on v.id = i.vendor_id
left join public.locations l on l.id = i.location_id
left join public.org_settings s on s.org_id = e.org_id
left join lateral (
  select ((select count(*) from (
             select distinct on (f.field) f.value, f.confidence from public.invoice_fields f
             where f.invoice_id = i.id order by f.field, f.version desc) lf
           where lf.value is not null and lf.confidence < coalesce(s.field_floor, 0.75))
        + (select count(*) from public.invoice_lines il cross join lateral jsonb_each(il.confidences) c
           where il.invoice_id = i.id and jsonb_typeof(c.value) = 'number'
             and (c.value #>> '{}')::numeric < coalesce(s.field_floor, 0.75)))::int as flagged_count) fl on true
where e.type = 'extraction_review' and e.status <> 'resolved';

------------------------------------------------------------------------------------------------
-- 7. v_invoice_detail — header for Extraction / Match / Invoice detail
------------------------------------------------------------------------------------------------
create or replace view public.v_invoice_detail with (security_invoker = true) as
select i.org_id, i.id as invoice_id, i.document_id,
       i.invoice_number, i.terms, i.currency::text as currency, i.invoice_date, i.due_date,
       i.subtotal, i.tax, i.freight, i.total, i.status, i.doc_confidence, i.gate_passed, i.touchless,
       i.human_touches, i.extraction_mode, i.received_at, i.posted_at, i.duplicate_of,
       i.vendor_id, v.display_name as vendor_name, v.legal_name as vendor_legal_name, v.category as vendor_category,
       en.id as entity_id, en.name as entity_name, en.short_code as entity_short_code,
       l.id as location_id, l.name as location_name, l.code as location_code,
       po.id as po_id, po.po_number, po.total as po_total, po.source as po_source,
       grn.grn_numbers, grn.grn_received_at, gf.grn_in_full,
       doc.channel, doc.storage_path, doc.original_filename, doc.mime, doc.page_count, doc.preprocessing, doc.source_meta,
       run.id as run_id, run.run_number, run.workflow_version,
       coalesce(flds.fields, '{}'::jsonb) as fields,
       coalesce(lns.lines, '[]'::jsonb)   as lines,
       ep.system as erp_system, ep.external_id as erp_external_id, ep.status as erp_status
from public.invoices i
join public.documents doc on doc.id = i.document_id
left join public.vendors v on v.id = i.vendor_id
left join public.locations l on l.id = i.location_id
left join public.entities en on en.id = coalesce(i.entity_id, l.entity_id)
left join public.purchase_orders po on po.id = i.po_id
left join lateral (
  select array_agg(g.grn_number order by g.received_at) as grn_numbers, max(g.received_at) as grn_received_at
  from public.goods_receipts g where g.po_id = po.id) grn on true
left join lateral (
  select case when po.id is null then null
              else coalesce(bool_and(coalesce(rcv.q, 0) >= pl.qty), false) end as grn_in_full
  from public.po_lines pl
  left join lateral (select sum(gl.qty_received) as q from public.grn_lines gl where gl.po_line_id = pl.id) rcv on true
  where pl.po_id = po.id) gf on true
left join lateral (
  select r.id, r.run_number, r.workflow_version from public.pipeline_runs r
  where r.invoice_id = i.id order by r.started_at desc limit 1) run on true
left join lateral (
  select jsonb_object_agg(f.field, jsonb_build_object(
           'value', f.value, 'confidence', f.confidence, 'raw_confidence', f.raw_confidence, 'bbox', f.bbox,
           'source', f.source, 'version', f.version, 'set_by', f.set_by, 'set_at', f.set_at)) as fields
  from (select distinct on (x.field) x.* from public.invoice_fields x
        where x.invoice_id = i.id order by x.field, x.version desc) f) flds on true
left join lateral (
  select jsonb_agg(jsonb_build_object(
           'id', il.id, 'line_no', il.line_no, 'description', il.description, 'qty', il.qty, 'uom', il.uom,
           'unit_price', il.unit_price, 'amount', il.amount, 'confidences', il.confidences, 'bboxes', il.bboxes,
           'gl_number', ga.number, 'gl_name', ga.name, 'gl_confidence', il.gl_confidence,
           'po_line_id', il.po_line_id, 'item_id', il.item_id) order by il.line_no) as lines
  from public.invoice_lines il left join public.gl_accounts ga on ga.id = il.gl_account_id
  where il.invoice_id = i.id) lns on true
left join lateral (
  select p.system, p.external_id, p.status from public.erp_postings p
  where p.invoice_id = i.id order by (p.status = 'posted') desc, p.posted_at desc nulls last limit 1) ep on true;

------------------------------------------------------------------------------------------------
-- 8. v_match_detail — one row per invoice line of a matched invoice
------------------------------------------------------------------------------------------------
create or replace view public.v_match_detail with (security_invoker = true) as
select i.org_id, i.id as invoice_id, m.id as match_result_id, m.verdict, m.tolerance_pct, m.tolerance_abs,
       m.expected_total, m.total_delta, m.lines_verified, m.lines_total, m.duration_ms, m.computed_at,
       il.id as invoice_line_id, il.line_no, il.description, il.uom,
       il.qty as inv_qty, il.unit_price as inv_unit_price, il.amount as inv_amount,
       coalesce(mlr.po_line_id, il.po_line_id) as po_line_id,
       pl.qty as po_qty, pl.unit_price as po_unit_price, pl.amount as po_amount,
       mlr.grn_qty, mlr.expected_unit_price, mlr.expected_source, mlr.expected_amount, mlr.delta_amount,
       mlr.allowed_amount, mlr.delta_pct,
       coalesce(mlr.verdict, 'matched'::public.line_verdict) as line_verdict, mlr.note,
       c.id as contract_id, c.title as contract_title, c.document_path as contract_document_path,
       c.effective_to as contract_effective_to, cp.clause_ref,
       ex.id as exception_id,
       case when rec.id is not null then jsonb_build_object(
         'action', rec.action, 'pay_amount', rec.pay_amount, 'hold_amount', rec.hold_amount,
         'confidence', rec.confidence, 'reasons', rec.reasons) end as recommendation,
       dcs.decision
from public.match_results m
join public.invoices i on i.id = m.invoice_id
join public.invoice_lines il on il.invoice_id = i.id
left join public.match_line_results mlr on mlr.match_result_id = m.id and mlr.invoice_line_id = il.id
left join public.po_lines pl on pl.id = coalesce(mlr.po_line_id, il.po_line_id)
left join public.contract_prices cp on cp.id = mlr.contract_price_id
left join public.contracts c on c.id = cp.contract_id
left join lateral (
  select e.id from public.exceptions e where e.invoice_id = i.id
  order by (e.type = 'extraction_review'), (e.status <> 'resolved') desc, e.opened_at desc limit 1) ex on true
left join public.recommendations rec on rec.exception_id = ex.id
left join lateral (
  select jsonb_build_object('approval_id', a.id, 'action', a.action, 'actor_id', a.actor_id,
                            'actor_name', p.full_name, 'decided_at', a.decided_at, 'pay_amount', a.pay_amount,
                            'hold_amount', a.hold_amount, 'comment', a.comment) as decision
  from public.approvals a left join public.profiles p on p.user_id = a.actor_id
  where a.exception_id = ex.id order by a.decided_at desc limit 1) dcs on true;

------------------------------------------------------------------------------------------------
-- 9. v_exception_queue — Exceptions queue + detail
------------------------------------------------------------------------------------------------
create or replace view public.v_exception_queue with (security_invoker = true) as
select e.org_id, e.id as exception_id, e.invoice_id, e.run_id, e.type,
       public.exception_group_label(e.type) as group_label,
       e.type in ('duplicate', 'new_vendor_screen') as is_risk_group,
       e.status, e.amount_at_risk, e.reason, e.assigned_role, e.assigned_to, ap.full_name as assigned_to_name,
       e.escalated, e.opened_at, e.sla_due_at, e.first_viewed_at, e.resolved_at,
       extract(epoch from (now() - e.opened_at))::int as age_seconds,
       i.vendor_id, v.display_name as vendor_name, i.invoice_number, i.total as invoice_total,
       l.name as location_name,
       (e.type in ('duplicate', 'new_vendor_screen') and e.status <> 'resolved') as payment_blocked,
       dup.similarity, dup.evidence as duplicate_evidence,
       fr.signal_score, fr.signals,
       case when rec.id is not null then jsonb_build_object(
         'action', rec.action, 'pay_amount', rec.pay_amount, 'hold_amount', rec.hold_amount,
         'confidence', rec.confidence, 'reasons', rec.reasons) end as recommendation,
       dcs.decision as latest_decision,
       exists (select 1 from public.exception_drafts dr where dr.exception_id = e.id) as has_draft
from public.exceptions e
join public.invoices i on i.id = e.invoice_id
left join public.vendors v on v.id = i.vendor_id
left join public.locations l on l.id = i.location_id
left join public.profiles ap on ap.user_id = e.assigned_to
left join public.recommendations rec on rec.exception_id = e.id
left join lateral (
  select dc.similarity, dc.evidence || jsonb_build_object('candidate_invoice_id', dc.candidate_invoice_id) as evidence
  from public.duplicate_candidates dc where dc.invoice_id = e.invoice_id
  order by dc.similarity desc, dc.created_at limit 1) dup on true
left join lateral (
  select least(1, sum(fs.weight))::numeric(4,3) as signal_score,
         jsonb_agg(jsonb_build_object('signal', fs.signal, 'weight', fs.weight, 'detail', fs.detail)
                   order by fs.weight desc, fs.signal) as signals
  from public.fraud_signals fs where fs.invoice_id = e.invoice_id
  having count(*) > 0) fr on true
left join lateral (
  select jsonb_build_object('approval_id', a.id, 'action', a.action, 'actor_id', a.actor_id,
                            'actor_name', p.full_name, 'decided_at', a.decided_at, 'pay_amount', a.pay_amount,
                            'hold_amount', a.hold_amount, 'comment', a.comment) as decision
  from public.approvals a left join public.profiles p on p.user_id = a.actor_id
  where a.exception_id = e.id order by a.decided_at desc limit 1) dcs on true;

------------------------------------------------------------------------------------------------
-- 10. v_invoice_audit (addition) — audit trail rows that concern one invoice
--     (entity invoice itself, or any row whose after.invoice_id names it). Filter by invoice_key.
------------------------------------------------------------------------------------------------
create index if not exists audit_log_invoice_key_idx on public.audit_log
  (org_id, (coalesce(case when entity_type = 'invoice' then entity_id end, after ->> 'invoice_id')), id);

create or replace view public.v_invoice_audit with (security_invoker = true) as
select a.org_id,
       coalesce(case when a.entity_type = 'invoice' then a.entity_id end, a.after ->> 'invoice_id') as invoice_key,
       a.id as audit_id, a.at, a.actor_type, a.actor_id, p.full_name as actor_name, a.action,
       a.entity_type, a.entity_id, a.before, a.after, a.prev_hash, a.hash
from public.audit_log a
left join public.profiles p on p.user_id = public.try_uuid(a.actor_id);

------------------------------------------------------------------------------------------------
-- 11. Materialized KPI views
------------------------------------------------------------------------------------------------
-- Periods per org: mtd, qtd, l30 (org-local dates); ts0/ts1 are the timestamptz bounds.
create or replace view public.v_kpi_periods with (security_invoker = true) as
select d.org_id, d.timezone, k.period_key, k.ps as period_start, d.day as period_end,
       (k.ps::timestamp at time zone d.timezone)        as ts0,
       ((d.day + 1)::timestamp at time zone d.timezone) as ts1,
       (d.day - k.ps + 1)                               as days,
       extract(day from (date_trunc('month', d.day) + interval '1 month - 1 day'))::int as month_days
from public.v_org_today d
cross join lateral (values ('mtd', date_trunc('month', d.day)::date),
                           ('qtd', date_trunc('quarter', d.day)::date),
                           ('l30', d.day - 29)) as k(period_key, ps);

-- KPIs count invoices that went through the Ledgic pipeline (have a run); seeded back-history
-- for GL kNN has no run and never inflates operational figures.
create materialized view public.mv_ops_period as
with p as (select * from public.v_kpi_periods),
inv as (
  select p.org_id, p.period_key, count(*)::int as n
  from p join public.invoices i on i.org_id = p.org_id and i.received_at >= p.ts0 and i.received_at < p.ts1
  where exists (select 1 from public.pipeline_runs r where r.invoice_id = i.id)
  group by 1, 2),
posted as (
  select p.org_id, p.period_key,
         count(*) as n_posted,
         count(*) filter (where i.touchless) as n_touchless,
         percentile_cont(0.5) within group (order by extract(epoch from (i.posted_at - i.received_at))) as median_cycle
  from p join public.invoices i on i.org_id = p.org_id and i.posted_at >= p.ts0 and i.posted_at < p.ts1
  where i.status = 'posted' and exists (select 1 from public.pipeline_runs r where r.invoice_id = i.id)
  group by 1, 2),
first_week as (
  select f.org_id,
         (count(*) filter (where i.touchless))::numeric / nullif(count(*), 0) as rate
  from (select i.org_id, min(i.posted_at) as first_at from public.invoices i
        where i.status = 'posted' and exists (select 1 from public.pipeline_runs r where r.invoice_id = i.id)
        group by i.org_id) f
  join public.invoices i on i.org_id = f.org_id and i.status = 'posted'
                        and i.posted_at >= f.first_at and i.posted_at < f.first_at + interval '7 days'
  where exists (select 1 from public.pipeline_runs r where r.invoice_id = i.id)
  group by f.org_id),
costs as (
  select p.org_id, p.period_key,
         coalesce(sum(c.amount_usd) filter (where c.kind = 'llm'), 0)   as llm,
         coalesce(sum(c.amount_usd) filter (where c.kind = 'ocr'), 0)   as ocr,
         coalesce(sum(c.amount_usd) filter (where c.kind = 'infra'), 0) as infra
  from p left join public.cost_ledger c on c.org_id = p.org_id and c.at >= p.ts0 and c.at < p.ts1
  group by 1, 2),
dcs as (
  select p.org_id, p.period_key,
         count(a.id)                                                            as n,
         coalesce(sum(a.time_spent_seconds), 0)                                 as seconds,
         coalesce(sum(a.hold_amount) filter (where a.action = 'short_pay'), 0)  as held_variances,
         coalesce(sum(e.amount_at_risk) filter (where a.action in ('merge', 'reject_copy')), 0) as held_duplicates,
         coalesce(sum(e.amount_at_risk) filter (where a.action = 'reject_invoice'
                                                  and e.type = 'new_vendor_screen'), 0)          as held_fraud,
         count(a.id) filter (where a.action = 'short_pay')                      as short_pays,
         avg(extract(epoch from (a.decided_at - e.opened_at)))                  as avg_decision,
         count(a.id) filter (where exists (
           select 1 from public.audit_log al where al.org_id = a.org_id and al.entity_type = 'approval'
             and al.entity_id = a.id::text))                                    as logged
  from p
  left join public.approvals a on a.org_id = p.org_id and a.decided_at >= p.ts0 and a.decided_at < p.ts1
  left join public.exceptions e on e.id = a.exception_id
  group by 1, 2),
catches as (
  select x.org_id, x.period_key,
         jsonb_agg(jsonb_build_object('exception_id', x.exception_id, 'invoice_number', x.invoice_number,
                                      'vendor_name', x.vendor_name, 'amount', x.amount, 'text', x.text)
                   order by x.amount desc, x.decided_at) as top
  from (
    select p.org_id, p.period_key, e.id as exception_id, i.invoice_number, v.display_name as vendor_name,
           a.decided_at,
           (case when a.action = 'short_pay' then a.hold_amount else e.amount_at_risk end)::numeric(12,2) as amount,
           case when a.action = 'short_pay' then 'Short-paid · ' || e.reason
                when a.action in ('merge', 'reject_copy') then 'Duplicate payment blocked · ' || e.reason
                else 'New-vendor invoice rejected · ' || e.reason end as text,
           row_number() over (partition by p.org_id, p.period_key
                              order by (case when a.action = 'short_pay' then a.hold_amount else e.amount_at_risk end) desc,
                                       a.decided_at) as rn
    from p
    join public.approvals a on a.org_id = p.org_id and a.decided_at >= p.ts0 and a.decided_at < p.ts1
    join public.exceptions e on e.id = a.exception_id
    join public.invoices i on i.id = e.invoice_id
    left join public.vendors v on v.id = i.vendor_id
    where a.action in ('short_pay', 'merge', 'reject_copy')
       or (a.action = 'reject_invoice' and e.type = 'new_vendor_screen')) x
  where x.rn <= 3
  group by 1, 2),
erp as (
  select p.org_id, p.period_key,
         jsonb_agg(jsonb_build_object(
           'system', sys.erp,
           'posted_count', (select count(*) from public.erp_postings ep
                             where ep.org_id = p.org_id and ep.system = sys.erp and ep.status = 'posted'
                               and ep.posted_at >= p.ts0 and ep.posted_at < p.ts1),
           'last_posted_at', (select max(ep.posted_at) from public.erp_postings ep
                               where ep.org_id = p.org_id and ep.system = sys.erp and ep.status = 'posted'),
           'failing', exists (select 1 from public.exceptions e join public.invoices i on i.id = e.invoice_id
                                join public.entities en on en.id = i.entity_id
                               where e.org_id = p.org_id and e.type = 'posting_failed' and e.status <> 'resolved'
                                 and en.erp = sys.erp),
           'mock', true) order by sys.erp) as sync
  from p
  join (select distinct org_id, erp from public.entities where erp <> 'none') sys on sys.org_id = p.org_id
  group by 1, 2)
select p.org_id, p.period_key, p.period_start, p.period_end,
       coalesce(inv.n, 0)                                                         as invoices,
       (select count(*) from public.locations x where x.org_id = p.org_id)::int    as locations,
       (select count(*) from public.entities x where x.org_id = p.org_id)::int     as entities,
       round(costs.llm, 2)::numeric(12,2)                                         as cost_llm,
       round(costs.ocr, 2)::numeric(12,2)                                         as cost_ocr,
       round(costs.infra + coalesce(s.infra_monthly_usd, 55.00) * p.days / p.month_days, 2)::numeric(12,2) as cost_infra,
       round(dcs.seconds / 3600.0 * coalesce(s.loaded_hourly_rate_usd, 35.00), 2)::numeric(12,2)      as cost_human,
       round(costs.llm + costs.ocr + costs.infra + coalesce(s.infra_monthly_usd, 55.00) * p.days / p.month_days
             + dcs.seconds / 3600.0 * coalesce(s.loaded_hourly_rate_usd, 35.00), 2)::numeric(12,2)    as cost_total,
       (case when coalesce(inv.n, 0) > 0 then
          (costs.llm + costs.ocr + costs.infra + coalesce(s.infra_monthly_usd, 55.00) * p.days / p.month_days
           + dcs.seconds / 3600.0 * coalesce(s.loaded_hourly_rate_usd, 35.00)) / inv.n end)::numeric(12,4) as cost_per_invoice,
       (posted.n_touchless::numeric / nullif(posted.n_posted, 0))::numeric(5,4)   as touchless_rate,
       fw.rate::numeric(5,4)                                                      as touchless_rate_first_week,
       round(posted.median_cycle::numeric, 0)                                     as median_cycle_seconds,
       dcs.held_variances::numeric(12,2)                                          as held_variances,
       dcs.held_duplicates::numeric(12,2)                                         as held_duplicates,
       dcs.held_fraud::numeric(12,2)                                              as held_fraud,
       (dcs.held_variances + dcs.held_duplicates + dcs.held_fraud)::numeric(12,2) as held_total,
       dcs.short_pays::int                                                        as short_pays_accepted,
       round(dcs.avg_decision::numeric, 1)                                        as avg_decision_seconds,
       (dcs.logged::numeric / nullif(dcs.n, 0))::numeric(5,4)                     as decisions_logged_pct,
       coalesce(catches.top, '[]'::jsonb)                                         as top_catches,
       coalesce(erp.sync, '[]'::jsonb)                                            as erp_sync,
       now()                                                                      as refreshed_at
from p
left join public.org_settings s on s.org_id = p.org_id
left join inv on inv.org_id = p.org_id and inv.period_key = p.period_key
left join posted on posted.org_id = p.org_id and posted.period_key = p.period_key
left join first_week fw on fw.org_id = p.org_id
left join costs on costs.org_id = p.org_id and costs.period_key = p.period_key
left join dcs on dcs.org_id = p.org_id and dcs.period_key = p.period_key
left join catches on catches.org_id = p.org_id and catches.period_key = p.period_key
left join erp on erp.org_id = p.org_id and erp.period_key = p.period_key;

create unique index mv_ops_period_pk on public.mv_ops_period (org_id, period_key);

create materialized view public.mv_location_period as
with p as (select * from public.v_kpi_periods),
st as (
  select p.org_id, p.period_key, i.location_id,
         count(*) as volume,
         count(*) filter (where exists (select 1 from public.exceptions e where e.invoice_id = i.id)) as with_exc,
         count(distinct i.vendor_id) filter (where i.vendor_id is not null and not exists (
           select 1 from public.contracts c where c.vendor_id = i.vendor_id
             and c.effective_from <= p.period_end and c.effective_to >= p.period_start)) as vendors_without_contract
  from p join public.invoices i on i.org_id = p.org_id and i.received_at >= p.ts0 and i.received_at < p.ts1
  where i.location_id is not null and exists (select 1 from public.pipeline_runs r where r.invoice_id = i.id)
  group by 1, 2, 3),
lrows as (
  select p.org_id, p.period_key, l.id as location_id, l.name as location_name, l.code as location_code,
         coalesce(st.volume, 0)::int as volume,
         coalesce(st.with_exc::numeric / nullif(st.volume, 0), 0)::numeric(5,4) as exception_rate,
         coalesce(st.vendors_without_contract, 0)::int as vendors_without_contract
  from p join public.locations l on l.org_id = p.org_id
  left join st on st.org_id = p.org_id and st.period_key = p.period_key and st.location_id = l.id),
med as (
  select org_id, period_key,
         (percentile_cont(0.5) within group (order by exception_rate))::numeric(5,4) as org_median
  from lrows where volume > 0 group by 1, 2)
select r.org_id, r.period_key, r.location_id, r.location_name, r.location_code, r.volume, r.exception_rate,
       (row_number() over (partition by r.org_id, r.period_key order by r.volume desc, r.location_name))::int as rank,
       (count(*) over (partition by r.org_id, r.period_key))::int as locations_total,
       coalesce(med.org_median, 0)::numeric(5,4) as org_median_exception_rate,
       r.vendors_without_contract
from lrows r left join med on med.org_id = r.org_id and med.period_key = r.period_key;

create unique index mv_location_period_pk on public.mv_location_period (org_id, period_key, location_id);

create materialized view public.mv_eval_weekly as
select e.org_id, e.week_start,
       (row_number() over (partition by e.org_id order by e.week_start))::int as week_index,
       e.accuracy, e.sample_size, e.prompt_version,
       (select max(pv.deployed_at) from public.prompt_versions pv
         where pv.deployed_at >= e.week_start::timestamptz and pv.deployed_at < (e.week_start + 7)::timestamptz)
         as prompt_deployed_at
from (select er.*, row_number() over (partition by er.org_id order by er.week_start desc) as rn
      from public.eval_runs er where er.org_id is not null) e
where e.rn <= 12;

create unique index mv_eval_weekly_pk on public.mv_eval_weekly (org_id, week_start);

-- Wrappers (owner rights read the MV; rows filtered to the caller's orgs)
create or replace view public.v_ops_period as
  select * from public.mv_ops_period where public.is_member(org_id) or public.ledgic_is_service();
create or replace view public.v_location_period as
  select * from public.mv_location_period where public.is_member(org_id) or public.ledgic_is_service();
create or replace view public.v_eval_weekly as
  select * from public.mv_eval_weekly where public.is_member(org_id) or public.ledgic_is_service();

------------------------------------------------------------------------------------------------
-- 12. v_ai_budget_today (global)
------------------------------------------------------------------------------------------------
create or replace view public.v_ai_budget_today with (security_invoker = true) as
select d.day,
       coalesce(b.cap_usd, public.ledgic_try_numeric(current_setting('ledgic.llm_daily_cap_usd', true)), 0.50) as cap_usd,
       coalesce(b.reserved_usd, 0) as reserved_usd,
       coalesce(b.spent_usd, 0)    as spent_usd,
       greatest(0, coalesce(b.cap_usd, public.ledgic_try_numeric(current_setting('ledgic.llm_daily_cap_usd', true)), 0.50)
                   - coalesce(b.reserved_usd, 0) - coalesce(b.spent_usd, 0)) as remaining_usd,
       (coalesce(b.cap_usd, public.ledgic_try_numeric(current_setting('ledgic.llm_daily_cap_usd', true)), 0.50)
          - coalesce(b.reserved_usd, 0) - coalesce(b.spent_usd, 0)) <= 0 as exhausted
from (select (now() at time zone 'utc')::date as day) d
left join public.llm_budget b on b.day = d.day;

------------------------------------------------------------------------------------------------
-- 13. v_status_bar
------------------------------------------------------------------------------------------------
create or replace view public.v_status_bar with (security_invoker = true) as
select d.org_id,
  lr.started_at                                                                     as last_run_at,
  (select count(*) from public.pipeline_runs r
    where r.org_id = d.org_id and r.started_at >= d.t0 and r.started_at < d.t1)::int as runs_today,
  (select count(*) from public.dead_letters dl where dl.org_id = d.org_id and dl.resolved_at is null)::int as dead_letters_open,
  lr.workflow_version,
  (select count(*) from public.exceptions e where e.org_id = d.org_id and e.type = 'extraction_review'
      and e.status <> 'resolved')::int                                             as review_queue_size,
  (select count(*) from public.exceptions e where e.org_id = d.org_id and e.status <> 'resolved')::int as exceptions_open,
  (select count(*) from public.exceptions e where e.org_id = d.org_id
      and e.opened_at >= d.t0 and e.opened_at < d.t1)::int                         as exceptions_raised_today,
  (select count(*) from public.exceptions e where e.org_id = d.org_id and e.status = 'resolved'
      and e.resolved_at >= d.t0 and e.resolved_at < d.t1)::int                     as exceptions_cleared_today,
  (select count(*) from public.exceptions e where e.org_id = d.org_id
      and e.type in ('duplicate', 'new_vendor_screen') and e.status <> 'resolved')::int as payments_blocked,
  (select round(avg(extract(epoch from (a.decided_at - e.opened_at)))::numeric, 1)
     from public.approvals a join public.exceptions e on e.id = a.exception_id
    where a.org_id = d.org_id and a.decided_at >= d.t0 and a.decided_at < d.t1)    as avg_decision_seconds_today,
  (select max(a.decided_at) from public.approvals a
    where a.org_id = d.org_id and a.action = 'confirm_fields')                     as last_autosave_at,
  (select coalesce(jsonb_agg(distinct x.sys), '[]'::jsonb) from (
     select en.erp::text as sys from public.exceptions e
       join public.invoices i on i.id = e.invoice_id join public.entities en on en.id = i.entity_id
      where e.org_id = d.org_id and e.type = 'posting_failed' and e.status <> 'resolved'
     union
     select p.system::text from public.erp_postings p join public.invoices i on i.id = p.invoice_id
      where p.org_id = d.org_id and p.status = 'failed' and i.status = 'posting') x)  as erp_failing,
  (select max(m.refreshed_at) from public.v_ops_period m where m.org_id = d.org_id)  as mv_refreshed_at,
  case when exists (select 1 from public.pipeline_runs r where r.org_id = d.org_id and r.status = 'running'
                      and r.next_attempt_at < now() - interval '15 minutes')
        and not exists (select 1 from public.pipeline_events pe where pe.org_id = d.org_id
                          and pe.at > now() - interval '15 minutes')
       then 'No run advanced in 15 minutes' end                                     as pipeline_paused_reason
from public.v_org_today d
left join lateral (
  select r.started_at, r.workflow_version from public.pipeline_runs r
  where r.org_id = d.org_id order by r.started_at desc limit 1) lr on true;

------------------------------------------------------------------------------------------------
-- 14. Refresh + schedule
------------------------------------------------------------------------------------------------
create or replace function public.refresh_kpis() returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not pg_try_advisory_xact_lock(hashtext('ledgic:refresh_kpis')) then
    return;  -- another refresh is running
  end if;
  refresh materialized view concurrently public.mv_ops_period;
  refresh materialized view concurrently public.mv_location_period;
  refresh materialized view concurrently public.mv_eval_weekly;
end $$;

do $$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.schedule('ledgic-refresh-kpis', '* * * * *', 'select public.refresh_kpis()');
    perform cron.schedule('ledgic-llm-release-stale', '*/5 * * * *', 'select public.llm_budget_release_stale()');
  else
    raise notice 'pg_cron not installed: core scheduler must call refresh_kpis()';
  end if;
end $$;

------------------------------------------------------------------------------------------------
-- 15. Grants
------------------------------------------------------------------------------------------------
revoke all on public.mv_ops_period, public.mv_location_period, public.mv_eval_weekly from anon, authenticated;
grant select on public.mv_ops_period, public.mv_location_period, public.mv_eval_weekly to service_role;

do $$
declare v text;
begin
  foreach v in array array['v_org_today','v_pipeline_today','v_stage_today','v_channel_today','v_recent_runs',
    'v_run_timeline','v_review_queue','v_invoice_detail','v_match_detail','v_exception_queue','v_invoice_audit',
    'v_kpi_periods','v_ops_period','v_location_period','v_eval_weekly','v_ai_budget_today','v_status_bar'] loop
    execute format('revoke all on public.%I from anon', v);
    execute format('revoke insert, update, delete, truncate on public.%I from authenticated', v);
    execute format('grant select on public.%I to authenticated, service_role', v);
  end loop;
end $$;

revoke execute on function public.refresh_kpis() from public, anon, authenticated;
grant execute on function public.refresh_kpis() to service_role;
grant execute on function public.ledgic_is_service(), public.ledgic_try_numeric(text) to authenticated;
