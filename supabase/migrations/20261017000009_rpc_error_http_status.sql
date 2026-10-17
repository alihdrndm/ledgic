-- RPC errors carry their HTTP status (2026-10-17). PostgREST answers a raised SQLSTATE 'PTxyz' with HTTP xyz;
-- the old codes came back as 500 (P0002, NOT_FOUND) and 400 (P0001 CONFLICT, 22023 INVALID). Clients parse
-- the LEDGIC_<CODE>: message prefix, which is unchanged. FORBIDDEN keeps 42501 (already 403).
create or replace function public.ledgic_error(p_code text, p_msg text) returns void
language plpgsql set search_path = '' as $$
begin
  raise exception using
    message = 'LEDGIC_' || p_code || ': ' || p_msg,
    errcode = case p_code when 'FORBIDDEN' then '42501' when 'NOT_FOUND' then 'PT404'
                          when 'CONFLICT' then 'PT409' when 'INVALID' then 'PT422' else 'P0001' end;
end $$;
