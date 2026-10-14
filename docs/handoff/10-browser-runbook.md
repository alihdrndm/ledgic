# 10 — Browser runbook (what Claude Code does in the user's browser)

You have control of the user's browser and cursor. Use it for console work that has no reliable CLI path or that needs the user's identity. Prefer CLIs (`gh`, `vercel`, `supabase`, `aws`, `terraform`) once authenticated.

**Legend:** 🛑 STOP and ask the user · 🔐 hand control to the user (login/2FA/CAPTCHA) · 📝 record in `docs/ops/INVENTORY.md` (non-secret) · 🔑 secret → destination directly, never chat/logs/files.

## 0. Before anything
1. Ask the user (single message) for: the GitHub account/org to use; the domain to use (e.g. `ledgic.example.com` or a subdomain of theirs) and where its DNS is managed; whether to keep a staging environment (cost); Supabase plan (Free vs Pro); whether the repo should become public at launch; the email for budget alerts. 🛑
2. Create `docs/ops/BUILD_LOG.md` and `INVENTORY.md` in the repo.

## 1. Local toolchain
Verify/install: git, Node 22 + pnpm, Python 3.12 + uv, Docker Desktop (running), Supabase CLI, Vercel CLI, AWS CLI v2, Terraform ≥ 1.8, GitHub CLI, Playwright browsers. Don't upgrade system-wide tools the user already has pinned without asking.

## 2. GitHub
1. `gh auth login` (🔐 the user completes device/browser auth).
2. `gh repo create <owner>/ledgic --private --clone`. 📝 repo URL.
3. In the browser: Settings → Code security → enable secret scanning + push protection, Dependabot alerts; Branches → protect `main` (after the first CI run exists); Environments → create `staging`, `production` (required reviewer: the user on `production`).

## 3. Supabase
1. Open supabase.com → sign in (🔐). If the org needs a plan upgrade for Pro: 🛑.
2. New project `ledgic-prod`, region `us-east-1` (East US / N. Virginia), generate a strong DB password → 🔑 GitHub env secret `SUPABASE_DB_PASSWORD_PROD` and AWS Secrets Manager `ledgic/prod/supabase-db-url` (compose URL from the Connect dialog: pooler transaction string). 📝 project ref, URL.
3. Project Settings → API: anon key → 🔑 Vercel `NEXT_PUBLIC_SUPABASE_ANON_KEY` (all scopes); service role key → 🔑 Vercel (server) + Secrets Manager `ledgic/prod/supabase-service-role`.
4. Account → Access Tokens → create `ledgic-ci` → 🔑 GitHub `SUPABASE_ACCESS_TOKEN`.
5. Auth → URL configuration: Site URL `https://app.<domain>`; redirects: `https://app.<domain>/**`, `https://*-<vercel-team>.vercel.app/**`, `http://localhost:3000/**`. Auth → Providers: Email (magic link on, confirm email on). SMTP: after SES is ready (§5), set custom SMTP (SES SMTP credentials → 🔑 entered directly in the Supabase form).
6. Database → Extensions: enable `pg_cron`, `vector`, `pg_trgm`, `pgcrypto`, `citext` (migrations also do this; enabling in UI first avoids permission issues with pg_cron).
7. Repeat for `ledgic-staging` if kept.

## 4. Vercel
1. vercel.com → sign in (🔐). Plan: Hobby unless the user says otherwise (Hobby is non-commercial — mention it; 🛑 if they want Pro).
2. `vercel link` in `apps/web` → create project `ledgic-web`, root `apps/web`. Connect Git repo in dashboard. 📝 project id.
3. Add env vars per `09` §3 via `vercel env add <NAME> <scope>` with values pasted interactively (🔑).
4. Domains → add `app.<domain>`; note the DNS record Vercel asks for (used in §5).

## 5. DNS
If DNS is at a provider Claude Code can operate in the browser (Cloudflare, Namecheap, GoDaddy, Route 53…): 🔐 login, then add:
- `app` CNAME → `cname.vercel-dns.com` (or the value Vercel shows)
- `core`, `n8n` CNAME → ALB DNS name (after Terraform apply)
- `ap` MX 10 → `inbound-smtp.us-east-1.amazonaws.com`
- SES DKIM: 3 CNAMEs from SES; SPF `v=spf1 include:amazonses.com ~all` on the MAIL FROM subdomain; DMARC `_dmarc` TXT `v=DMARC1; p=none; rua=mailto:<user email>` if none exists.
🛑 before editing any record that already exists on an apex/domain with live traffic. 📝 every record added.

## 6. Anthropic
console.anthropic.com → sign in (🔐) → Workspaces: create `ledgic` → Limits: monthly spend limit **$30** (🛑 if billing isn't set up — the user must add payment) → API Keys: create `ledgic-prod-core` → 🔑 Secrets Manager `ledgic/prod/anthropic`; create `ledgic-ci-eval` → 🔑 GitHub `ANTHROPIC_API_KEY_EVAL`; create `ledgic-dev` → the user's local `.env` (tell them where; don't write it yourself unless they ask).

## 7. AWS
1. Sign in to the console (🔐; root user only if no IAM user exists — then create an admin IAM Identity Center user for the user and continue with that, 🛑 confirm first).
2. Billing → Budgets: create monthly cost budget $50, alerts 50/80/100% to the user's email. **Do this before any other resource.**
3. CLI access for Terraform bootstrap: `aws configure sso` (🔐) — no long-lived access keys.
4. `terraform -chdir=infra/terraform/bootstrap apply` (state bucket, lock table, GitHub OIDC provider + roles). 📝 role ARNs → GitHub secret `AWS_ACCOUNT_ID` (non-secret but kept as secret for convenience).
5. `terraform -chdir=infra/terraform/envs/prod apply` (🛑 show the plan summary and monthly cost estimate first — ALB ≈ $16–20, 2 Fargate tasks ≈ $18–30, others small).
6. Secrets Manager: fill the shells created by Terraform (🔑): `anthropic`, `core-hmac` (generate 32-byte random: `openssl rand -hex 32` piped straight into `aws secretsmanager put-secret-value`), `n8n-webhook` (same), `n8n-encryption-key` (same — back it up: 🛑 tell the user to store a copy in their password manager; losing it bricks n8n credentials), `supabase-db-url`, `supabase-service-role`, `qbo` (after §8), `sentry`.
7. SES: verify domain identity (records → §5); create receipt rule set per `08` §1 and set it **active**; request production access only if Supabase auth emails will go through SES (🛑 form submitted in the user's name).
8. Confirm SNS HTTPS subscriptions show "Confirmed" after n8n is live.

## 8. Intuit (QuickBooks sandbox)
developer.intuit.com → sign in (🔐; create developer account if needed — 🛑 ToS acceptance) → Dashboard → Create app `Ledgic` (QuickBooks Online and Payments, Accounting scope) → Keys & credentials (Development): client id/secret → 🔑 Vercel `QBO_CLIENT_ID`/`QBO_CLIENT_SECRET` and Secrets Manager `ledgic/prod/qbo`. Redirect URIs per `08` §4. Sandbox → create sandbox company (US). Then in the running app: Settings → Integrations → Connect QuickBooks (🔐 the user authorizes). Run `tools/seed/seed_qbo.py`.

## 9. Slack
api.slack.com/apps → Create from manifest (`infra/slack/manifest.yml`) → 🛑 which workspace (suggest a new free workspace `ledgic-demo`) → install → then connect from Settings → Integrations → Slack (OAuth). Create channels `#ap-digest`, `#ap-alerts`, invite the bot.

## 10. n8n first run
After the ECS service is healthy: open `https://n8n.<domain>` → create owner account with the user's email and a generated password (🔑 into the user's password manager — ask them to save it; don't store it anywhere) → Settings → API → create API key → 🔑 GitHub `N8N_API_KEY_PROD`. Credentials in n8n are **not** used for secrets that core holds; n8n only needs: Slack bot token (credential `slack-bot`), and env-injected HMAC secrets. Run the `deploy-n8n` workflow to import and activate workflows.

## 11. Sentry & uptime
sentry.io → sign in (🔐) → org → projects `ledgic-web` (Next.js), `ledgic-core` (Python) → DSNs → 🔑 Vercel/Secrets Manager; auth token → 🔑 GitHub + Vercel. Better Stack (or CloudWatch Synthetics) monitors per `09` §8.

## 12. Demo accounts
Create users in Supabase Auth (via seed script using the service role, not the UI): `elena.marsh@demo.<domain>` (ap_manager), `tom.iwu@demo.<domain>` (controller), `demo-viewer@<domain>` (viewer; password 🔑 Vercel `DEMO_VIEWER_PASSWORD`). Demo persona emails use a subdomain with no MX so nothing is ever delivered.

## 13. When things go wrong in a console
- Don't retry destructive actions blindly. Screenshot the error, record it in BUILD_LOG, search the provider docs, and try the documented fix.
- If a quota/limit blocks progress (e.g., SES sandbox, Fargate vCPU limit), 🛑 explain and propose the request/alternative.
