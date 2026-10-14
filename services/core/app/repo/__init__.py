"""SQL repositories used by the orchestrator, API, scheduler and demo tooling.

All functions take an open `AsyncConnection` (service role unless the caller switched to a user with
`app.db.pool.as_user`) and never commit: the caller owns the transaction, so a stage's effects, its
`pipeline_events` row, `audit_log` rows and `cost_ledger` rows land atomically.
"""
