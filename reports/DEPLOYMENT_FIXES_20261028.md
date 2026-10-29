# Deployment corrections — 2026-10-28

## Implemented behavior

- Removed published PostgreSQL ports and default passwords. Compose requires explicit secrets from the same env file supplied by both deployment scripts.
- Separated the one-shot owner-credential migration job from the runtime backend. Migration/provisioning failures block startup. The runtime role has table DML and sequence permissions, no schema creation or role/database administration, and read-only migration metadata.
- Added `/health/deployment` for model plus database-schema readiness and updated backend/gateway probes. Kept `/health/ready` model-only and `/health/live` process-only to preserve existing contracts. Updated OpenAPI snapshots.
- Added certificate-based HTTPS gateway configuration. The explicit local override uses only loopback HTTP port 8080 and localhost auth origins. Forwarded headers preserve the browser Host/port and overwrite client-supplied forwarding information. Backend has no published port; proxy trust assumes only trusted containers on the private network.
- Deployment scripts check Docker/Compose availability, propagate failures, use explicit env-file arguments and wait for health checks. No `Invoke-Expression`, success-after-sleep or implicit configuration copying remains.
- Added a secret-free `.env.container.example`; private env/certificate files and model artifacts remain excluded. Existing private configuration and model files were not overwritten. Frontend install now uses `npm ci` without a fallback dependency resolution.
- Added the Linux OpenMP runtime dependency to the backend image. One backend worker is configured because the login limiter is process-local.

## Checks

Before changes, the review established 254 distinct passing backend tests across runs/recovery, 30 frontend tests and a successful frontend build.

New regression tests exercise migration failure propagation, combined readiness, native PowerShell failures, exact env-file/wait arguments and real PostgreSQL runtime grants. The initial four new tests passed, including the isolated PostgreSQL permission check. The expanded script checks passed (five non-PostgreSQL tests). Final targeted rerun: all six deployment tests passed, including PostgreSQL, in 8.26s.

An initial broad run exposed two existing tests that explicitly require model readiness to remain independent of database availability. The implementation was corrected by adding a separate deployment probe; those existing assertions were preserved. The final database-independent run passed **134 tests**, with **126 PostgreSQL tests deselected**, in 34.83s. The broad run finished with 256 passed / 2 failed in 325.46s; its two failures were those now-corrected readiness compatibility assertions. All 126 PostgreSQL tests passed. Together with the final 134 database-independent checks, all 260 distinct tests passed across runs; this was not an uninterrupted green full-suite run.

Bash syntax validation passed for `scripts/deploy.sh` and `backend/entrypoint.sh`. Git ignore checks confirmed that private production settings, certificate keys and model artifacts remain ignored while the empty container example is not ignored.

Docker execution is **blocked**: the daemon pipe is unavailable and the Compose plugin is absent. Image builds, Compose schema validation, gateway TLS, fresh-volume startup and browser login have not been claimed as passed. No Docker containers were deployed. The mocked PowerShell checks never invoke actual Docker.

## Commands executed

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_container_deployment.py --tb=short
.venv/Scripts/python.exe -m pytest -q --tb=short
.venv/Scripts/python.exe -m pytest -q -m 'not postgres' --tb=short
```

PostgreSQL runs explicitly supplied `SENTINEL_TEST_ADMIN_URL` from the existing private local-cluster configuration. Fixtures create/drop generated disposable databases and test roles. No application records were reset. Test logs are in `.runtime/deployment-*`; they are not commit artifacts. Docker availability and Git Bash syntax checks were also executed.

## Changed files and operational limits

Deployment: `docker-compose.yml`, `docker-compose.dev.yml`, backend Dockerfile/entrypoint, frontend Dockerfile, gateway Dockerfile/config plus new local config, scripts/deploy.ps1, scripts/deploy.sh, Makefile, ignore files and `.env.container.example`.

Application: `sentinel/container_setup.py`, `sentinel/api.py`, `tests/test_container_deployment.py`, API schema snapshots. Documentation: DEPLOYMENT.md, README, quickstart, implementation status files and the superseded deployment report.

Schema revision stays `0007_mlops`. Existing volumes created with the previous owner/password require deliberate migration or backup/restore before using the new owner configuration; changing environment values does not rotate stored database credentials. Never remove volumes to bypass this. Generate distinct private secrets and provide a hostname-valid certificate before HTTPS deployment. The existing private env file was preserved and is not silently upgraded.

This is not a claim of complete production security. RLS, shared rate limiting for replicas, Docker model promotion/durable release pointers and production backup/restore verification remain outstanding. Standard Nginx image privilege behavior is documented; no claim that all containers run unprivileged is made. See [deployment setup](../DEPLOYMENT.md). The local override requires Compose 2.24.4+ per the [Docker merge reference](https://docs.docker.com/reference/compose-file/merge/).
