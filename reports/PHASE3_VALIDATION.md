# Phase 3 validation — authentication, authorization and tenant isolation

Completed 2026-10-26, Asia/Calcutta. Current project:
`H:\HarixAI\Projects\Meridian_Sentinel\Meridian_Sentinel_Full_Architecture`.
Implementation and the full test run initially used
`H:\HarixAI\Meridian_Sentinel\Meridian_Sentinel_Full_Architecture`.
The project was moved during the chat pause; the same files and saved evidence were
located under Projects on continuation. The historical Downloads path is absent.
No new project copy, Git commit, dashboard, Lovable work, model training or dataset
replacement was performed.

## Baseline and prerequisites

Read repository instructions, README/setup/status, architecture, database/API/security
blueprints and actual configuration, API, database, migration and test source. Root
api.md/database.md are absent; the real contracts are under docs/blueprint. Source and
executed checks took precedence over stale planning README statements.

Phase 2 was implemented and working. Started the isolated native PostgreSQL 18.4 cluster
on loopback port 55432. The unchanged baseline passed **75 tests**, including PostgreSQL,
in 28.38 seconds. No database prerequisite repair was needed before Phase 3. Initial
migration `0001_registry` and its SQL were not rewritten; no SQLite was substituted.

Installed argon2-cffi 25.1.0 and email-validator 2.3.0, with argon2-cffi-bindings 26.1.0,
cffi 2.1.1, dnspython 2.9.0 and pycparser 3.12. Dependency files pin these versions.
Final dependency check reported no broken requirements.

After the folder move, a retained PostgreSQL PID file incorrectly prevented the helper
from starting a stopped cluster. The helper now uses `pg_ctl status` rather than PID-file
existence. It does not delete/reset data or terminate an unrelated process. This is an
operational prerequisite correction discovered during final cleanup, separate from auth.

## Implemented

- Normalized unique email, maintained Argon2id hashing/verification/rehash, active user
  checks and explicit organization membership checks. Existing OIDC identity fields remain.
- Explicit bootstrap/create-user/reset-password/disable-user CLI, hidden password prompts,
  no password arguments/default credentials, atomic duplicate protection. No startup admin.
- Opaque random sessions storing only session/CSRF digests; absolute expiry, logout,
  password-change/disable revocation, and current database membership/role authorization.
- Host-only HttpOnly/SameSite=Lax cookies; Secure outside explicit localhost development.
  Origin/custom-header login-CSRF strategy and session-bound CSRF on authenticated mutations.
- Login/me/logout/password/CSRF endpoints; organization read; admin-only member list/add/
  change/disable. Tenant predicates, strict inputs, transactional audit and last-admin checks.
- Central admin/plant_manager/technician/viewer mapping. Organization admin is not platform
  admin. No registry or maintenance HTTP workflows were invented.
- Exact CORS allowlist, proxy-header trust disabled, bounded process-local login limits,
  sanitized errors and minimal audit events tied to existing request IDs.
- Additive `0002_auth` migration: identity fields, slug, sessions/audits/indexes and
  revocation trigger. manager becomes plant_manager; ml_engineer upgrade aborts until
  explicit operator resolution, preserving existing data rather than guessing privileges.

The user-requested local password design supersedes OIDC-only planning for this slice.
See [authentication](../docs/AUTHENTICATION.md) and [roles](../docs/ROLE_PERMISSIONS.md).

## Executed commands

Read-only discovery used Get-Content, rg, path/process checks and package inspection.
Core commands (from the project root, some repeated after fixes):

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -m pip show argon2-cffi email-validator
.\.venv\Scripts\python.exe -m pip install 'argon2-cffi==25.1.0' 'email-validator==2.3.0'
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.auth --help
.\.venv\Scripts\python.exe -m compileall -q sentinel tests database/migrations scripts/verify-auth-local.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest --collect-only -q -m 'not postgres'
```

Executed test/network orchestration loaded the private URL without printing it:

```python
os.environ['SENTINEL_TEST_ADMIN_URL'] = read_env('.runtime/postgres.env')['DATABASE_URL']
subprocess.call([sys.executable, '-m', 'pytest', '-q'])  # unchanged baseline
subprocess.call([sys.executable, '-m', 'pytest', '-q',
                 'tests/test_auth_unit.py', 'tests/test_auth_postgres.py', '--tb=short'])
subprocess.call([sys.executable, '-m', 'pytest', '-q', '--tb=short'])
subprocess.call([sys.executable, 'scripts/verify-auth-local.py'])
```

The full suite was rerun after CLI and lockout checks were added. Alembic Python calls
executed fresh upgrade, disposable downgrade/re-upgrade, and populated Phase 2 upgrade.
Offline `command.upgrade(config, '0001_registry:head', sql=True)` generated the review SQL.
Development was upgraded forward only; no non-test database was reset or downgraded.

## Actual test results

| Run | Result |
|---|---|
| Unchanged baseline | 75 passed |
| Initial new auth tests | 34 passed |
| Expanded full suite | 112 passed |
| Final full suite | **116 passed, 0 failed, 0 skipped**, 72.93 seconds |
| Database-independent tests within final run | **77 passed** |
| Real PostgreSQL tests within final run | **39 passed** |
| Dependency and final compile checks | Passed |

The 77/39 partition was confirmed by collection markers; it is not a claim of separately
executed subset runs. The only warning is the existing Starlette/httpx TestClient
deprecation. Missing explicit test URL causes visible PostgreSQL skips, but none were
skipped in verified runs. No mocked/SQLite result is counted as PostgreSQL verification.

A compile check after the 112-test run caught a Windows encoding error in the new CLI
prompt. The prompt was made ASCII and explicit CLI bootstrap/non-TTY tests were added;
compile/help and the final suite passed. No assertions were weakened. The original Phase 2
schema equality test was extended for the two new tables; other old assertions remain.
OpenAPI was regenerated and the existing equality test passed.

Coverage includes login success/generic failures; Argon2id salts/verification/rehash;
disabled/unassigned users; expiry, revocation, logout and rotation; password changes/reset;
CSRF and Origin rejection; role permissions; forged tenant/member IDs; mass assignment;
immediate role/removal effects; concurrent last-admin demotions; rollback on failure;
unusable admins; login limits and proxy spoof attempts; secure cookies/CORS; API-key
separation; safe logs/errors; database failure; bootstrap duplicate atomicity; email/session
constraints; fresh migration and populated Phase 2 preservation. CLI hidden-input functions
were supplied test input against real PostgreSQL; no permanent admin was created.

## Real loopback HTTP verification

The verification script created a new disposable PostgreSQL database, two organizations
and users with all four roles and random disposable credentials. It started a temporary
Uvicorn server and sent actual network HTTP requests, not only TestClient requests.

| Request | HTTP result |
|---|---|
| Admin login / me / own member list | 200 / 200 / 200 |
| Cross-tenant member read / write | 404 / 404 |
| Logout without CSRF | 403 |
| Logout with CSRF / reuse old session | 200 / 401 |
| Viewer login / own organization read | 200 / 200 |
| Viewer member list / membership write | 403 / 403 |
| Saved-model replay | 200 |
| Liveness / model readiness / database readiness | 200 / 200 / 200 |

[Sanitized HTTP evidence](phase3-http.json) includes no passwords, session/CSRF tokens or
cookie headers. Audit counts confirm bootstrap, login and logout; integration tests also
verify failed login, rate-limit and membership audits.

Existing check logic verified trusted bundle/model/report and all three FD001 source
hashes. Engine 1 at observed cycle 31 returned **136.21971130371094 RUL cycles** with
30 observations, exactly matching prior phases. Probability/interval remain null,
diagnosis unavailable, data mode replay and release status experiment_only.
No training/inference model source or artifacts were edited.

## Data and cleanup evidence

[Database evidence](phase3-database.json): revision `0002_auth`, one preserved SAMPLE
record in each of the six Phase 2 tables, zero local password identities in development,
and zero remaining generated test databases after verification. No default administrator
or password exists. [Rendered migration](phase3-upgrade.sql) contains schema only.
The verification script shut down its HTTP server and dropped only its generated database.

## Files changed

- New auth: sentinel/auth/__init__.py, __main__.py, security.py, permissions.py,
  limiter.py, service.py and api.py.
- Runtime/config: sentinel/config.py, sentinel/api.py, sentinel/http_support.py,
  sentinel/serve.py, sentinel/db/__init__.py, .env.example.
- Migration: database/migrations/versions/0002_auth.py (0001 unchanged).
- Tests: tests/test_auth_unit.py, tests/test_auth_postgres.py; additive table expectation
  in tests/test_postgres.py.
- Operations: scripts/verify-auth-local.py, scripts/postgres-local.py (stale-PID fix).
- Contracts: packages/contracts/experimental.openapi.json, reports/openapi.json.
- Dependencies: requirements.txt, requirements.lock.txt, requirements.windows.lock.txt.
- Docs: README.md, BACKEND_QUICKSTART.md, both IMPLEMENTATION_STATUS.md files,
  docs/AUTHENTICATION.md, docs/ROLE_PERMISSIONS.md, database/README.md,
  database/migrations/README.md and this report.
- Evidence: reports/phase3-http.json, phase3-database.json, phase3-upgrade.sql.

Private environment/database state remains ignored. No secrets, session data, datasets
or model artifacts were committed.

## Startup, shutdown and remaining limitations

Follow [authentication setup](../docs/AUTHENTICATION.md): start PostgreSQL, upgrade/check,
explicitly bootstrap using hidden password prompts, set private DATABASE_URL and auth
flags/exact localhost origin, then run the existing start-local.ps1 on the matching port.
Stop the API with Ctrl+C. Stop the isolated cluster with:

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py stop --bin 'C:\Program Files\PostgreSQL\18\bin'
```

This is not production-ready. Login limits are process-local; production TLS/proxy
configuration, least-privilege grants/RLS, append-only audit permissions, shared rate
limiting, MFA, email verification/recovery, OIDC, idle timeout, retention jobs and production
restore verification remain pending. Password-change requests require session/CSRF/current
password but lack a separate abuse limiter. Only Windows PostgreSQL 18.4/Python 3.12 was
tested; Docker/Linux were not verified.

Next backend phase: authenticated machine/sensor registry and installation history using
the established membership context, role mapping and composite tenant foreign keys,
with cross-tenant API tests. No dashboard or maintenance placeholders are required.


## Final continuation checks after the workspace move

Reran `scripts/verify-auth-local.py` successfully from the new Projects path: all HTTP
statuses and the saved-model prediction matched the table above. Reran compile checks,
verified database readiness and zero remaining generated test databases, and verified
start is idempotent while the cluster is already running. The updated helper then stopped
the isolated cluster successfully with data retained. Source/docs/evidence scanning found
neither the actual private API key nor database password. No blockers remain for this phase.
The complete 116-test run predates the folder move; post-move checks were the real HTTP,
model, compile, database-readiness and native startup/shutdown checks just listed.
