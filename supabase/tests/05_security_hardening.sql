-- Security hardening (migration 20261016000007): browser roles cannot drive rate limits or write storage
-- directly, and demo personas' credentials are pinned.
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

insert into auth.users (id, aud, role, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'authenticated', 'authenticated', 'viewer@a.test'),
  ('aaaaaaaa-0000-0000-0000-000000000003', 'authenticated', 'authenticated', 'manager@a.test');
insert into public.orgs (id, slug, name, is_demo, timezone) values
  ('0a000000-0000-0000-0000-000000000000', 'org-a', 'Org A', true, 'America/New_York');
insert into public.memberships (org_id, user_id, role) values
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000001', 'viewer'),
  ('0a000000-0000-0000-0000-000000000000', 'aaaaaaaa-0000-0000-0000-000000000003', 'ap_manager');

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

select plan(9);

-- 1. rate_limit_hit is service-only
select ok(not has_function_privilege('authenticated', 'public.rate_limit_hit(text, int, int)', 'execute'),
  'authenticated cannot execute rate_limit_hit');
select ok(not has_function_privilege('anon', 'public.rate_limit_hit(text, int, int)', 'execute'),
  'anon cannot execute rate_limit_hit');
select ok(has_function_privilege('service_role', 'public.rate_limit_hit(text, int, int)', 'execute'),
  'service_role can execute rate_limit_hit');

select pg_temp.login('aaaaaaaa-0000-0000-0000-000000000001');
select throws_ok($q$select public.rate_limit_hit('copilot:user:x', 60, 0)$q$, '42501', null,
  'the demo viewer cannot reset a rate limit');
select pg_temp.logout();

-- 2. a zero window no longer resets the counter
select is(public.rate_limit_hit('t:zero', 1, 0), false, 'first hit is under the limit');
select is(public.rate_limit_hit('t:zero', 1, 0), true, 'a zero window is clamped to 1s, so the second hit counts');

-- 3. storage: no direct browser uploads
select is((select count(*)::int from pg_policies where schemaname = 'storage' and tablename = 'objects'
           and policyname = 'ledgic_documents_member_upload'), 0, 'member upload policy is gone');

-- 4. demo credentials are pinned by a trigger, and new functions stay closed to browser roles
select is((select count(*)::int from pg_trigger where tgname = 'ledgic_pin_demo_credentials'
           and tgrelid = 'auth.users'::regclass), 1, 'demo credential trigger installed');
select ok(not has_function_privilege('authenticated', 'public.ledgic_pin_demo_credentials()', 'execute'),
  'trigger function is not callable by browser roles');

select * from finish();
rollback;
