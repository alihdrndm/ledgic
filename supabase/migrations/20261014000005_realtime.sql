-- Ledgic 0005: Realtime publication (05-database.md §11). Clients subscribe with filter
-- org_id=eq.<id>; Realtime applies the table's RLS select policy per subscriber.
do $$
declare t text;
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
  foreach t in array array['pipeline_events', 'exceptions', 'approvals', 'erp_postings', 'pipeline_runs'] loop
    if not exists (select 1 from pg_publication_tables
                   where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;
