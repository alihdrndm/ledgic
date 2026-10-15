# Security policy

Ledgic is an open-source portfolio project with a public, synthetic-data demo. Security reports are
welcome and taken seriously.

## Supported versions

Only the `main` branch (and the hosted demo, which is deployed from it) receives security fixes. There are
no released versions or long-lived branches.

| Version | Supported |
|---|---|
| `main` | Yes |
| Anything else (forks, old commits) | No |

## Reporting a vulnerability

**Do not open a public issue, pull request or discussion for a vulnerability.**

1. **Preferred: GitHub private vulnerability reporting.** Go to the repository's **Security** tab and click
   **Report a vulnerability**, or open
   [a new advisory](https://github.com/alihdrndm/ledgic/security/advisories/new) directly.
2. **Fallback: email** [alihdrndm@gmail.com](mailto:alihdrndm@gmail.com) with the subject
   `SECURITY: <short summary>`.

Please include:

- the affected component (see [Scope](#scope)) and the commit or URL;
- a description of the issue and its impact;
- step-by-step reproduction, ideally against a local stack ([Run locally](README.md#run-locally));
- any proof-of-concept code, with secrets and personal data removed.

### What to expect

| Step | Target |
|---|---|
| Acknowledge your report | within 72 hours |
| Initial triage and severity assessment | within 7 days |
| Fix or mitigation for confirmed issues | as quickly as practical, prioritised by severity |

This is maintained by one person on a best-effort basis, so these are targets rather than guarantees. You
will be kept informed of progress, and credited in the advisory if you wish once a fix is released. There is
no bug bounty.

## Scope

In scope:

- **Web app**: `apps/web` (Next.js), including server actions and API routes.
- **Core service**: `services/core` (FastAPI), including the REST API, HMAC-signed admin endpoints, the
  orchestrator and the AI gateway.
- **Database**: Supabase row-level security policies, `security definer` RPCs, views and triggers in
  `supabase/migrations`.
- **MCP server**: `services/core/app/mcp` (streamable HTTP at `/mcp` and the `ledgic-mcp` stdio entry point),
  including token handling and scopes.
- **Hosted demo**: https://ledgic-pearl.vercel.app and https://core-production-f996.up.railway.app, within the
  rules below.

Out of scope:

- Denial-of-service, load or volumetric attacks against the free-tier demo.
- Rate limits on the demo (their values, or the absence of a limit on a non-sensitive endpoint).
- Social engineering, phishing or physical attacks against the maintainer or hosting providers.
- Findings that require a leaked or stolen maintainer credential, or access to the maintainer's accounts or
  devices.
- The Supabase anon key in the web app. It is public by design; access is enforced by row-level security.
  An RLS bypass *using* the anon key is in scope.
- The demo login buttons, and the read-only access they grant, which are intentional.
- Vulnerabilities in third-party services (Supabase, Vercel, Railway, OpenAI, GitHub) themselves. Report
  those to the vendor.
- Missing security headers or best-practice suggestions without a demonstrated impact.

## Rules for testing the hosted demo

- Use only the demo accounts offered on the login page, or your own local stack.
- Do not access, modify or delete data that is not yours, and stop as soon as you have shown that such access
  is possible.
- Do not run automated vulnerability scanners, fuzzers or crawlers against the hosted demo. Run them against a
  local stack instead.
- Do not attempt to exhaust the daily AI budget or degrade the demo for other visitors.
- Keep any data you obtain confidential and delete it once the report is resolved.

## Safe harbor

If you make a good-faith effort to follow this policy, the maintainer will consider your research
authorized, will not pursue or support legal action against you, and will work with you to understand and
resolve the issue. If in doubt about whether something is allowed, ask first at the address above.

## Security design

A short summary; details are in the linked documents.

- **Row-level security on every table**, with `security_invoker` views, so the browser, core and the MCP
  server all see only what the signed-in user may see.
  ([docs/ARCHITECTURE.md, Auth model](docs/ARCHITECTURE.md#4-auth-model))
- **`security definer` RPCs** with a fixed `search_path` carry role limits and segregation of duties, so
  permissions are enforced in the database rather than the UI. Core and the MCP server act as the calling
  user.
- **Hash-chained, append-only audit log**: every decision and system action is written to a per-org SHA-256
  chain, guarded by triggers and verifiable from the UI and the MCP server.
- **HMAC-signed admin endpoints**: server-to-core admin calls carry a timestamped HMAC-SHA256 signature
  (5-minute window, constant-time compare).
- **MCP tokens are stored as sha256 hashes** only, with `read` / `decide` scopes and per-token rate limits.
  ([docs/MCP.md, Security model](docs/MCP.md#security-model))
- **AI spend cap**: every model call reserves its estimated cost atomically in Postgres against a hard daily
  cap that fails closed. ([docs/ARCHITECTURE.md, Cost guardrails](docs/ARCHITECTURE.md#7-cost-guardrails))
- **Secrets stay out of git**: `.env*` files are ignored, CI runs gitleaks on every pull request and every push to `main`, and GitHub secret
  scanning with push protection is enabled. Rotation steps are in
  [docs/RUNBOOK.md](docs/RUNBOOK.md#3-rotate-secrets).

pgTAP tests in `supabase/tests` cover RLS isolation, audit-log immutability and the decision RPCs.
