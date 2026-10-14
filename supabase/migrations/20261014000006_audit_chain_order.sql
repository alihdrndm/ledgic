-- Audit chain: assign the row id under the per-org chain lock.
--
-- `id` (bigserial) used to be drawn from the sequence before the BEFORE INSERT trigger took the
-- advisory lock. Two concurrent writers (e.g. the replay tick and a backfill) could then get ids
-- 26 and 27, with 27 taking the lock first and linking to 25, and 26 linking to 27. The chain was
-- intact by link order but `audit_verify` walks it in id order and reported it broken. Drawing the
-- id after the lock (held until commit) makes id order equal chain order.

create or replace function public.audit_chain() returns trigger language plpgsql
security definer set search_path = '' as $$
declare p text;
begin
  perform pg_advisory_xact_lock(hashtext('audit:' || new.org_id::text));
  new.id := nextval(pg_get_serial_sequence('public.audit_log', 'id'));
  select hash into p from public.audit_log where org_id = new.org_id order by id desc limit 1;
  new.at := coalesce(new.at, clock_timestamp());
  new.prev_hash := coalesce(p, repeat('0',64));
  new.hash := public.audit_row_digest(new.prev_hash, new.org_id, new.at, new.actor_type, new.actor_id,
                                      new.action, new.entity_type, new.entity_id, new.before, new.after);
  return new;
end $$;
