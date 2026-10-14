-- Ledgic 0003: RPCs (contracts/rpc.md). Decision RPCs carry every role limit and
-- segregation-of-duties rule in one place; core / MCP / replay call them "as a user".
-- Error convention: SQLSTATE + message prefix LEDGIC_<CODE>: (see rpc.md).

------------------------------------------------------------------------------------------------
-- 0. Internal helpers (not granted to browser roles)
------------------------------------------------------------------------------------------------
create or replace function public.ledgic_error(p_code text, p_msg text) returns void
language plpgsql set search_path = '' as $$
begin
  raise exception using
    message = 'LEDGIC_' || p_code || ': ' || p_msg,
    errcode = case p_code when 'FORBIDDEN' then '42501' when 'NOT_FOUND' then 'P0002'
                          when 'CONFLICT' then 'P0001' when 'INVALID' then '22023' else 'P0001' end;
end $$;

create or replace function public.ledgic_money(p numeric) returns text
language sql immutable set search_path = '' as $$
  select '$' || to_char(p, 'FM999,999,999,990.00')
$$;

-- True for server-side callers (service role JWT or a direct DB connection without SET ROLE).
create or replace function public.ledgic_is_service() returns boolean
language sql stable set search_path = '' as $$
  select coalesce(auth.role(), '') = 'service_role'
      or coalesce(current_setting('role', true), 'none') in ('none', 'service_role', 'postgres')
$$;

-- Actor type recorded in audit rows for user-initiated calls: MCP / agent callers acting as a user
-- add {"actor_type":"mcp"} to request.jwt.claims; browsers get 'user'.
create or replace function public.ledgic_actor_type() returns public.actor_type
language sql stable set search_path = '' as $$
  select case nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'actor_type'
           when 'mcp' then 'mcp'::public.actor_type
           when 'agent' then 'agent'::public.actor_type
           else 'user'::public.actor_type end
$$;

create or replace function public.audit_write(
  p_org uuid, p_actor_type public.actor_type, p_actor_id text, p_action text,
  p_entity_type text, p_entity_id text, p_before jsonb, p_after jsonb) returns bigint
language sql security definer set search_path = '' as $$
  insert into public.audit_log (org_id, actor_type, actor_id, action, entity_type, entity_id, before, after)
  values (p_org, p_actor_type, p_actor_id, p_action, p_entity_type, p_entity_id, p_before, p_after)
  returning id
$$;

-- Parse a decimal string; raise LEDGIC_INVALID unless it is > 0 (or >= 0 when p_allow_zero).
create or replace function public.ledgic_parse_amount(p_value text, p_label text, p_allow_zero boolean default false)
returns numeric language plpgsql immutable set search_path = '' as $$
declare v numeric;
begin
  begin
    v := replace(replace(btrim(p_value), ',', ''), '$', '')::numeric;
  exception when others then
    perform public.ledgic_error('INVALID', format('Enter a number for %s', p_label));
  end;
  if v is null or v < 0 or (v = 0 and not p_allow_zero) then
    perform public.ledgic_error('INVALID', format('%s must be greater than 0', p_label));
  end if;
  return v;
end $$;

create or replace function public.ledgic_parse_date(p_value text, p_label text) returns date
language plpgsql immutable set search_path = '' as $$
begin
  return btrim(p_value)::date;
exception when others then
  perform public.ledgic_error('INVALID', format('Enter a valid date for %s', p_label));
  return null;
end $$;

-- UI label for a decision action ("<label> by <full name>").
create or replace function public.decision_action_label(p public.decision_action) returns text
language sql immutable set search_path = '' as $$
  select case p
    when 'confirm_fields' then 'Confirmed'          when 'short_pay' then 'Short-pay'
    when 'approve_as_is' then 'Approved as-is'      when 'dispute' then 'Disputed'
    when 'link_po' then 'PO linked'                 when 'approve_without_po' then 'Approved without PO'
    when 'merge' then 'Merged'                      when 'reject_copy' then 'Second copy rejected'
    when 'not_duplicate' then 'Marked not a duplicate'
    when 'request_w9' then 'W-9 re-verification requested'
    when 'release_hold' then 'Hold released'        when 'reject_invoice' then 'Invoice rejected'
    when 'retry_posting' then 'Posting retried' end
$$;

-- Wake (or annotate) the run parked on an exception. Returns the run id or null.
create or replace function public.ledgic_resume_run(
  p_exception public.exceptions, p_next_stage public.stage, p_decision jsonb,
  p_event_stage public.stage, p_summary text, p_wake boolean, p_actor uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare v_run public.pipeline_runs%rowtype;
begin
  select * into v_run from public.pipeline_runs r
   where r.wait_exception_id = p_exception.id
      or (r.id = p_exception.run_id and r.status = 'waiting')
   order by (r.wait_exception_id = p_exception.id) desc nulls last
   limit 1 for update;
  if not found then
    return null;
  end if;

  if p_wake then
    update public.pipeline_runs
       set status = 'running', next_stage = p_next_stage, next_attempt_at = now(),
           wait_exception_id = null, last_error = null,
           context = context || jsonb_build_object('decision', p_decision)
     where id = v_run.id;
  else
    update public.pipeline_runs
       set context = context || jsonb_build_object('decision', p_decision)
     where id = v_run.id;
  end if;

  insert into public.pipeline_events (org_id, run_id, stage, status, summary, detail)
  values (v_run.org_id, v_run.id, p_event_stage,
          case when p_wake then 'resumed'::public.event_status else 'waiting'::public.event_status end,
          p_summary,
          jsonb_build_object('actor_id', p_actor, 'exception_id', p_exception.id,
                             'action', p_decision ->> 'action', 'approval_id', p_decision ->> 'approval_id',
                             'next_stage', case when p_wake then p_next_stage end));

  if p_wake then
    perform pg_notify('ledgic_runs', v_run.id::text);
  end if;
  return v_run.id;
end $$;

------------------------------------------------------------------------------------------------
-- 1. rpc_confirm_fields — extraction review confirm / correct
------------------------------------------------------------------------------------------------
create or replace function public.rpc_confirm_fields(p_invoice_id uuid, p_fields jsonb, p_time_spent int default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_uid uuid := auth.uid();
  v_actor_type public.actor_type := public.ledgic_actor_type();
  v_exc public.exceptions%rowtype;
  v_inv public.invoices%rowtype;
  v_role public.member_role;
  v_item jsonb;
  v_field text;
  v_key text;
  v_val text;
  v_num numeric;
  v_date date;
  v_prev public.invoice_fields%rowtype;
  v_line public.invoice_lines%rowtype;
  v_old text;
  v_old_conf numeric;
  v_is_changed boolean;
  v_monetary boolean;
  v_changed int := 0;
  v_new_id uuid;
  v_version int;
  v_approval uuid;
  v_run uuid;
  v_name text;
  v_spent int;
begin
  if v_uid is null then
    perform public.ledgic_error('FORBIDDEN', 'Not signed in');
  end if;

  select * into v_inv from public.invoices where id = p_invoice_id;
  if not found or not public.is_member(v_inv.org_id) then
    perform public.ledgic_error('NOT_FOUND', 'Invoice not found');
  end if;

  v_role := public.member_role_of(v_inv.org_id);
  if public.role_rank(v_role) < 1 then
    perform public.ledgic_error('FORBIDDEN', 'Read-only access');
  end if;

  -- Lock order everywhere: exception, then invoice.
  select * into v_exc from public.exceptions
   where invoice_id = p_invoice_id and type = 'extraction_review' and status <> 'resolved'
   order by opened_at limit 1 for update;
  if not found then
    perform public.ledgic_error('CONFLICT', 'No open extraction review for this invoice');
  end if;
  select * into v_inv from public.invoices where id = p_invoice_id for update;

  if p_fields is null or jsonb_typeof(p_fields) <> 'array' then
    perform public.ledgic_error('INVALID', 'Fields must be a list');
  end if;

  for v_item in select value from jsonb_array_elements(p_fields) loop
    v_val := nullif(btrim(v_item ->> 'value'), '');

    if v_item ? 'line_id' then
      -------------------------------------------------------------------- line cell
      v_key := v_item ->> 'key';
      select * into v_line from public.invoice_lines
       where id = public.try_uuid(v_item ->> 'line_id') and invoice_id = p_invoice_id for update;
      if not found then
        perform public.ledgic_error('INVALID', 'Unknown invoice line');
      end if;
      if v_key is null or v_key not in ('qty', 'unit_price', 'amount', 'description', 'uom') then
        perform public.ledgic_error('INVALID', 'Unknown line field');
      end if;
      if v_val is null then
        perform public.ledgic_error('INVALID', format('A value is required for %s', v_key));
      end if;
      v_old_conf := case when jsonb_typeof(v_line.confidences -> v_key) = 'number'
                         then (v_line.confidences ->> v_key)::numeric end;

      if v_key in ('qty', 'unit_price', 'amount') then
        v_num := public.ledgic_parse_amount(v_val, replace(v_key, '_', ' '));
        v_old := case v_key when 'qty' then v_line.qty::text when 'unit_price' then v_line.unit_price::text
                            else v_line.amount::text end;
        v_is_changed := (case v_key when 'qty' then v_line.qty when 'unit_price' then v_line.unit_price
                                    else v_line.amount end) is distinct from v_num;
        v_val := v_num::text;
      else
        v_old := case v_key when 'description' then v_line.description else v_line.uom end;
        v_is_changed := v_old is distinct from v_val;
      end if;

      update public.invoice_lines
         set qty         = case when v_key = 'qty' then v_num else qty end,
             unit_price  = case when v_key = 'unit_price' then v_num else unit_price end,
             amount      = case when v_key = 'amount' then v_num else amount end,
             description = case when v_key = 'description' then v_val else description end,
             uom         = case when v_key = 'uom' then v_val else uom end,
             confidences = jsonb_set(coalesce(confidences, '{}'::jsonb), array[v_key], to_jsonb(1.0))
       where id = v_line.id;

      v_monetary := v_is_changed and v_key in ('qty', 'unit_price', 'amount');
      perform public.audit_write(v_inv.org_id, v_actor_type, v_uid::text,
        case when v_is_changed then 'field.corrected' else 'field.confirmed' end,
        'invoice_line', v_line.id::text,
        jsonb_build_object('field', v_key, 'line_no', v_line.line_no, 'value', v_old, 'confidence', v_old_conf),
        jsonb_build_object('field', v_key, 'line_no', v_line.line_no, 'value', v_val, 'confidence', 1.0,
                           'invoice_id', p_invoice_id, 'monetary', v_monetary));

    elsif v_item ? 'field' then
      -------------------------------------------------------------------- header field
      v_field := v_item ->> 'field';
      if v_field is null or v_field !~ '^[a-z_]{1,40}$' then
        perform public.ledgic_error('INVALID', 'Unknown field');
      end if;
      if v_field in ('subtotal', 'total') then
        v_num := public.ledgic_parse_amount(v_val, v_field);
        v_val := v_num::text;
      elsif v_field in ('tax', 'freight') then
        v_num := public.ledgic_parse_amount(coalesce(v_val, '0'), v_field, true);
        v_val := v_num::text;
      elsif v_field in ('invoice_date', 'due_date') then
        if v_val is null then
          perform public.ledgic_error('INVALID', format('A value is required for %s', replace(v_field, '_', ' ')));
        end if;
        v_date := public.ledgic_parse_date(v_val, replace(v_field, '_', ' '));
        v_val := v_date::text;
      elsif v_field in ('invoice_number', 'vendor_name') and v_val is null then
        perform public.ledgic_error('INVALID', format('A value is required for %s', replace(v_field, '_', ' ')));
      end if;

      select * into v_prev from public.invoice_fields
       where invoice_id = p_invoice_id and field = v_field order by version desc limit 1;
      v_version := coalesce(v_prev.version, 0) + 1;
      v_old := v_prev.value;
      if v_field in ('subtotal', 'total', 'tax', 'freight') then
        v_is_changed := public.ledgic_try_numeric(v_old) is distinct from v_num;
      else
        v_is_changed := v_old is distinct from v_val;
      end if;

      insert into public.invoice_fields (invoice_id, field, value, confidence, raw_confidence, bbox, source, version, set_by)
      values (p_invoice_id, v_field, v_val, 1.000, v_prev.raw_confidence, v_prev.bbox, 'human', v_version, v_uid)
      returning id into v_new_id;

      update public.invoices
         set invoice_number = case when v_field = 'invoice_number' then v_val else invoice_number end,
             invoice_date   = case when v_field = 'invoice_date' then v_date else invoice_date end,
             due_date       = case when v_field = 'due_date' then v_date else due_date end,
             terms          = case when v_field = 'terms' then v_val else terms end,
             subtotal       = case when v_field = 'subtotal' then v_num else subtotal end,
             tax            = case when v_field = 'tax' then v_num else tax end,
             freight        = case when v_field = 'freight' then v_num else freight end,
             total          = case when v_field = 'total' then v_num else total end
       where id = p_invoice_id;

      v_monetary := v_is_changed and v_field in ('total', 'subtotal', 'tax', 'freight');
      perform public.audit_write(v_inv.org_id, v_actor_type, v_uid::text,
        case when v_is_changed then 'field.corrected' else 'field.confirmed' end,
        'invoice_field', v_new_id::text,
        jsonb_build_object('field', v_field, 'value', v_old, 'confidence', v_prev.confidence, 'version', v_prev.version),
        jsonb_build_object('field', v_field, 'value', v_val, 'confidence', 1.0, 'version', v_version,
                           'invoice_id', p_invoice_id, 'monetary', v_monetary));
    else
      perform public.ledgic_error('INVALID', 'Each item needs "field" or "line_id"');
    end if;

    if v_is_changed then
      v_changed := v_changed + 1;
    end if;
  end loop;

  update public.invoices
     set gate_passed = true, human_touches = human_touches + 1, touchless = false, status = 'extracted'
   where id = p_invoice_id;

  v_spent := least(greatest(coalesce(p_time_spent,
               extract(epoch from now() - v_exc.first_viewed_at)::int), 0), 1800);

  update public.exceptions set status = 'resolved', resolved_at = now() where id = v_exc.id;

  insert into public.approvals (org_id, exception_id, actor_id, action, comment, time_spent_seconds)
  values (v_exc.org_id, v_exc.id, v_uid, 'confirm_fields', null, v_spent)
  returning id into v_approval;

  perform public.audit_write(v_exc.org_id, v_actor_type, v_uid::text, 'decision.confirm_fields', 'approval',
    v_approval::text, null,
    jsonb_build_object('exception_id', v_exc.id, 'invoice_id', p_invoice_id, 'action', 'confirm_fields',
                       'changed', v_changed, 'time_spent_seconds', v_spent));
  perform public.audit_write(v_exc.org_id, v_actor_type, v_uid::text, 'exception.resolved', 'exception',
    v_exc.id::text, jsonb_build_object('status', v_exc.status),
    jsonb_build_object('status', 'resolved', 'invoice_id', p_invoice_id, 'approval_id', v_approval));

  select full_name into v_name from public.profiles where user_id = v_uid;
  v_run := public.ledgic_resume_run(v_exc, 'enrichment',
    jsonb_build_object('action', 'confirm_fields', 'approval_id', v_approval, 'actor_id', v_uid,
                       'changed', v_changed, 'pay_amount', null, 'hold_amount', null, 'extra', '{}'::jsonb),
    'review', 'Confirmed by ' || coalesce(v_name, 'a reviewer'), true, v_uid);

  return jsonb_build_object('approval_id', v_approval, 'run_id', v_run, 'changed', v_changed);
end $$;

create or replace function public.ledgic_try_numeric(p text) returns numeric
language plpgsql immutable set search_path = '' as $$
begin
  return replace(replace(btrim(p), ',', ''), '$', '')::numeric;
exception when others then
  return null;
end $$;

------------------------------------------------------------------------------------------------
-- 2. rpc_decide_exception — every money / duplicate / fraud / posting decision
------------------------------------------------------------------------------------------------
create or replace function public.rpc_decide_exception(
  p_exception_id uuid,
  p_action public.decision_action,
  p_pay_amount numeric default null,
  p_hold_amount numeric default null,
  p_comment text default null,
  p_time_spent int default null,
  p_extra jsonb default '{}')
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_uid uuid := auth.uid();
  v_actor_type public.actor_type := public.ledgic_actor_type();
  v_exc public.exceptions%rowtype;
  v_inv public.invoices%rowtype;
  v_rec public.recommendations%rowtype;
  v_role public.member_role;
  v_rank int;
  v_need int;
  v_need_label text;
  v_limit numeric;
  v_impact numeric;
  v_pay numeric := p_pay_amount;
  v_hold numeric := p_hold_amount;
  v_extra jsonb := coalesce(p_extra, '{}'::jsonb);
  v_comment text := nullif(btrim(p_comment), '');
  v_new_status public.exception_status;
  v_next public.stage;
  v_wake boolean;
  v_approval uuid;
  v_run uuid;
  v_name text;
  v_spent int;
  v_cand uuid;
  v_keep uuid;
  v_copy uuid;
  v_po public.purchase_orders%rowtype;
  v_vendor_creator uuid;
  v_before jsonb;
  v_allowed public.decision_action[];
begin
  if v_uid is null then
    perform public.ledgic_error('FORBIDDEN', 'Not signed in');
  end if;

  -- 1. existence / membership / state
  select * into v_exc from public.exceptions where id = p_exception_id for update;
  if not found or not public.is_member(v_exc.org_id) then
    perform public.ledgic_error('NOT_FOUND', 'Exception not found');
  end if;
  if v_exc.status = 'resolved' then
    perform public.ledgic_error('CONFLICT', 'This exception is already resolved');
  end if;
  select * into v_inv from public.invoices where id = v_exc.invoice_id for update;

  -- action valid for type
  v_allowed := case v_exc.type
    when 'price_variance' then array['short_pay','approve_as_is','dispute','reject_invoice']
    when 'qty_mismatch'   then array['short_pay','approve_as_is','dispute','reject_invoice']
    when 'unmatched_line' then array['short_pay','approve_as_is','dispute','reject_invoice']
    when 'no_po'          then array['link_po','approve_without_po','reject_invoice']
    when 'duplicate'      then array['merge','reject_copy','not_duplicate']
    when 'new_vendor_screen' then array['request_w9','release_hold','reject_invoice']
    when 'posting_failed' then array['retry_posting','reject_invoice']
    else array[]::text[] end::public.decision_action[];
  if p_action is null or not (p_action = any(v_allowed)) then
    perform public.ledgic_error('INVALID', 'Action not allowed for this exception');
  end if;

  -- 2. role
  v_role := public.member_role_of(v_exc.org_id);
  v_rank := public.role_rank(v_role);
  if v_rank < 1 then
    perform public.ledgic_error('FORBIDDEN', 'Read-only access');
  end if;
  if p_action = 'link_po' then
    v_need := 1;
  elsif p_action = 'not_duplicate' or (v_exc.type = 'new_vendor_screen' and p_action <> 'request_w9') then
    v_need := 3;
  else
    v_need := 2;
  end if;
  if v_rank < v_need then
    perform public.ledgic_error('FORBIDDEN', case v_need when 3 then 'Needs controller' else 'Needs AP manager' end);
  end if;

  -- amounts: short_pay defaults to the recommendation; approvals pay the invoice total
  select * into v_rec from public.recommendations where exception_id = v_exc.id;
  if p_action = 'short_pay' then
    if v_pay is null and v_hold is null and v_rec.action = 'short_pay' then
      v_pay := v_rec.pay_amount;
      v_hold := v_rec.hold_amount;
    elsif v_pay is null and v_hold is not null then
      v_pay := v_inv.total - v_hold;
    elsif v_hold is null and v_pay is not null then
      v_hold := v_inv.total - v_pay;
    end if;
  elsif p_action in ('approve_as_is', 'approve_without_po', 'release_hold', 'not_duplicate') then
    v_pay := coalesce(v_pay, v_inv.total);
    v_hold := coalesce(v_hold, 0);
  end if;

  -- 3. approval limit (ap_manager)
  v_impact := case when p_action = 'short_pay' then coalesce(v_hold, v_exc.amount_at_risk) else v_exc.amount_at_risk end;
  select manager_limit into v_limit from public.org_settings where org_id = v_exc.org_id;
  v_limit := coalesce(v_limit, 5000.00);
  if v_role = 'ap_manager' and p_action <> 'link_po' and coalesce(v_impact, 0) > v_limit then
    perform public.ledgic_error('FORBIDDEN', 'Above your approval limit of ' || public.ledgic_money(v_limit));
  end if;

  -- 4. comment / verification
  if p_action in ('approve_as_is', 'approve_without_po', 'not_duplicate', 'release_hold', 'dispute')
     and v_comment is null then
    perform public.ledgic_error('INVALID', 'A comment is required for this decision');
  end if;
  if p_action = 'release_hold'
     and not (coalesce((v_extra ->> 'verified_by_phone')::boolean, false)
              or coalesce((v_extra ->> 'verified')::boolean, false)) then
    perform public.ledgic_error('INVALID', 'Confirm you verified the bank details with the vendor by phone');
  end if;

  -- 5. amounts consistent
  if p_action = 'short_pay' then
    if v_pay is null or v_hold is null then
      perform public.ledgic_error('INVALID', 'Pay and hold amounts are required for a short-pay');
    end if;
    if v_hold <= 0 or v_pay < 0 then
      perform public.ledgic_error('INVALID', 'The held amount must be greater than 0');
    end if;
    if abs(v_pay + v_hold - coalesce(v_inv.total, 0)) > 0.01 then
      perform public.ledgic_error('INVALID', 'Pay and hold must add up to the invoice total of '
                                             || public.ledgic_money(coalesce(v_inv.total, 0)));
    end if;
  end if;

  -- 6. segregation of duties
  if p_action <> 'link_po' and (
       exists (select 1 from public.invoice_fields f
                 join public.audit_log a on a.org_id = v_exc.org_id and a.entity_type = 'invoice_field'
                                        and a.entity_id = f.id::text
                where f.invoice_id = v_exc.invoice_id and f.source = 'human' and f.set_by = v_uid
                  and a.after ->> 'monetary' = 'true')
    or exists (select 1 from public.invoice_lines l
                 join public.audit_log a on a.org_id = v_exc.org_id and a.entity_type = 'invoice_line'
                                        and a.entity_id = l.id::text
                where l.invoice_id = v_exc.invoice_id and a.actor_id = v_uid::text
                  and a.after ->> 'monetary' = 'true')) then
    perform public.ledgic_error('FORBIDDEN', 'You edited this invoice''s amounts, so someone else must approve it');
  end if;
  if p_action = 'release_hold' then
    select created_by into v_vendor_creator from public.vendors where id = v_inv.vendor_id;
    if v_vendor_creator = v_uid then
      perform public.ledgic_error('FORBIDDEN', 'You created this vendor record');
    end if;
  end if;

  -- link_po validation
  if p_action = 'link_po' then
    select * into v_po from public.purchase_orders
     where id = public.try_uuid(v_extra ->> 'po_id') and org_id = v_exc.org_id;
    if not found or v_po.vendor_id is distinct from v_inv.vendor_id then
      perform public.ledgic_error('INVALID', 'Choose a purchase order from this vendor');
    end if;
  end if;

  -- duplicate pair
  if p_action in ('merge', 'reject_copy') then
    select candidate_invoice_id into v_cand from public.duplicate_candidates
     where invoice_id = v_exc.invoice_id order by similarity desc, created_at limit 1;
    if p_action = 'merge' then
      if v_cand is null then
        perform public.ledgic_error('INVALID', 'No duplicate candidate recorded for this invoice');
      end if;
      v_keep := public.try_uuid(v_extra ->> 'keep_invoice_id');
      if v_keep is null then
        select i.id into v_keep from public.invoices i where i.id in (v_exc.invoice_id, v_cand)
         order by i.received_at, i.created_at limit 1;
      elsif v_keep not in (v_exc.invoice_id, v_cand) then
        perform public.ledgic_error('INVALID', 'Keep one of the two copies');
      end if;
      v_copy := case when v_keep = v_exc.invoice_id then v_cand else v_exc.invoice_id end;
    else
      v_copy := v_exc.invoice_id;
      v_keep := v_cand;
    end if;
  end if;

  ------------------------------------------------------------------ effects
  v_spent := least(greatest(coalesce(p_time_spent,
               extract(epoch from now() - v_exc.first_viewed_at)::int), 0), 1800);

  insert into public.approvals (org_id, exception_id, actor_id, action, pay_amount, hold_amount, comment, time_spent_seconds)
  values (v_exc.org_id, v_exc.id, v_uid, p_action, v_pay, v_hold, v_comment, v_spent)
  returning id into v_approval;

  perform public.audit_write(v_exc.org_id, v_actor_type, v_uid::text, 'decision.' || p_action::text, 'approval',
    v_approval::text, null,
    jsonb_build_object('exception_id', v_exc.id, 'invoice_id', v_exc.invoice_id, 'action', p_action,
                       'pay_amount', v_pay, 'hold_amount', v_hold, 'comment', v_comment, 'extra', v_extra,
                       'role', v_role, 'time_spent_seconds', v_spent));

  v_new_status := case p_action when 'dispute' then 'disputed'::public.exception_status
                                when 'request_w9' then 'awaiting_vendor'::public.exception_status
                                else 'resolved'::public.exception_status end;
  update public.exceptions
     set status = v_new_status,
         resolved_at = case when v_new_status = 'resolved' then now() else resolved_at end
   where id = v_exc.id;
  perform public.audit_write(v_exc.org_id, v_actor_type, v_uid::text, 'exception.' || v_new_status::text,
    'exception', v_exc.id::text, jsonb_build_object('status', v_exc.status),
    jsonb_build_object('status', v_new_status, 'invoice_id', v_exc.invoice_id, 'approval_id', v_approval));

  -- invoice side effects
  v_before := jsonb_build_object('status', v_inv.status, 'po_id', v_inv.po_id, 'duplicate_of', v_inv.duplicate_of);
  update public.invoices
     set human_touches = human_touches + 1, touchless = false,
         status = case
           when p_action = 'reject_invoice' then 'rejected'::public.invoice_status
           when p_action in ('short_pay', 'approve_as_is', 'approve_without_po', 'release_hold', 'not_duplicate')
             then 'approved'::public.invoice_status
           when p_action in ('merge', 'reject_copy') and id = v_copy then 'duplicate'::public.invoice_status
           when p_action = 'merge' and id = v_keep then 'approved'::public.invoice_status
           else status end,
         duplicate_of = case when p_action in ('merge', 'reject_copy') and id = v_copy then v_keep else duplicate_of end,
         po_id = case when p_action = 'link_po' then v_po.id else po_id end
   where id = v_exc.invoice_id;
  perform public.audit_write(v_exc.org_id, v_actor_type, v_uid::text, 'invoice.updated', 'invoice',
    v_exc.invoice_id::text, v_before,
    (select jsonb_build_object('status', i.status, 'po_id', i.po_id, 'duplicate_of', i.duplicate_of,
                               'invoice_id', i.id, 'approval_id', v_approval)
       from public.invoices i where i.id = v_exc.invoice_id));

  -- merge that keeps the held copy: the other (earlier) copy becomes the duplicate
  if p_action = 'merge' and v_copy is distinct from v_exc.invoice_id then
    update public.invoices set status = 'duplicate', duplicate_of = v_keep where id = v_copy;
    perform public.audit_write(v_exc.org_id, v_actor_type, v_uid::text, 'invoice.updated', 'invoice',
      v_copy::text, null,
      jsonb_build_object('status', 'duplicate', 'duplicate_of', v_keep, 'invoice_id', v_copy,
                         'approval_id', v_approval));
  end if;

  -- resume the parked run
  v_wake := p_action not in ('dispute', 'request_w9');
  v_next := case
    when p_action in ('link_po', 'release_hold', 'not_duplicate') then 'match'::public.stage
    when p_action in ('retry_posting', 'short_pay', 'approve_as_is', 'approve_without_po') then 'posting'::public.stage
    else 'close'::public.stage end;
  select full_name into v_name from public.profiles where user_id = v_uid;
  v_run := public.ledgic_resume_run(v_exc, v_next,
    jsonb_build_object('action', p_action, 'pay_amount', v_pay, 'hold_amount', v_hold,
                       'approval_id', v_approval, 'actor_id', v_uid, 'comment', v_comment,
                       'extra', v_extra || case when v_po.id is not null then jsonb_build_object('po_id', v_po.id)
                                                when v_keep is not null then jsonb_build_object('keep_invoice_id', v_keep, 'duplicate_invoice_id', v_copy)
                                                else '{}'::jsonb end),
    'approval', public.decision_action_label(p_action) || ' by ' || coalesce(v_name, 'a reviewer'), v_wake, v_uid);

  return jsonb_build_object('approval_id', v_approval, 'run_id', v_run, 'exception_status', v_new_status);
end $$;

------------------------------------------------------------------------------------------------
-- 3. rpc_mark_exception_viewed
------------------------------------------------------------------------------------------------
create or replace function public.rpc_mark_exception_viewed(p_exception_id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare v_exc public.exceptions%rowtype;
begin
  if auth.uid() is null then
    perform public.ledgic_error('FORBIDDEN', 'Not signed in');
  end if;
  select * into v_exc from public.exceptions where id = p_exception_id;
  if not found or not public.is_member(v_exc.org_id) then
    perform public.ledgic_error('NOT_FOUND', 'Exception not found');
  end if;
  update public.exceptions set first_viewed_at = now() where id = p_exception_id and first_viewed_at is null;
  insert into public.ui_events (org_id, user_id, exception_id, kind) values (v_exc.org_id, auth.uid(), p_exception_id, 'opened');
end $$;

------------------------------------------------------------------------------------------------
-- 4. audit_verify_org
------------------------------------------------------------------------------------------------
create or replace function public.audit_verify_org(p_org uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare v_broken bigint; v_entries bigint; v_head text;
begin
  if not public.is_member(p_org) and not public.ledgic_is_service() then
    perform public.ledgic_error('FORBIDDEN', 'Not a member of this organization');
  end if;
  v_broken := public.audit_verify(p_org);
  select count(*) into v_entries from public.audit_log where org_id = p_org;
  select hash into v_head from public.audit_log where org_id = p_org order by id desc limit 1;
  return jsonb_build_object('ok', v_broken is null, 'entries', v_entries, 'first_broken_id', v_broken, 'head_hash', v_head);
end $$;

------------------------------------------------------------------------------------------------
-- 5. LLM budget (global daily cap, UTC day)
------------------------------------------------------------------------------------------------
create or replace function public.llm_budget_reserve(p_est numeric, p_cap numeric default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  v_day date := (now() at time zone 'utc')::date;
  v_cap numeric := coalesce(p_cap, public.ledgic_try_numeric(current_setting('ledgic.llm_daily_cap_usd', true)), 0.50);
  v_id uuid;
begin
  if p_est is null or p_est < 0 then
    perform public.ledgic_error('INVALID', 'Estimate must be >= 0');
  end if;
  insert into public.llm_budget (day, cap_usd) values (v_day, v_cap) on conflict (day) do nothing;
  if p_cap is not null then
    update public.llm_budget set cap_usd = p_cap where day = v_day and cap_usd <> p_cap;
  end if;
  update public.llm_budget set reserved_usd = reserved_usd + p_est
   where day = v_day and spent_usd + reserved_usd + p_est <= cap_usd;
  if not found then
    return null;
  end if;
  insert into public.llm_budget_reservations (day, est_usd) values (v_day, p_est) returning id into v_id;
  return v_id;
end $$;

create or replace function public.llm_budget_settle(p_reservation uuid, p_actual numeric) returns void
language plpgsql security definer set search_path = '' as $$
declare r public.llm_budget_reservations%rowtype;
begin
  select * into r from public.llm_budget_reservations where id = p_reservation for update;
  if not found or r.status <> 'reserved' then
    return;  -- idempotent
  end if;
  update public.llm_budget
     set reserved_usd = greatest(0, reserved_usd - r.est_usd), spent_usd = spent_usd + coalesce(p_actual, 0)
   where day = r.day;
  update public.llm_budget_reservations
     set actual_usd = coalesce(p_actual, 0), settled_at = now(),
         status = case when coalesce(p_actual, 0) = 0 then 'released' else 'settled' end
   where id = r.id;
end $$;

create or replace function public.llm_budget_release_stale() returns int
language plpgsql security definer set search_path = '' as $$
declare r record; n int := 0;
begin
  for r in select id from public.llm_budget_reservations
            where status = 'reserved' and created_at < now() - interval '10 minutes' loop
    perform public.llm_budget_settle(r.id, 0);
    n := n + 1;
  end loop;
  return n;
end $$;

------------------------------------------------------------------------------------------------
-- 6. kb_search — hybrid retrieval with reciprocal-rank fusion (k = 60). Security invoker.
------------------------------------------------------------------------------------------------
create or replace function public.kb_search(
  p_org uuid, p_query_embedding extensions.vector(512), p_query_text text,
  p_k int default 8, p_kinds text[] default null)
returns table (chunk_id uuid, document_id uuid, title text, kind text, contract_id uuid, vendor_id uuid,
               heading_path text, clause_ref text, content text,
               vector_rank int, text_rank int, rrf_score double precision)
language sql stable set search_path = '' as $$
  with vec as (
    select x.id, row_number() over (order by x.dist, x.id)::int as rnk
    from (select c.id, c.embedding operator(extensions.<=>) p_query_embedding as dist
            from public.kb_chunks c join public.kb_documents d on d.id = c.document_id
           where p_query_embedding is not null and c.org_id = p_org and c.embedding is not null
             and (p_kinds is null or d.kind = any(p_kinds))
           order by c.embedding operator(extensions.<=>) p_query_embedding
           limit 40) x
  ),
  q as (select websearch_to_tsquery('english'::regconfig, coalesce(p_query_text, '')) as tsq),
  txt as (
    select x.id, row_number() over (order by x.score desc, x.id)::int as rnk
    from (select c.id, ts_rank_cd(c.tsv, q.tsq) as score
            from public.kb_chunks c join public.kb_documents d on d.id = c.document_id, q
           where c.org_id = p_org and c.tsv @@ q.tsq
             and (p_kinds is null or d.kind = any(p_kinds))
           order by ts_rank_cd(c.tsv, q.tsq) desc
           limit 40) x
  ),
  fused as (
    select coalesce(vec.id, txt.id) as id, vec.rnk as vector_rank, txt.rnk as text_rank,
           coalesce(1.0 / (60 + vec.rnk), 0) + coalesce(1.0 / (60 + txt.rnk), 0) as rrf
    from vec full join txt on txt.id = vec.id
  )
  select c.id, c.document_id, d.title, d.kind, d.contract_id, d.vendor_id, c.heading_path, c.clause_ref, c.content,
         f.vector_rank, f.text_rank, f.rrf::double precision
  from fused f join public.kb_chunks c on c.id = f.id join public.kb_documents d on d.id = c.document_id
  order by f.rrf desc, c.id
  limit greatest(coalesce(p_k, 8), 1)
$$;

------------------------------------------------------------------------------------------------
-- 7. rate_limit_hit — fixed window counter; true when over the limit
------------------------------------------------------------------------------------------------
create or replace function public.rate_limit_hit(p_key text, p_limit int, p_window_seconds int) returns boolean
language plpgsql security definer set search_path = '' as $$
declare v_count int;
begin
  insert into public.rate_limits as r (key, window_start, count) values (p_key, now(), 1)
  on conflict (key) do update
    set window_start = case when r.window_start < now() - make_interval(secs => p_window_seconds)
                            then now() else r.window_start end,
        count = case when r.window_start < now() - make_interval(secs => p_window_seconds)
                     then 1 else r.count + 1 end
  returning count into v_count;
  return v_count > p_limit;
end $$;

------------------------------------------------------------------------------------------------
-- 8. demo_purge_org — nightly/monthly demo reset (service role only; refuses non-demo orgs)
--    p_keep_master = true keeps org, members, settings and master data and deletes only
--    transactional data (documents → invoices → everything downstream, runs, costs, audit).
------------------------------------------------------------------------------------------------
create or replace function public.demo_purge_org(p_org uuid, p_keep_master boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare v_audit bigint; v_docs bigint;
begin
  if not exists (select 1 from public.orgs where id = p_org and is_demo) then
    perform public.ledgic_error('FORBIDDEN', 'Only demo organizations can be purged');
  end if;
  perform set_config('ledgic.allow_audit_purge', 'on', true);
  delete from public.audit_log where org_id = p_org;
  get diagnostics v_audit = row_count;
  perform set_config('ledgic.allow_audit_purge', 'off', true);

  if p_keep_master then
    update public.pipeline_runs set wait_exception_id = null where org_id = p_org;
    delete from public.documents where org_id = p_org;          -- invoices, runs, events, exceptions, approvals …
    get diagnostics v_docs = row_count;
    delete from public.cost_ledger where org_id = p_org;
    delete from public.dead_letters where org_id = p_org;
    delete from public.ui_events where org_id = p_org;
    delete from public.copilot_cache where org_id = p_org;
    delete from public.goods_receipts where org_id = p_org;
    delete from public.purchase_orders where org_id = p_org;
  else
    select count(*) into v_docs from public.documents where org_id = p_org;
    update public.pipeline_runs set wait_exception_id = null where org_id = p_org;
    delete from public.orgs where id = p_org;                    -- cascades to every org table
  end if;
  return jsonb_build_object('org_id', p_org, 'audit_rows', v_audit, 'documents', v_docs, 'kept_master', p_keep_master);
end $$;

------------------------------------------------------------------------------------------------
-- 9. Grants
------------------------------------------------------------------------------------------------
revoke execute on all functions in schema public from public, anon;

grant execute on function
  public.rpc_confirm_fields(uuid, jsonb, int),
  public.rpc_decide_exception(uuid, public.decision_action, numeric, numeric, text, int, jsonb),
  public.rpc_mark_exception_viewed(uuid),
  public.audit_verify_org(uuid),
  public.audit_verify(uuid),
  public.kb_search(uuid, extensions.vector, text, int, text[]),
  public.rate_limit_hit(text, int, int),
  public.is_member(uuid), public.has_role(uuid, public.member_role[]), public.member_role_of(uuid),
  public.shares_org(uuid), public.role_rank(public.member_role), public.try_uuid(text),
  public.decision_action_label(public.decision_action), public.ledgic_money(numeric)
to authenticated;

grant execute on all functions in schema public to service_role;

-- Internal-only helpers: browser roles never call these directly (security definer writers).
revoke execute on function public.audit_write(uuid, public.actor_type, text, text, text, text, jsonb, jsonb),
  public.ledgic_resume_run(public.exceptions, public.stage, jsonb, public.stage, text, boolean, uuid),
  public.llm_budget_reserve(numeric, numeric), public.llm_budget_settle(uuid, numeric),
  public.llm_budget_release_stale(), public.demo_purge_org(uuid, boolean)
from authenticated;

-- Supabase grants execute on new functions to anon/authenticated by default; keep new ones closed.
alter default privileges in schema public revoke execute on functions from public, anon;
