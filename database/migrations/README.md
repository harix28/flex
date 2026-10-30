# Executable migrations

Current head: `0009_fleet_jobs`. Adds fleet job support and persisted results to the
durable queue introduced in `0008_outbox`. Downgrade refuses while fleet jobs exist.
See [background job operations and rollback](../../docs/BACKGROUND_JOBS.md).
The revision notes below describe historical rollout stages.

See [database operations](../README.md) for setup, upgrade, destructive downgrade
warnings and test isolation. Initial revision: `0001_registry`; immutable SQL lives
beside its Python revision. Migrations run transactionally and are operator-invoked.
Do not edit applied revisions; add a new revision. No automatic database reset.


Current head: `0002_auth`. Adds local identity fields, sessions, audits and revocation
trigger. Renames manager to plant_manager and stops for explicit resolution of legacy
ml_engineer memberships. Never rewrite 0001. Downgrade of 0002 loses local credentials,
sessions, slugs and audits; registry rows remain. See docs/AUTHENTICATION.md for details.


Current head: `0003_registry` (after immutable 0001/0002). Existing registry rows are
preserved. Legacy overlapping machine/channel slots cause transactional upgrade failure
for manual review. Downgrade refuses if registry audit events exist and otherwise loses
new metadata/constraints; use disposable tests or a reviewed restore plan only.
