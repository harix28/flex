# Background jobs validation — 2026-10-30

Implemented migration 0008_outbox, internal transactional producer, PostgreSQL
worker and operator CLI. The only handler is FD001 drift evaluation; other async
workloads and periodic scheduling remain planned.

Executed with the repository Windows virtual environment and local PostgreSQL
credentials loaded privately into SENTINEL_TEST_ADMIN_URL. Fixtures created and
dropped generated disposable databases; the application database was not migrated.

```text
python -m pytest tests/test_jobs_postgres.py tests/test_database.py tests/test_container_deployment.py tests/test_mlops_postgres.py -q --tb=short
27 passed, 1 warning in 35.07s
```

Eight new integration tests cover transactional enqueue rollback, tenant-separated
idempotency, payload rejection, SKIP LOCKED claims, expired leases, stale-worker
fencing, handler rollback/backoff, dead-letter exhaustion, interrupted transaction
recovery, one committed successful effect, migration downgrade/upgrade and actual
drift execution with explicit insufficient-data results. Existing deployment tests
verify runtime role restrictions; MLOps tests cover the existing monitoring paths.

Also executed CLI help and git diff whitespace checks successfully. The warning is
the existing Starlette/httpx deprecation. No full-suite, browser, container-runtime,
load or production deployment validation is claimed. No worker was installed or
left running. Internal worker database transactions do not make future external
notification deliveries exactly once; those require adapter-level deduplication.
