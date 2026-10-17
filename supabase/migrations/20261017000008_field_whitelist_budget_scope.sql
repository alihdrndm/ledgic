-- Deferred hardening (2026-10-17).

------------------------------------------------------------------------------------------------
-- 1. rpc_confirm_fields: header corrections are limited to the fields extraction actually produces.
--    The old check accepted any [a-z_] name, so a clerk could attach arbitrary fields to an invoice.
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
      if v_field is null or v_field not in ('vendor_name', 'invoice_number', 'invoice_date', 'due_date', 'terms',
          'po_reference', 'subtotal', 'tax', 'freight', 'total', 'currency', 'remit_to_name', 'remit_to_address',
          'remit_to', 'bank_details') then
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

------------------------------------------------------------------------------------------------
-- 2. llm_budget: members read today's row only (all v_ai_budget_today needs), not the spend history.
------------------------------------------------------------------------------------------------
drop policy if exists llm_budget_read on public.llm_budget;
create policy llm_budget_read on public.llm_budget for select to authenticated
  using (day = (now() at time zone 'utc')::date);
