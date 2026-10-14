# 09 — Infrastructure & DevOps

## 1. Monorepo
pnpm workspaces + Turborepo. Node 22 LTS, pnpm 9, Python 3.12 with `uv`.
```
ledgic/
  apps/web/                    Next.js 15 app (Vercel root directory)
  services/core/               FastAPI service (Dockerfile)
  services/n8n/                Dockerfile (FROM pinned n8n), workflows/*.json, VERSION, import.ts
  packages/ui/                 modernist.css (vendored), ledgic.css, React primitives
  packages/db/                 supabase/ (config.toml, migrations/, seed.sql), src/types.ts
  packages/config/             eslint, tsconfig, prettier presets
  tools/corpus/                synthetic invoice generator (Python)
  tools/seed/                  seed_demo.py, seed_qbo.py
  infra/terraform/             AWS (modules: network, ecr, ecs, alb, ses, s3, secrets, iam, budgets, observability)
  infra/slack/manifest.yml
  docs/                        ops/BUILD_LOG.md, ops/INVENTORY.md, runbooks/*.md, api/
  .github/workflows/
  docker-compose.yml           local n8n + core (+ supabase via CLI)
  turbo.json, pnpm-workspace.yaml, .nvmrc, .python-version, .env.example (names only, no values)
```
Tooling: ESLint (flat config) + Prettier; TypeScript `strict`, `noUncheckedIndexedAccess`; Ruff + mypy (strict on `app/`); commitlint; Husky pre-commit (lint-staged, `gitleaks protect --staged`).

## 2. Local development
```
supabase start                         # Postgres, Auth, Storage, Realtime on Docker
pnpm db:reset                          # migrations + seed (demo org skeleton)
docker compose up n8n core             # core on :8000, n8n on :5678 (workflows auto-imported by services/n8n/import.ts)
pnpm dev                               # web on :3000
pnpm corpus:generate --n 300           # synthetic documents into tools/corpus/out
pnpm demo:replay --once                # drop a batch through local intake
```
Textract/SES are mocked locally (`CORE_OCR_MODE=mock`, emails injected via `tools/seed/send_local_email.py`). Anthropic is real (dev key with a low limit) or `CORE_LLM_MODE=fixture` to replay recorded responses.

## 3. Vercel (web)
- Project `ledgic-web`, root `apps/web`, framework Next.js, Node 22. Git integration with the GitHub repo: Production = `main`, Preview = all PRs.
- Env vars (Production / Preview / Development scopes separately): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (server only — used only by the OAuth callback and `openDemo`), `N8N_BASE_URL`, `N8N_WEBHOOK_SECRET`, `CORE_URL`, `CORE_HMAC_SECRET`, `DEMO_VIEWER_EMAIL`, `DEMO_VIEWER_PASSWORD`, `QBO_CLIENT_ID`, `QBO_CLIENT_SECRET`, `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `DEMO_PORTAL_USER`, `DEMO_PORTAL_PASSWORD`.
- Domains: `app.<domain>` (prod). Previews on `*.vercel.app`.
- Headers (next.config): strict CSP (self + Supabase + Sentry), `X-Frame-Options: DENY`, HSTS, `Referrer-Policy: strict-origin-when-cross-origin`.

## 4. Supabase
- Projects: `ledgic-prod` (and `ledgic-staging` if staging is kept). Region `us-east-1` to sit next to AWS.
- Auth: email magic link; Site URL `https://app.<domain>`; redirect URLs for prod, previews (`https://*-<team>.vercel.app/**`), localhost. SMTP: use SES (verified domain) for auth emails in prod.
- Storage bucket `documents` (private), size limit 25 MB, allowed MIME `application/pdf,image/*,text/plain`.
- DB: enable extensions (`05` §1); Postgres role `n8n_user` with schema `n8n` only; `core_user` is the service role via pooler (transaction mode, port 6543) for core, session mode for migrations.
- `pg_cron` jobs: refresh materialized views every minute; nightly `vacuum analyze` on hot tables is managed by Supabase.
- Backups: daily (plan default); enable PITR if on Pro (ask).

## 5. AWS (Terraform, `infra/terraform`)
State: S3 bucket `ledgic-tfstate-<account>` + DynamoDB lock table (bootstrap module, created once). Workspaces or directories per env (`envs/prod`, `envs/staging`).

Resources per env:
- **Network**: VPC 2 AZs, public subnets for ALB, private subnets for tasks, **no NAT gateway** (cost) → tasks in public subnets with public IPs and security groups allowing only ALB ingress (document the trade-off; NAT optional variable).
- **ECR**: `ledgic/core`, `ledgic/n8n` (scan on push, lifecycle keep 20).
- **ECS Fargate** cluster `ledgic-<env>`: service `core` (0.5 vCPU / 1 GB, desired 1, autoscale to 3 on CPU 60%), service `n8n` (0.5 vCPU / 1 GB, desired 1). Task roles with least privilege: core → S3 read on raw-mail/edi buckets, Textract AnalyzeExpense, Secrets Manager read on its secrets; n8n → Secrets read on its secrets only.
- **ALB** with ACM cert for `core.<domain>` and `n8n.<domain>`; HTTP→HTTPS redirect; n8n UI additionally restricted by n8n auth; `/webhook/*` open, `/rest/*` and UI behind n8n login. Health checks `/health` (core), `/healthz` (n8n).
- **Route 53** or external DNS: if the user's DNS isn't in Route 53, output the records for Claude Code to add in the user's DNS provider via browser (runbook §5).
- **SES**: domain identity + DKIM, receipt rule set (`08` §1), configuration set; production access request if outbound auth email is needed (STOP: requires a form submission in the user's name — ask).
- **S3**: `ledgic-<env>-raw-mail` (SES write policy, lifecycle expire 90 days), `ledgic-<env>-edi-inbound`, both encrypted SSE-S3, public access blocked; event notifications → SNS topics.
- **SNS**: `inbound-mail`, `edi-inbound` with HTTPS subscriptions to n8n webhooks (subscription confirmed by WF-01/04).
- **Secrets Manager**: `ledgic/<env>/{anthropic, core-hmac, n8n-webhook, n8n-encryption-key, supabase-db-url, supabase-service-role, qbo, sentry}`. Values are set via console or CLI by Claude Code per runbook — Terraform creates the secret shells only.
- **CloudWatch**: log groups (30-day retention), alarms: ECS task restarts, ALB 5xx > 1% over 5 min, core p95 latency, DLQ count (custom metric pushed by core), SNS delivery failures → SNS topic `alerts` → email to the user.
- **Budgets**: monthly $50 with alerts at 50/80/100% to the user's email.
- **GitHub OIDC**: IAM OIDC provider for `token.actions.githubusercontent.com`, role `ledgic-gha-deploy` assumable only by `repo:<owner>/ledgic:ref:refs/heads/main` and environment `production` (and `staging`); permissions: ECR push, ECS update-service, describe; Terraform role separate (`ledgic-gha-terraform`) with broader rights, only from the `terraform.yml` workflow on `main` with environment approval.

## 6. GitHub
- Repo `ledgic` (private until launch; the user decides if public — a public repo helps the portfolio claim; STOP and ask).
- Branch protection on `main`: PR required, status checks (`ci`), linear history, no force-push.
- Environments: `staging` (auto), `production` (required reviewer = the user for Terraform and DB migrations only; app deploys automatic after CI).
- Secrets (repo/environment): `AWS_ACCOUNT_ID`, `AWS_REGION`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD_PROD`, `SUPABASE_PROJECT_REF_PROD` (+ staging), `N8N_API_KEY_PROD`, `N8N_BASE_URL_PROD`, `ANTHROPIC_API_KEY_EVAL` (low-limit key for CI eval), `SENTRY_AUTH_TOKEN`. No AWS keys — OIDC only.
- Dependabot (npm, pip, docker, github-actions weekly); CodeQL (JS/TS + Python); secret scanning + push protection on.

## 7. GitHub Actions workflows

### `ci.yml` (PRs and main)
```yaml
name: ci
on: { pull_request: {}, push: { branches: [main] } }
concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }
jobs:
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version-file: .nvmrc, cache: pnpm }
      - run: pnpm install --frozen-lockfile
      - run: pnpm turbo lint typecheck test --filter=./apps/* --filter=./packages/*
  core:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: services/core } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run mypy app
      - run: uv run pytest -m "not integration" --cov=app --cov-fail-under=85
  db:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
      - run: supabase start -x studio,imgproxy,edge-runtime
      - run: supabase db reset && supabase test db          # pgTAP tests: RLS, audit immutability, views
      - run: pnpm --filter db gen:types && git diff --exit-code packages/db/src/types.ts
  integration:
    needs: [core, db]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.ci.yml up -d --wait   # supabase + core(fixture LLM, mock OCR) + n8n
      - run: pnpm --filter e2e test:pipeline                          # drives documents end to end through n8n
  e2e:
    needs: [web, integration]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pnpm install --frozen-lockfile && pnpm exec playwright install --with-deps chromium
      - run: pnpm --filter e2e test:ui       # includes visual regression vs design PNGs (fixture mode)
      - uses: actions/upload-artifact@v4
        if: failure()
        with: { name: playwright-report, path: e2e/playwright-report }
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gitleaks/gitleaks-action@v2
      - run: pnpm audit --prod --audit-level=high || true
      - uses: aquasecurity/trivy-action@0.24.0
        with: { scan-type: fs, severity: HIGH,CRITICAL, exit-code: '1', ignore-unfixed: true }
```

### `deploy-core.yml` and `deploy-n8n.yml` (on push to main, paths-filtered)
Steps: checkout → `aws-actions/configure-aws-credentials@v4` with `role-to-assume: arn:aws:iam::${{secrets.AWS_ACCOUNT_ID}}:role/ledgic-gha-deploy` → ECR login → build (`docker buildx`, tag `sha`) → push → render task definition with new image → `aws-actions/amazon-ecs-deploy-task-definition@v2` with `wait-for-service-stability: true` → smoke `curl -f https://core.<domain>/health`. For n8n additionally: after stability, run `services/n8n/import.ts` which, via the n8n public API, upserts each workflow by name, re-links credentials by name, activates them, and sets `WORKFLOW_VERSION` (read from `services/n8n/VERSION`) — CI fails if `workflows/*.json` changed but `VERSION` did not.

### `db-migrate.yml` (push to main touching `packages/db/supabase/migrations/**`)
Environment `production` (manual approval) → `supabase link --project-ref $REF` → `supabase db push` → re-run pgTAP smoke against prod read-only checks (RLS enabled on all tables).

### `terraform.yml`
PR: `fmt -check`, `validate`, `tflint`, `plan` (posted as PR comment). Main: `apply` in environment `production` with approval.

### `eval.yml`
Nightly 03:00 UTC + manual: run extraction eval on a 60-document fixed subset with `ANTHROPIC_API_KEY_EVAL`; fail if accuracy drops > 1.0 pt vs baseline in `services/core/eval/baseline.json`; upload report. On prompt changes (`extraction/prompts/**`), required on PR.

### `release.yml`
On tag `v*`: changelog from conventional commits, GitHub release.

## 8. Observability & ops
- Sentry projects `ledgic-web`, `ledgic-core`; release = git sha; source maps uploaded by Vercel build.
- Structured JSON logs (structlog) with `run_id`, `invoice_id`, `org_id` on every line; n8n execution id propagated as `X-N8N-Execution` header.
- Uptime monitor (Better Stack free, or CloudWatch Synthetics canary) on `app.<domain>/api/health`, `core.<domain>/health`, `n8n.<domain>/healthz` every 1 min. **Only if this runs** may an uptime figure appear anywhere (it doesn't appear in the designed screens; don't add it).
- Runbooks in `docs/runbooks/`: `pipeline-stuck.md`, `erp-reconnect.md`, `dlq-replay.md`, `rotate-secrets.md`, `restore-db.md`, `cost-spike.md`.
