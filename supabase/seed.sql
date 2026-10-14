-- Intentionally light. `supabase db reset` runs this file; it does not load demo data.
-- The Northside demo tenant (orgs, users, master data, history, eval runs) is seeded by:
--     cd services/core && uv run python -m app.demo.seed --reset
-- (see services/core/app/demo/seed.py). Keeping the seed in Python lets it share the
-- deterministic corpus catalog with the replay and create Auth users through GoTrue.
select 1;
