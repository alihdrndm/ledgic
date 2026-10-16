-- Security hardening (2026-10-16). The public demo gives every visitor a real session (viewer or
-- Elena, ap_manager), so "authenticated" is effectively public: close what that role should not reach.

------------------------------------------------------------------------------------------------
-- 1. rate_limit_hit: service-only, and no zero-length windows (a caller-chosen window of 0 reset any
--    counter, and a huge one locked other visitors out).
------------------------------------------------------------------------------------------------
create or replace function public.rate_limit_hit(p_key text, p_limit int, p_window_seconds int) returns boolean
language plpgsql security definer set search_path = '' as $$
declare v_count int; v_window int := greatest(coalesce(p_window_seconds, 1), 1);
begin
  insert into public.rate_limits as r (key, window_start, count) values (p_key, now(), 1)
  on conflict (key) do update
    set window_start = case when r.window_start < now() - make_interval(secs => v_window)
                            then now() else r.window_start end,
        count = case when r.window_start < now() - make_interval(secs => v_window)
                     then 1 else r.count + 1 end
  returning count into v_count;
  return v_count > greatest(coalesce(p_limit, 1), 1);
end $$;

revoke execute on function public.rate_limit_hit(text, int, int) from public, anon, authenticated;
grant execute on function public.rate_limit_hit(text, int, int) to service_role;

------------------------------------------------------------------------------------------------
-- 2. rpc_decide_exception: a short-pay counts against the approval limit by the larger of what it holds
--    back and the overcharge it lets through (a 0.01 hold no longer slips a large variance under it).
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
  v_impact := case when p_action = 'short_pay'
                   then greatest(coalesce(v_hold, v_exc.amount_at_risk),
                                 coalesce(v_exc.amount_at_risk, 0) - coalesce(v_hold, 0))
                   else v_exc.amount_at_risk end;
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
-- 3. Storage: uploads only through server-issued signed URLs (role- and rate-checked); browser
--    sessions, including the public viewer, can no longer write objects directly.
------------------------------------------------------------------------------------------------
do $$
begin
  if to_regclass('storage.objects') is null then
    raise notice 'storage schema missing; skipping';
    return;
  end if;
  execute $p$drop policy if exists ledgic_documents_member_upload on storage.objects$p$;
end $$;

------------------------------------------------------------------------------------------------
-- 4. Demo personas: every visitor holds their session, so pin their credentials. Auth API updates
--    (user or admin) keep the password, email and phone; direct SQL as the owner can still rotate them.
------------------------------------------------------------------------------------------------
create or replace function public.ledgic_pin_demo_credentials() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if session_user <> 'postgres' and exists (  -- session_user: the connecting role, not the definer
    select 1 from public.memberships m join public.orgs o on o.id = m.org_id
    where m.user_id = old.id and o.is_demo
  ) then
    new.encrypted_password := old.encrypted_password;
    new.email := old.email;
    new.phone := old.phone;
  end if;
  return new;
end $$;

revoke execute on function public.ledgic_pin_demo_credentials() from public, anon, authenticated;

do $$
begin
  if to_regclass('auth.users') is null then
    raise notice 'auth schema missing; skipping';
    return;
  end if;
  execute 'drop trigger if exists ledgic_pin_demo_credentials on auth.users';
  execute 'create trigger ledgic_pin_demo_credentials before update on auth.users
           for each row execute function public.ledgic_pin_demo_credentials()';
end $$;

------------------------------------------------------------------------------------------------
-- 5. New functions stay closed to browser roles until granted explicitly.
------------------------------------------------------------------------------------------------
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;
