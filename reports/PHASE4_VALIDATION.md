# Phase 4 - Machine and sensor registry validation

Date: 2026-10-26 (Asia/Calcutta).
Actual existing project: `H:\HarixAI\Projects\Meridian_Sentinel\Meridian_Sentinel_Full_Architecture`.
The old Downloads path in the request is absent. Work continued in the same relocated
project identified in Phase 3; no copy, rebuild, Lovable, dashboard or frontend was created.
No hardware connection, telemetry ingestion, model training or artifact overwrite occurred.

## Prerequisite verification

Read AGENTS.md, README, quickstart and both status documents, PRD, architecture, Models,
actual database/API blueprints, auth/role documentation, schema/migrations, API and tests.
Root database.md/api.md do not exist; the actual contracts are under docs/blueprint.
Distinguished historical planning claims from executable source and saved evidence.

Started the existing isolated PostgreSQL cluster using its native helper. The unchanged
baseline passed **116 tests**, zero failures/skips, in 112.44 seconds. This exercised
configuration, inference behavior, real PostgreSQL migrations and Phase 3 authentication.
The existing helper and database worked; no prerequisite repair was needed in Phase 4.
Reused PostgreSQL 18.4, Python 3.12.15 and installed dependencies. No dependencies changed.
The final real HTTP run also verified the existing trusted model and all three FD001 data
hashes. No substantial earlier phase was missing or rebuilt.

## Implemented and schema decisions

- Extended existing machines/sensors/installations with machine metadata, explicit
  lifecycle, source identity, timestamps, sensor metadata and installation notes.
- Authenticated organization-scoped machine/sensor create/list/detail/update, machine
  archive, sensor retire, installation create/history/remove, and logical channel catalog.
- Stable organization-scoped codes and canonical detail paths for future technician labels.
  Identity is registered, never inferred. Registry health is unknown and model compatibility
  not evaluated; no physical machine receives a replay prediction.
- NASA source binding is C-MAPSS/subset/test-engine ID, unique per organization. FD001 and
  FD002 engine 1 are distinct. Test partition is explicit; train/test identities are not
  conflated. Legacy records retain unknown source; none is silently classified as hardware.
- Stable sensor_01..sensor_21 definitions and separate setting_1..setting_3 preserve existing
  inference order. Unknown units/names/components remain null; replay sensors are logical.
- PostgreSQL exclusions prevent sensor and machine/channel overlap; row-locking triggers
  enforce archived/retired/source/channel restrictions and immutable mapping identity.
- Shared existing session/CSRF/current-membership checks, centralized permissions and
  transactional registry audits with actor, tenant, action, target UUID/type and time.
- Explicit operator CLI registers only selected local test engines, validates local data
  structure/presence, records file hash in its report, and reports created/existing/conflict
  counts. Per-engine savepoints prevent partial conflicting registration. No user/org,
  download, prediction or raw telemetry is created by registration.

New migration is `0003_registry`; existing 0001/0002 files were not rewritten. No duplicate
registry tables or new dependencies. See [registry guide](../docs/MACHINE_SENSOR_REGISTRY.md)
for field contracts, role matrix, intentional test-partition restriction and rollback notes.

## Commands executed

Commands ran from the actual project root. Inspection used Get-Content, rg and path/file
queries. Core commands:

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.registry --help
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q sentinel tests database/migrations scripts/verify-registry-local.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_foundation.py::test_openapi_snapshots_match_factory
```

Test orchestration loaded the dedicated admin URL without printing it:

```python
os.environ['SENTINEL_TEST_ADMIN_URL'] = read_env('.runtime/postgres.env')['DATABASE_URL']
subprocess.call([sys.executable, '-m', 'pytest', '-q', '--tb=short'])  # baseline and final
subprocess.call([sys.executable, '-m', 'pytest', '-q', 'tests/test_postgres.py',
                 'tests/test_auth_unit.py', '--tb=short'])
subprocess.call([sys.executable, '-m', 'pytest', '-q', 'tests/test_registry.py', '--tb=short'])
subprocess.call([sys.executable, 'scripts/verify-registry-local.py'])
```

The real verification script executed the CLI twice in a private environment pointing
only at its newly created disposable database:

```text
python -m sentinel.registry register-replay --tenant-id <test organization UUID>
  --actor-user-id <test administrator UUID> --subset FD001 --engine-id 2
```

The angle-bracket values above redact generated IDs; no password was passed as an argument.
Alembic tests executed fresh upgrade and populated-Phase-3 downgrade/upgrade only on
randomly named disposable databases. Offline Alembic range `0002_auth:head` generated
reports/phase4-upgrade.sql. Development was upgraded forward only, never reset/downgraded.
OpenAPI snapshots were regenerated from the factory, including accurate registry metadata.

## Test outcomes

| Executed run | Actual result |
|---|---|
| Unchanged Phase 1-3 baseline | 116 passed, 0 failed/skipped |
| Early PostgreSQL/auth-unit regression subset | 32 passed |
| Initial registry integration suite | 24 passed |
| Final complete suite with 26 registry cases | **142 passed, 0 failed, 0 skipped**, 189.76 seconds |
| Database-independent portion of final suite | **77 passed** |
| Real PostgreSQL portion of final suite | **65 passed** |
| Focused OpenAPI check after description refresh | 1 passed |
| Dependency check | No broken requirements found |
| Python compile check | Passed |

77/65 is the partition of the full successful run, not separate subset-run claims.
Only the pre-existing Starlette/httpx TestClient warning remains. No warnings were
suppressed and no existing test assertions were weakened or edited for Phase 4.
Tests skip PostgreSQL visibly without the explicit admin URL, but **none were skipped**
in the reported executed runs. No SQLite/mocked result is counted as PostgreSQL evidence.

The 26 new PostgreSQL cases cover machine/sensor create-read-update/archive/retire;
duplicate codes/bindings and separate subset identities; malformed source fields;
unknown/separate logical channels; all four role profiles and CSRF; cross-tenant
read/update/archive/install/remove attempts; immutable/mass-assigned fields; replacement
history, adjacent ranges and overlap; expired/closed removal semantics; archived/retired/
source restrictions; stable bounded filters/pages; API-key bypass rejection; current
membership removal; concurrent direct-DB slot contention; audit/write rollback; source
NULL constraint behavior; explicit replay idempotency, invalid engines/roles and late
conflict savepoint rollback; and preservation during populated schema upgrade.

Some CLI validation tests use explicitly labelled schema-valid local fixtures; they do
not claim NASA authenticity. Real verification below uses the existing hash-verified FD001
files. No synthetic fixture is reported as saved-model or official NASA verification.

## Actual real HTTP and CLI verification

`scripts/verify-registry-local.py` creates a disposable database, applies migrations,
creates two test organizations and random disposable credentials, runs two CLI registrations,
then starts a temporary Uvicorn server on a real loopback socket. HTTPX sends actual network
requests. The script cleans up only its own server and generated database.

| HTTP operation | Observed status |
|---|---|
| Authorized login | 200 |
| Create replay machine / logical sensor / installation | 201 / 201 / 201 |
| Read logical catalog / machine details / installation history | 200 / 200 / 200 |
| Duplicate machine registration | 409 |
| Remove logical installation | 200 |
| Viewer attempts registry write | 403 |
| Other organization reads machine / forges machine ID under own tenant | 404 / 404 |
| Missing CSRF / reuse logged-out session | 403 / 401 |
| Separate experimental saved-model replay | 200 |
| Liveness / model readiness / database readiness | 200 / 200 / 200 |

CLI first run for explicitly selected FD001 test engine 2: **43 created, 0 existing**
(one machine, 21 logical sensors, 21 mappings). Second run: **0 created, 43 existing**.
No other engines were registered by the CLI. The HTTP flow separately registered test
engine 1 and one logical mapping for its installation/removal demonstration. Catalog
verification found 21 sensor channels and 3 operating settings.

[Sanitized HTTP/CLI evidence](phase4-http.json) contains status codes, counts, safe test
resource IDs and prediction evidence, never passwords/session/CSRF tokens or cookie
headers. Those resource paths belong to a database that has been dropped; they are
verification evidence, not links to retained development assets. Audit counts confirm
machine/sensor/installation creation and removal; integration tests check update/archive
and failed-write rollback as well.

## Independent inference regression

Existing trusted bundle/model/report and all three FD001 source hashes verified.
The existing experimental endpoint returned engine 1, observed cycle 31, 30 observations,
**136.21971130371094 RUL cycles**, exactly matching previous phases. Probability and
interval remain null, diagnosis unavailable, replay mode and experiment_only release
unchanged. The replay request is evaluated separately; its result is not stored on a
registry machine and is not represented as live telemetry or a hardware prediction.
Model artifacts, training code, inference implementation, data and startup scripts were
not modified for this phase.

## Development migration and cleanup

[Database evidence](phase4-database.json): PostgreSQL 18.4, revision **0003_registry**,
one preserved record in each of the original six tables, one legacy machine explicitly
unclassified, and **zero remaining generated test databases**. The existing development
SAMPLE record was not converted into a verified replay asset. No organization/admin or
new demo registration was implicitly added to development.

[Rendered migration SQL](phase4-upgrade.sql) is schema-only. Actual private API key and
database password were checked against source/docs/reports and were absent. Runtime
credentials/data remain ignored. No secrets, datasets, session records or model artifacts
were committed. The verification HTTP server is stopped; the isolated PostgreSQL cluster
is stopped at completion with development data retained. Unrelated services are untouched.

## Files changed

- New registry modules: sentinel/registry/__init__.py, api.py, schemas.py, service.py,
  channels.py, replay.py, __main__.py.
- Shared authorization: sentinel/auth/context.py (extracted), sentinel/auth/api.py,
  sentinel/auth/permissions.py.
- Wiring/readiness: sentinel/api.py, sentinel/db/__init__.py;
  sentinel/db/repository.py documentation updated for authenticated callers.
- Migration: database/migrations/versions/0003_registry.py.
- Tests: tests/test_registry.py (26 parametrized PostgreSQL cases); old tests unchanged.
- Verification: scripts/verify-registry-local.py, reports/phase4-http.json,
  phase4-database.json, phase4-upgrade.sql and this report.
- Contracts: packages/contracts/experimental.openapi.json, reports/openapi.json.
- Docs: README.md, BACKEND_QUICKSTART.md, IMPLEMENTATION_STATUS.md,
  docs/IMPLEMENTATION_STATUS.md, docs/MACHINE_SENSOR_REGISTRY.md,
  docs/AUTHENTICATION.md, docs/ROLE_PERMISSIONS.md, database/README.md,
  database/migrations/README.md.

Dependency files and prior migrations remain unchanged in Phase 4.

## Register the first retained replay machine

Start PostgreSQL, apply upgrade, and use an existing authorized organization/admin or
plant manager. Follow [registry setup](../docs/MACHINE_SENSOR_REGISTRY.md) for the explicit
CLI command using your organization/user UUIDs and `--subset FD001 --engine-id 1`.
No user/org is implicitly created. Use the existing Phase 3 login/CSRF flow to GET the
organization's `/machines?asset_code=NASA-FD001-TEST-1`; follow its detail_api_path and
`/installations`. Stop the API with Ctrl+C and the database with the native helper's stop
action. All exact commands are in the guide and quickstart.

## Limitations and next phase

No Phase 4 blockers remain. Replay registration deliberately supports test partition only;
API source validation is structural, CLI additionally verifies local rows. Metadata
references are operator assertions, not automated authoritative-document checks. Legacy
unclassified records require explicit review before new API mappings. No physical
connectivity, readings, telemetry ingestion, compatibility assignment, maintenance flow or
frontend exists. Pagination is offset-based and writes serialize per organization. Existing
Phase 3 production-security limitations still apply; this is not a production-readiness
claim. Only native Windows PostgreSQL/Python were verified.

Next: **Phase 5 - persistent replay ingestion, data-quality validation and sensor reading
history**, resolved through this registry's tenant/source identity and installation validity.
