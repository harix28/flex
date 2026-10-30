# Fleet scoring worker validation — 2026-10-30

Implemented operator-enqueued bounded fleet scoring, frozen input/model snapshots,
execution-time membership checks, atomic prediction/audit persistence, stored job
results and tenant-scoped operator status lookup. Migration 0009_fleet_jobs extends
the outbox event constraint and adds its nullable result object. Runtime readiness
expects 0009. The runbook describes rollout, limits and guarded rollback.

Executed from the repository Windows virtual environment with local PostgreSQL
credentials loaded privately into SENTINEL_TEST_ADMIN_URL. Fixtures create/drop
generated disposable databases; no application database migration was performed.

```text
python -m pytest tests/test_fleet_jobs_postgres.py tests/test_jobs_postgres.py tests/test_predictions_postgres.py tests/test_container_deployment.py -q --tb=short
35 passed, 1 warning in 67.84s
```

The 11 fleet integration cases exercise real primary-model execution; frozen cutoff
behavior after later ingestion; prediction/audit idempotency; explicit unknown output;
inactive-machine exclusion; viewer and foreign-tenant requester rejection; revoked
membership and disabled-account rejection; model mismatch and backfill rejection;
batch rollback and successful retry; conflicting payload rejection; foreign-machine
protection; 101-machine rejection without partial enqueue; guarded downgrade; and
tenant-scoped CLI status. Existing queue tests cover leases, crashes, stale workers,
backoff/dead letters and migration round trips. Existing prediction and deployment
tests exercise compatibility, causal windows, concurrency and runtime permissions.

An earlier expanded run had 33 passes and one failure: the unsupported-subset test
implicitly auto-discovered a locally installed FD002 candidate while assuming a
single FD001 model. Its fixture now explicitly injects a verified single-model
Predictor for that test. Production prediction/inference code was not changed to
make the assertion pass. The final run above includes that corrected test.

CLI enqueue-fleet/status help and git whitespace checks also passed. The remaining
warning is the existing Starlette/httpx deprecation. No full-suite, browser, container
runtime, load, production rollout or automatic scheduling validation is claimed.

Limits: operator CLI only; maximum 100 active machines per run; configured primary
model only; tenant writes can contend with batch execution; all-or-nothing batch
transaction; no ingestion/notification handlers or recurring scheduler. No models
were trained/promoted, work orders approved, or worker processes left running.
