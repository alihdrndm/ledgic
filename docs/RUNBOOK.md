# Runbook

How to deploy, configure, rotate, reset and debug Ledgic. Secrets never go into git, chat or this file.
Set them in the provider dashboards or CLIs.

| Piece | Host | Production URL |
|---|---|---|
| Web (`apps/web`) | Vercel Hobby | https://ledgic-pearl.vercel.app |
| Core (`services/core`) | Railway | https://core-production-f996.up.railway.app (`/health`, `/mcp`) |
| Database, Auth, Storage, Realtime | Supabase Free | the project's dashboard |

## 1. Deploy

### 1.1 Supabase (database)

```bash
npx supabase login
npx supabase link --project-ref <project-ref>
npx supabase db push                     # applies supabase/migrations/*.sql in order
```

Then, in the Supabase dashboard:

- **Database → Extensions:** enable `pg_cron` if the migration reported it unavailable. Without it the core
  scheduler refreshes KPIs instead.
- **Auth → URL configuration:** Site URL = the Vercel URL. Add `https://ledgic-pearl.vercel.app/auth/callback`
  to the redirect allow-list.
- **Auth → Providers → Email:** turn off public sign-ups. Demo users are created by the seed via the admin API.
- **Storage:** the `documents` bucket is created by the migrations.

Seed the demo tenant from a machine that has the **production** env vars loaded (from the repo root
`.env`, or exported in the shell):

```bash
cd services/core
uv sync
uv run python -m app.demo.seed                     # org, users, master data, contracts, eval history
uv run python -m app.ai.seed_kb                    # knowledge base + precomputed copilot answers
uv run python -m app.demo.backfill --days 30 --today
uv run python -m app.mcp.tokens demo               # mint MCP_DEMO_TOKEN for the demo viewer (read-only)
```

All four commands are idempotent.

### 1.2 Railway (core)

The repo-root `railway.json` builds `services/core/Dockerfile` with the **repo root as build context**,
because the image also needs `tools/corpus/kb`, `tools/corpus/fixtures` and `contracts/fixtures.json`.
It runs one replica, health-checks `/health` and restarts on failure. `.railwayignore` keeps the web app,
docs and Supabase files out of the upload.

```bash
railway login
railway link                 # select the ledgic project / core service
railway up                   # or connect the GitHub repo for deploy-on-push from main
```

Set the variables from §2 in the service's **Variables** tab. Railway provides `PORT` and
`RAILWAY_GIT_COMMIT_SHA` (shown as `version` in `/health`).

Check the deploy:

```bash
curl -s https://core-production-f996.up.railway.app/health
# expect "status":"ok", "db":true, "worker":{"alive":true,...}, "scheduler":{"leader":true,...}
```

### 1.3 Vercel (web)

- Project **Root Directory: `apps/web`**, framework Next.js. Install command `pnpm install`, which runs from
  the workspace root so `@ledgic/db-types` resolves.
- Set the web variables from §2 for Production (and Preview if you use it).
- Deploy with `npx vercel --prod`, or push to `main` with the Git integration.

### 1.4 After deploying

1. Open the web app → **Open the demo**. All five screens should show data, and new runs should
   appear in Pipeline as the replay ticks.
2. **Try as Elena**: open PS-88214 in Exceptions, short-pay it, and watch the run resume and post in Pipeline.
3. Invoices → any invoice → **Verify chain** should report OK.
4. Ask the copilot "What does clause 4.2 of the Protein Supplier agreement say about shrimp?". The answer
   should carry a §4.2 citation.
5. Connect an MCP client with the demo token and call `list_exceptions` ([MCP.md](MCP.md)).

## 2. Environment variables

Names only. Local values go in `.env` (core, read from the repo root) and `apps/web/.env.local` (web).
`.env.example` lists the local defaults.

### Core (Railway)

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string. Use Supabase's **session** pooler or a direct connection: the worker needs `LISTEN` and the scheduler needs session advisory locks, which the transaction pooler does not support. |
| `SUPABASE_URL` | yes | Project URL (Auth admin API, Storage, JWT fallback check) |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Storage reads and writes, seeding Auth users |
| `SUPABASE_JWT_SECRET` | yes* | Local HS256 verification of user JWTs. If absent, core falls back to `GET /auth/v1/user`. |
| `CORE_HMAC_SECRET` | yes | Shared with the web app. Signs admin and service calls. |
| `CORS_ORIGINS` | yes | Comma-separated allowed origins (the Vercel URL) |
| `LLM_MODE` | yes | `fixture` (no OpenAI calls) or `live` |
| `OPENAI_API_KEY` | live only | Owner's key, capped by `LLM_DAILY_CAP_USD` |
| `LLM_MODEL` | no | default `gpt-4.1-mini` |
| `EMBED_MODEL`, `EMBED_DIMS` | no | default `text-embedding-3-small`, `512` |
| `LLM_DAILY_CAP_USD` | no | default `0.50` |
| `WORKER_ENABLED` | no | default `true` |
| `REPLAY_ENABLED` | prod: `true` | Demo drip every 5 min |
| `ORCHESTRATOR_VERSION` | no | default `v1`. Stamped on runs. |
| `MCP_DEMO_TOKEN` | no | Read-only public MCP token (`lgc_…`, 16–256 chars), upserted for the demo viewer on startup |
| `CORE_PUBLIC_URL` | no | Issuer URL advertised by the MCP auth settings |
| `DEMO_VIEWER_PASSWORD`, `DEMO_ELENA_PASSWORD` | for seed / reset | Passwords set on the demo Auth users by `app.demo.seed` (and by `/v1/admin/reset-demo`) |
| `LEDGIC_KB_DIR`, `LEDGIC_FIXTURES_DIR` | set by the Dockerfile | Paths to the knowledge base and hero fixtures inside the image |

### Web (Vercel)

| Variable | Required | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | Supabase project URL (browser + server) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | Public anon key. RLS protects the data. |
| `SUPABASE_URL` | yes | Server-side Supabase URL |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Server-only: rate-limit counters and admin helpers (`lib/auth/admin.ts`) |
| `CORE_URL` | yes | Core base URL for server-side calls |
| `NEXT_PUBLIC_CORE_URL` | no | Added to the CSP `connect-src` |
| `CORE_HMAC_SECRET` | yes | Same value as core |
| `DEMO_VIEWER_EMAIL`, `DEMO_VIEWER_PASSWORD` | yes | "Open the demo" server-side password grant |
| `DEMO_ELENA_EMAIL`, `DEMO_ELENA_PASSWORD` | yes | "Try as Elena" server-side password grant |
| `NEXT_PUBLIC_DEMO_ORG_SLUG` | no | Org the demo buttons land in |
| `NEXT_PUBLIC_SITE_URL` | recommended | Canonical origin for auth redirects (falls back to the request host) |
| `NEXT_PUBLIC_REPO_URL`, `NEXT_PUBLIC_LEDGIC_VERSION` | no | Repo link and version shown in the UI |
| `LEDGIC_SHOW_SYSTEM` | no | Enables the `/_system` component gallery outside development |

### CI (GitHub Actions)

No secrets are needed. CI runs in fixture mode against a throwaway local Supabase.

## 3. Rotate secrets

Rotate on suspicion of exposure, and whenever someone with access leaves.

| Secret | Steps |
|---|---|
| `CORE_HMAC_SECRET` | Generate a new random value (`openssl rand -hex 32`). Set it in **both** Railway and Vercel, then redeploy both. Signatures made with the old value fail with `INVALID_SIGNATURE` until both sides match. |
| `OPENAI_API_KEY` | Create a new key in the OpenAI dashboard, set it on Railway, redeploy, then revoke the old key. Keep the monthly usage limit in the OpenAI dashboard. |
| `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET` / anon key | Rotate in Supabase → Project Settings → API (rotating the JWT secret re-issues the anon and service keys and signs everyone out). Update Railway (`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`) and Vercel (`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`), then redeploy both. |
| Database password | Reset in Supabase → Database settings, update `DATABASE_URL` on Railway, redeploy. |
| Demo passwords | Change `DEMO_VIEWER_PASSWORD` / `DEMO_ELENA_PASSWORD` on Vercel **and** wherever the seed runs, then re-run `uv run python -m app.demo.seed` to update the Auth users. Redeploy Vercel. |
| `MCP_DEMO_TOKEN` | Set a new value on Railway and redeploy (it is upserted at startup). List and revoke the old one: `uv run python -m app.mcp.tokens list` then `… tokens revoke --id <id>`. Update the token in the README. |
| Personal MCP tokens | `uv run python -m app.mcp.tokens revoke --id <id>`. Takes effect on the next request. |

If a secret was ever committed, rotating it is mandatory. Rewriting git history is not enough.

## 4. Reset the demo

The scheduler's nightly job (03:00 America/New_York) already resets earlier heroes, auto-resolves stale
exceptions and purges data older than 30 days. To fully reset the demo org on demand, call the HMAC-signed
admin endpoint:

```bash
CORE=https://core-production-f996.up.railway.app
BODY='{"backfill_days":30}'
T=$(date +%s)
SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "$CORE_HMAC_SECRET" | sed 's/^.* //')
curl -s -X POST "$CORE/v1/admin/reset-demo" \
  -H "Content-Type: application/json" -H "X-Ledgic-Signature: t=$T,v1=$SIG" -d "$BODY"
```

`CORE_HMAC_SECRET` comes from your shell environment. Never paste it into a file.

This runs `demo_purge_org` (deletes the demo org, which cascades to every org table including its audit
chain, knowledge base and MCP tokens), re-runs the master-data seed, then backfills history and today in the
background. A second call while one is running returns `409 CONFLICT`. Afterwards:

```bash
cd services/core
uv run python -m app.ai.seed_kb          # re-index the knowledge base, re-cache copilot answers
uv run python -m app.mcp.tokens demo     # re-mint the demo MCP token (or restart the core service)
```

Related endpoints (same signing): `POST /v1/admin/seed-today` (release today's documents up to now,
idempotent) and `POST /v1/admin/replay/tick` (force a replay tick).

## 5. Common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health` `status: degraded`, `db: false` | `DATABASE_URL` wrong, or an IPv6-only direct host from Railway | Use the Supabase **session pooler** connection string (IPv4) |
| `/health` `worker.alive: false` | Worker loops crashed, or `WORKER_ENABLED=false` | Check Railway logs for `ledgic.worker`. Restart the service. Runs are durable and resume after restart. |
| Decisions don't resume runs | `LISTEN` not possible (transaction pooler) | Switch to the session pooler. The 2 s poll still advances runs, only more slowly. |
| Scheduler `leader: false` on the only replica | Advisory lock held by a stale session | It frees itself when the old connection dies. Restart core if it persists. |
| Operations KPIs never change | `pg_cron` missing and the scheduler is not leader | Enable `pg_cron`, or check the scheduler. Run `select public.refresh_kpis();` manually. |
| Pipeline screen is empty today | Replay disabled or no demo org | Set `REPLAY_ENABLED=true`. Call `/v1/admin/seed-today`. |
| "Open the demo" or "Try as Elena" fails | Web demo env vars don't match the passwords the seed set | Align `DEMO_*` on Vercel with the seed env and re-run `app.demo.seed` |
| Magic link lands on the wrong host | Supabase Site URL or redirect list | Fix in Auth → URL configuration |
| Admin calls return `401 INVALID_SIGNATURE` | Secret mismatch, or a clock more than 300 s off | Align `CORE_HMAC_SECRET`. Sync the clock. Sign the exact raw body. |
| Copilot always answers `retrieval_only` | `LLM_MODE=fixture`, no `OPENAI_API_KEY`, or the daily cap is spent | Expected when the budget is gone. It resets at 00:00 UTC. Check `v_ai_budget_today`. |
| Copilot answers have no citations | Knowledge base not indexed (for example after a reset) | `uv run python -m app.ai.seed_kb` |
| Uploads stay in extraction review with empty fields | No live extraction possible (fixture mode or budget spent) | Expected degradation. Enter the fields, or use BYOK. |
| MCP client gets `401` | Token revoked, wrong header, or the demo org was reset | Re-mint with `tokens demo` / restart core. Send `Authorization: Bearer lgc_…`. |
| MCP client gets a redirect or 404 on `/mcp` | Proxy path rewrite | Call `/mcp` exactly, with no trailing slash |
| Browser console CSP errors to core or Supabase | `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_CORE_URL` unset at build time | Set them and redeploy (the CSP is built at build time) |
| Supabase project paused | Free-tier inactivity | Restore in the dashboard. The scheduler's ticks normally keep it active. |
| Realtime doesn't refresh screens | Publication missing tables | Re-apply `20261014000005_realtime.sql` (`db push`) |
| Windows local dev: psycopg event-loop error | Proactor loop | `app/main.py` already sets the selector policy. Run through `uvicorn app.main:app`. |
