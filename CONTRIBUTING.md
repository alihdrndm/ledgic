# Contributing to Ledgic

Thanks for your interest. Ledgic is a portfolio project, but issues and pull requests are welcome,
especially bug reports against the live demo, test cases for edge-case invoices, and documentation fixes.

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). For questions, see
[SUPPORT.md](SUPPORT.md). For vulnerabilities, see [SECURITY.md](SECURITY.md), never a public issue.

## Ground rules

1. **No hard-coded metrics.** Every number in the UI must come from a SQL view over real rows. If you
   add a KPI, add the view (and a pgTAP test for it) first.
2. **The LLM reads, it never decides.** Money math, verdicts and recommendations live in
   `services/core/app/domain/` as pure `Decimal` functions. LLM output that contains money must pass a
   guard against deterministic figures.
3. **Permissions live in the database.** Role limits and segregation of duties belong in the RPCs
   (`supabase/migrations`), never only in the UI or in core. Core and MCP act *as the user*.
4. **Contracts are frozen.** Changes to `contracts/*` (core API, RPCs, views, extraction schema, hero
   fixtures) need a matching change on every side and a note in the PR.
5. **No secrets in git.** See [Secrets and security](#secrets-and-security).
6. **Departures from the spec** in `docs/handoff/` get a row in `docs/DECISIONS.md`.

## Setup

Follow [Run locally](README.md#run-locally): Node 22+, pnpm 9, Python 3.12 + uv, Docker.

Then install the git hooks (requires [pre-commit](https://pre-commit.com), for example
`uv tool install pre-commit` or `pipx install pre-commit`):

```bash
pre-commit install
```

The hooks in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) are security-only: gitleaks, private-key
detection, a 1.5 MB file-size limit and merge-conflict markers.

## Workflow

1. Open or comment on an issue first for anything larger than a small fix, so effort isn't wasted.
2. Fork the repo (or branch, if you have access) from `main`. Name branches by type and topic, for example
   `feat/vendor-aliases`, `fix/match-tolerance`, `docs/runbook`.
3. Commit using [Conventional Commits](https://www.conventionalcommits.org) scoped by area:
   `feat(core): …`, `fix(db): …`, `docs: …`, `test(web): …`, `chore(ci): …`. Keep commits focused.
4. Open a pull request against `main` and fill in the template. Keep PRs small and reviewable.

`.github/CODEOWNERS` requests a review from the maintainer automatically, with extra care for migrations,
CI configuration and the core API.

## Before opening a PR

```bash
# core
cd services/core
uv run ruff check .
uv run pytest                      # unit tests (integration tests are deselected by default)
uv run pytest -m integration       # needs `npx supabase start` and a seeded demo org

# database
npx supabase db reset && npx supabase test db

# web (repo root)
pnpm typecheck && pnpm lint && pnpm --filter @ledgic/web check:tokens
pnpm test:e2e                      # Playwright smoke + axe (specs in apps/web/e2e), needs the app running

# secrets (repo root)
pre-commit run --all-files         # or: gitleaks detect --source . -v --redact
```

If you change the schema, regenerate the types: `pnpm db:types`.

### PR checklist

- [ ] The relevant suites above pass locally, and new behaviour has tests (pytest, pgTAP or Playwright).
- [ ] Docs are updated (`README.md`, `docs/`, `contracts/`) where behaviour or interfaces change.
- [ ] No secrets, credentials, real `.env` values or personal data are added, including in fixtures,
      screenshots and logs.
- [ ] Migrations are new files (never edit an applied migration), safe on existing data, and keep RLS on every
      new table with pgTAP coverage.
- [ ] UI changes include before/after screenshots and use design tokens only.

## Style

- **Python:** ruff (line length 110), type hints everywhere, `Decimal` for money (never `float`), money
  crosses the API as decimal strings.
- **TypeScript:** strict mode, `decimal.js` for money, design tokens only (no raw colors or sizes;
  `check:tokens` enforces this).
- **SQL:** `security definer` functions use `set search_path = ''` and fully qualified names. Errors use
  the `LEDGIC_*:` prefixes from `contracts/rpc.md`.

## Secrets and security

- **Never commit `.env` files** or any real key, token, password, JWT secret or connection string. `.env*`
  is git-ignored except `.env.example`.
- **Use placeholders.** New configuration goes in `.env.example` with an empty or obviously fake value and a
  comment, and in the environment-variable tables in [docs/RUNBOOK.md](docs/RUNBOOK.md#2-environment-variables).
  Test fixtures use clearly fake values (for example `lgc_pat_this-token-does-not-exist-anywhere`).
- **Scan before pushing.** Run `pre-commit run --all-files` or `gitleaks detect --source . -v --redact`.
  CI runs gitleaks on every pull request, and GitHub secret scanning with push protection is enabled, so a
  push containing a recognised secret is blocked.
- **If you leak a secret,** treat it as compromised: rotate it first (see
  [docs/RUNBOOK.md](docs/RUNBOOK.md#3-rotate-secrets)), then remove it from history. Removing the commit
  alone is not enough. If it is a maintainer-owned secret, report it privately as below.
- **Report vulnerabilities privately** via GitHub's **Security → Report a vulnerability**, as described in
  [SECURITY.md](SECURITY.md). Never in a public issue, PR or discussion.
- **Forks don't get secrets in CI.** Workflows triggered by pull requests from forks run without repository
  secrets, and the CI jobs are designed to pass without them. Don't add steps that need secrets to
  `pull_request` jobs, and never switch a workflow to `pull_request_target` to work around this.
- **Don't paste secrets into issues or PRs.** Redact keys, tokens, cookies and personal data from logs and
  screenshots.

## License

Ledgic is licensed under the [MIT License](LICENSE). Contributions are accepted under the same license
(inbound = outbound): by opening a pull request you agree that your contribution is licensed under MIT. No CLA
or DCO sign-off is required.
