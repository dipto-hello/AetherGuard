# AetherGuard project instructions

Read [Architecture](docs/ARCHITECTURE.md) for the implemented trust and data flows, [Local setup](docs/SETUP.md) for verification, and [Developer handover](docs/HANDOVER.md) before broad changes.

Keep the demo synthetic. Validate caller, scope, and exact tool arguments at the trusted boundary. Check approval expiry, fingerprint, cumulative limits, replay, and idempotency when touching execution. Use disposable SQLite databases for tests. Preserve existing data and document migration behavior. Distinguish live model behavior from deterministic evaluation results. Keep private runtime state outside Git.
