# Phase 2 — PostgreSQL foundation validation

Date: 2026-10-25 (Asia/Calcutta).
Actual workspace: `H:\HarixAI\Meridian_Sentinel\Meridian_Sentinel_Full_Architecture`.
The requested historical Downloads path does not exist. The current workspace
contains the Phase 1 implementation and its validation report. No project copy,
model retraining, model overwrite, data replacement or Git commit was performed.
The outer Git repository contains unrelated changes; these were left untouched.

## Baseline and setup

Read AGENTS.md, PRD, architecture, implementation status, backend quickstart,
database/security blueprints, reference DDL, Phase 1 validation, configuration,
API, startup and tests before implementing. Baseline run: **53 passed**, one existing
Starlette/httpx deprecation warning, Python 3.12.15.

Installed packages were already compatible: SQLAlchemy 2.0.55, Alembic 1.20.1,
psycopg/psycopg-binary 3.3.3, greenlet 3.5.6, Mako 1.4.3, MarkupSafe 3.0.4.
No package installation was necessary; direct and platform dependency files now
pin these versions. `pip check`: **No broken requirements found**.

PostgreSQL 18.4 binaries and an existing PostgreSQL service were found. Docker CLI
exists but `docker info` reported that its daemon pipe was unavailable. Reused native
PostgreSQL binaries for an isolated SCRAM-authenticated cluster on 127.0.0.1:55432;
the existing service was untouched. Development database: `meridian_dev`. Passwords
are random and only stored in ACL-restricted ignored `.runtime/postgres.env`.

## Implemented and reviewed

Six foundation tables; UUID keys; timezone-aware timestamps; tenant-scoped codes;
composite tenant foreign keys; constrained additive membership roles; nonblank required
text; installation bounds, paired verification and GiST overlap exclusion. Immutable
Alembic revision `0001_registry` and its SQL are separate from the reference design.
See database/README.md for justified deviations and the authentication boundary.

SQLAlchemy transaction/session cleanup, rollback, bounded pool/connect/query/lock
waits, separate `/health/database`, safe CLI checks/upgrades and explicit idempotent
SAMPLE seed are implemented. There are no registry CRUD endpoints. Explicit repository
tenant scope is not authentication; RLS and production authorization remain pending.

## Commands actually executed

All commands ran from the actual workspace. Read-only discovery used `Get-Content`,
`rg`, `Test-Path`, `where.exe`, process/service/listener queries and package inspection.
Core commands (some repeated after fixes):

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip show SQLAlchemy alembic psycopg psycopg-binary greenlet Mako MarkupSafe
.\.venv\Scripts\python.exe -m pytest -q
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' --version
docker info --format '{{.ServerVersion}}'
.\.venv\Scripts\python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.check
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q sentinel tests database/migrations scripts/postgres-local.py
.\.venv\Scripts\python.exe -m pytest -q -m 'not postgres'
.\.venv\Scripts\python.exe scripts/postgres-local.py stop --bin 'C:\Program Files\PostgreSQL\18\bin'
```

The following inline Python orchestration was executed without printing credentials:

```python
os.environ['DATABASE_URL'] = read_env('.runtime/postgres.env')['DATABASE_URL']
for action in ('upgrade', 'check', 'seed-demo', 'seed-demo'):
    subprocess.run([sys.executable, '-m', 'sentinel.db', action], check=True)
os.environ['SENTINEL_TEST_ADMIN_URL'] = os.environ['DATABASE_URL']
subprocess.call([sys.executable, '-m', 'pytest', '-q', 'tests/test_postgres.py', '--tb=short'])
```

Additional executed runs used the same private test URL with `pytest -q --tb=short`
and `pytest -q -m postgres --tb=short`. Alembic's Python `command.upgrade(config,
'head', sql=True)` generated reports/phase2-upgrade.sql for review. The tests executed
real `upgrade head`, `downgrade base`, and re-upgrade on generated disposable databases.
No downgrade ran against development data.

## Actual verification results

| Verification | Result |
|---|---|
| Existing Phase 1 baseline | 53 passed |
| Final database-independent suite | 60 passed, 15 PostgreSQL tests deselected |
| Final real PostgreSQL integration coverage | 15 passed |
| Combined suite | 75 passed, zero failed, zero skipped, 25.93 seconds |
| Dependency check | No broken requirements |
| Python compile check | Passed |
| Fresh development migration | Upgrade and revision readiness succeeded |
| Seed repeated twice | Succeeded; one row in each of six tables |
| Native server stop/start | Succeeded; revision and six sample records persisted |
| Cleanup | Zero remaining generated test databases after combined run |

The existing Starlette/httpx deprecation warning remains. An Alembic configuration
warning was resolved by declaring `path_separator = os`. No warning suppression was
added. PostgreSQL integration tests are explicitly skipped when the dedicated test
admin URL is absent; **none were skipped in the verified combined run**. No mocked
or SQLite result is counted as PostgreSQL verification.

Integration assertions cover exact tables, migration round trip, new-connection
persistence, transaction rollback, required fields, uniqueness of codes/identities/
memberships, invalid roles, missing FKs, cross-tenant machine/sensor/verifier rejection,
tenant-scoped reads and retirement, invalid/overlapping/adjacent installation ranges,
concurrent overlap rejection and idempotent seeding. Unit tests cover configuration
precedence/redaction, unsupported URLs, required tenant context and controlled database
failure while model readiness stays 200. Database readiness is also false after downgrade.

Intermediate failures resolved: the native pg_ctl subprocess initially inherited
captured pipe handles into its long-running server, leaving its launcher waiting;
changed helper subprocess output to DEVNULL and reused the already-created cluster.
One unit test exposed missing database error codes in the HTTP sanitizer; added the
two explicit safe codes. Final tests passed without weakening assertions.

## Inference regression and persistence evidence

`sentinel.check` verified the trusted bundle, model/report and all three FD001 source
hashes. A real saved engine-1 request was submitted through FastAPI TestClient with
the existing verified model and private local API key (not a mocked predictor).
HTTP **200**, RUL **136.21971130371094 cycles**, observed cycle **31**, 30 observations;
absolute difference from Phase 1 was zero. Failure probability/interval remain null,
diagnosis remains unavailable. All three health endpoints returned 200 with the
migrated database. This was in-process HTTP validation, not a new external HTTP server.

Evidence: [prediction](phase2-smoke.json), [database restart persistence](phase2-database.json),
[rendered migration SQL](phase2-upgrade.sql). Model/training/inference source and artifacts
were not edited. Existing replay, API-key auth and PowerShell startup scripts remain intact.

## Files changed

- Configuration/API: sentinel/config.py, sentinel/api.py, sentinel/http_support.py,
  .env.example; both OpenAPI snapshots under packages/contracts/ and reports/.
- New persistence: sentinel/db/__init__.py, __main__.py, repository.py, seed.py.
- Migrations: alembic.ini, database/migrations/env.py,
  database/migrations/versions/0001_registry.py and 0001_registry.sql.
- Local operations: scripts/postgres-local.py.
- Tests: tests/test_database.py, tests/test_postgres.py, pytest.ini.
- Dependencies: requirements.txt, requirements.lock.txt, requirements.windows.lock.txt.
- Documentation: IMPLEMENTATION_STATUS.md, docs/IMPLEMENTATION_STATUS.md,
  BACKEND_QUICKSTART.md, database/README.md, database/migrations/README.md,
  database/seeds/README.md and this report.
- Evidence: reports/phase2-smoke.json, phase2-database.json, phase2-upgrade.sql.

## Operations, blockers and Phase 3

Follow [database operations](../database/README.md) for exact startup, private URL
loading, upgrade/check/seed and shutdown commands. Stop the API with Ctrl+C and
stop this cluster with the helper's `stop` action. Data remains in ignored .runtime.
The verification cluster was stopped at completion; no API server was launched.

No Phase 2 blockers remain. PostgreSQL verification used native Windows 18.4 only;
Docker engine, other platforms and production backup/restore were not verified.
Downgrade destroys all six tables' records; re-upgrade is not data recovery.
Production authentication remains pending. Phase 3 must implement login, validated
OIDC identity, secure sessions, roles and authenticated tenant resolution before
exposing registry routes. Add least-privilege runtime grants, audit and deployment
security; do not treat caller-provided tenant IDs or local API keys as tenant identity.
