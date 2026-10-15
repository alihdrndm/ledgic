## Summary

<!-- What does this change and why? Link the issue, for example "Closes #123". -->

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Refactor or chore (no behaviour change)
- [ ] Docs
- [ ] Database migration
- [ ] Change to `contracts/*` (core API, RPCs, views, extraction schema, fixtures)

## How was this tested?

<!-- Commands run and anything checked by hand. -->

## Checklist

- [ ] Tests pass locally (`uv run ruff check . && uv run pytest`, `npx supabase test db`, `pnpm typecheck && pnpm lint`, as relevant)
- [ ] New behaviour is covered by tests
- [ ] Docs updated (`README.md`, `docs/`, `contracts/`, and `docs/DECISIONS.md` for departures from the spec)
- [ ] No secrets, credentials, `.env` values or personal data added (code, fixtures, screenshots, logs), and `pre-commit run --all-files` is clean
- [ ] Migrations are new files, reversible or safe on existing data, and keep RLS enabled with pgTAP coverage
- [ ] Commit messages follow Conventional Commits
- [ ] UI changes: screenshots attached below, design tokens only (`check:tokens` passes)

## Screenshots

<!-- Before and after, for UI changes. Delete this section if not applicable. -->
