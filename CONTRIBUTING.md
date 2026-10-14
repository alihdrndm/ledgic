# Contributing to Ledgic

Thanks for your interest. Ledgic is a portfolio project, but issues and pull requests are welcome,
especially bug reports against the live demo, test cases for edge-case invoices, and documentation fixes.

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
5. **No secrets in git.** `.env*` is ignored except `.env.example`. CI runs gitleaks on every push.
6. **Departures from the spec** in `docs/handoff/` get a row in `docs/DECISIONS.md`.

## Setup

Follow [Run locally](README.md#run-locally): Node 22+, pnpm 9, Python 3.12 + uv, Docker.

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
```

If you change the schema, regenerate the types: `pnpm db:types`.

## Style

- **Python:** ruff (line length 110), type hints everywhere, `Decimal` for money (never `float`), money
  crosses the API as decimal strings.
- **TypeScript:** strict mode, `decimal.js` for money, design tokens only (no raw colors or sizes;
  `check:tokens` enforces this).
- **SQL:** `security definer` functions use `set search_path = ''` and fully qualified names. Errors use
  the `LEDGIC_*:` prefixes from `contracts/rpc.md`.
- **Commits:** Conventional Commits scoped by area, for example `feat(core): …`, `fix(db): …`,
  `docs: …`, `test(web): …`.

## Reporting security issues

Please don't open a public issue for a vulnerability. Open a private security advisory on GitHub
(Security → Report a vulnerability).

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
