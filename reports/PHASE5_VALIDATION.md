# Phase 5 validation — 2026-10-26

Implemented in the existing Meridian Sentinel Full Architecture repository on Windows
with Python 3.12 and native PostgreSQL 18. No Lovable, dashboard, model training,
artifact replacement, physical-device ingestion or prediction persistence was added.

## Prerequisite inspection and baseline

Read AGENTS.md/PRD.md, README, quickstart, both implementation-status files,
architecture.md, Models.md, authentication/roles/registry documentation, the database
and API blueprints under docs/blueprint (no separate root database.md/api.md), and
actual sentinel source, migrations and tests. Architecture folders with planning
READMEs remain plans. Actual Phases 2–4 had PostgreSQL/Alembic, session/CSRF/roles,
tenant-scoped registry, source bindings and canonical logical channels. Phase 4
bindings identified only test trajectories and lacked file version; Phase 5 adds an
incremental migration instead of replacing the registry. No earlier-phase blocker.

Before changes: full suite **142 passed**, 1 existing Starlette/httpx warning,
268.76s; zero failures/skips. Trusted artifact verification passed. Existing saved
model engine1 test replay HTTP200, RUL136.21971130371094 cycles.

## Final checks

- Full final suite: **181 passed**, **0 failed, 0 skipped, 0 blocked**, 154.70s.
  Collected split:109 database-independent,72 PostgreSQL tests. PostgreSQL tests used
  generated disposable databases; no SQLite fallback or weakened existing assertions.
- Foundation migration suite after schema addition:15 passed in21.92s.
- Initial new-test run:38 passed,1 failed due to an incomplete legacy upgrade fixture
  (missing location). First full run:180 passed,1 failed because the same fixture used
  an empty location. Corrected it to the existing schema's explicit unknown sentinel;
  targeted migration test passed, followed by the full181-pass run above.
- One pre-existing Starlette/httpx TestClient deprecation warning remains. Dependencies
  were not replaced to silence it. `pip check`: no broken requirements.
- Compileall passed. Both OpenAPI snapshots match the factory (covered by existing test).
- `sentinel.check`: bundle/model/report hashes verified, all3 FD001 file hashes verified;
  existing30-observation inference input at cycle31 preserved.
- Real HTTP script passed; every status is recorded below and in phase5-http.json.
- Development database forward upgrade/check succeeded at0004_replay. Existing six
  sample registry table counts remain1 each; all3 new tables remain empty. Test users,
  observations and source bindings were confined to disposable verification databases.
  Final PostgreSQL catalog check found0 remaining meridian_test_* databases.
- Credential scan of157 source/document/report files found no configured local API key
  or PostgreSQL password. Runtime/private files, datasets and model runs remain ignored.
  No commit was made; the project was already untracked beneath its parent Git repository.

Coverage includes real-format numeric/channel round trips, strict shape/finite/integer
validation, partition/engine/subset/version mismatch, physical rejection, roles/CSRF,
API-key denial, tenant reads/writes, atomic rollback, out-of-order gaps, bounded/keyset
pagination, duplicate/conflicting requests, same/mismatched idempotency payloads,
concurrent duplicate/same-key/conflicting HTTP requests, direct database constraints,
immutable history, populated Phase4 forward upgrade, exclusion of RUL fields, and
unchanged experimental saved-model replay.

## Actual HTTP verification

`verify-ingestion-local.py` explicitly provisions two authorized test organizations in
a disposable PostgreSQL database, registers FD001 test engine1, then selects that
existing machine for the authenticated CLI importer. It uses a real Uvicorn loopback
socket and actual local test_FD001.txt. The importer is exercised through its callable
CLI implementation (hidden-password interactive terminal input itself was not automated).
The test file SHA256 is
`3cda7109ce17bafb5443f2ac926cfcf88154b941b8c4cf95eb55d1ddd6f52851`.

| Operation | Actual status / counts |
|---|---|
| Login |200|
| Explicit test-machine setup |201|
| Import in batches10/10/10/1 |4 x HTTP200;31 inserted,0 existing|
| Repeat identical import |4 x HTTP200;0 newly inserted,31 existing; original outcomes replayed|
| Fresh-key duplicate import |200;0 inserted,31 existing|
| History / quality / batch detail |200 each;31 cycles,first1/latest31,no gaps|
| Changed sensor_01 at cycle1 |409 observation_conflict; still31 total observations|
| Cross-tenant history / ingestion / forged tenant-machine path |404 each|
| Separate saved-model replay |200;136.21971130371094 RUL cycles; no prediction storage|

Small actual sanitized history response below (request ID omitted). UUIDs belong to
removed disposable test records and cannot be reused as permanent machine identifiers.

```json
{
  "stream": {
    "id": "79cede61-f376-4790-a47f-a26a95a40621",
    "tenant_id": "50e0095b-2f7a-4a68-8bb6-4d686047387b",
    "machine_id": "ae6f4538-9290-4ac5-9405-00146a5675bb",
    "dataset": "C-MAPSS",
    "subset": "FD001",
    "partition": "test",
    "engine_id": 1,
    "file_sha256": "3cda7109ce17bafb5443f2ac926cfcf88154b941b8c4cf95eb55d1ddd6f52851",
    "schema_version": 1,
    "created_at": "2026-10-26T07:05:27.582788+00:00"
  },
  "channel_schema": {
    "version": 1,
    "operating_settings": [
      "setting_1",
      "setting_2",
      "setting_3"
    ],
    "sensor_channels": [
      "sensor_01",
      "sensor_02",
      "sensor_03",
      "sensor_04",
      "sensor_05",
      "sensor_06",
      "sensor_07",
      "sensor_08",
      "sensor_09",
      "sensor_10",
      "sensor_11",
      "sensor_12",
      "sensor_13",
      "sensor_14",
      "sensor_15",
      "sensor_16",
      "sensor_17",
      "sensor_18",
      "sensor_19",
      "sensor_20",
      "sensor_21"
    ]
  },
  "items": [
    {
      "stream_id": "79cede61-f376-4790-a47f-a26a95a40621",
      "cycle": 1,
      "settings": [
        0.0023,
        0.0003,
        100.0
      ],
      "sensors": [
        518.67,
        643.02,
        1585.29,
        1398.21,
        14.62,
        21.61,
        553.9,
        2388.04,
        9050.17,
        1.3,
        47.2,
        521.72,
        2388.03,
        8125.55,
        8.4052,
        0.03,
        392.0,
        2388.0,
        100.0,
        38.86,
        23.3735
      ],
      "observed_at": null,
      "ingested_at": "2026-10-26T07:05:27.591397+00:00",
      "batch_id": "23f25944-cf89-4a97-900a-7b5427f1a637"
    },
    {
      "stream_id": "79cede61-f376-4790-a47f-a26a95a40621",
      "cycle": 2,
      "settings": [
        -0.0027,
        -0.0003,
        100.0
      ],
      "sensors": [
        518.67,
        641.71,
        1588.45,
        1395.42,
        14.62,
        21.61,
        554.85,
        2388.01,
        9054.42,
        1.3,
        47.5,
        522.16,
        2388.06,
        8139.62,
        8.3803,
        0.03,
        393.0,
        2388.0,
        100.0,
        39.02,
        23.3916
      ],
      "observed_at": null,
      "ingested_at": "2026-10-26T07:05:27.591397+00:00",
      "batch_id": "23f25944-cf89-4a97-900a-7b5427f1a637"
    }
  ],
  "next_after_cycle": 2,
  "data_mode": "replay"
}
```

Full provenance, timestamps, idempotency outcomes and actual statuses:
[phase5-http.json](phase5-http.json). Development schema/count evidence:
[phase5-database.json](phase5-database.json). Generated forward DDL:
[phase5-upgrade.sql](phase5-upgrade.sql).

## Commands executed

All from `H:\HarixAI\Projects\Meridian_Sentinel\Meridian_Sentinel_Full_Architecture`.
Credential values were loaded privately, never printed:

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
$env:SENTINEL_TEST_ADMIN_URL = (Get-Content .runtime/postgres.env | Where-Object { $_ -like 'DATABASE_URL=*' }) -replace '^DATABASE_URL=',''
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_postgres.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_ingestion.py tests/test_ingestion_postgres.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_ingestion_postgres.py::test_upgrade_populated_phase4_binding -q
.\.venv\Scripts\python.exe scripts/verify-ingestion-local.py
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.ingestion --help
.\.venv\Scripts\python.exe -m compileall -q sentinel scripts tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m sentinel.check
.\.venv\Scripts\python.exe -m pytest --collect-only -q -m postgres
.\.venv\Scripts\python.exe -m pytest --collect-only -q -m 'not postgres'
```

Also executed inline Python for baseline saved-model HTTP replay, OpenAPI generation,
Alembic offline `0003_registry:head` DDL export, development DB row counts, test-database
cleanup verification and credential scanning. rg/Get-Content inspected source/docs.
The native helper stop command is recorded after successful cleanup below.

## Files added or updated

Added: sentinel/ingestion/{__init__,schemas,service,api,importer,__main__}.py;
database/migrations/versions/0004_replay.py; tests/test_ingestion.py;
tests/test_ingestion_postgres.py; scripts/verify-ingestion-local.py;
docs/REPLAY_INGESTION.md; docs/PHASE5_HANDOFF.md; this report;
reports/phase5-http.json, phase5-database.json, phase5-upgrade.sql.

Updated: sentinel/api.py, http_support.py, db/__init__.py, auth/permissions.py;
sentinel/registry/{schemas,service,replay}.py; tests/test_postgres.py (additive table
expectation); reports/openapi.json; packages/contracts/experimental.openapi.json;
README.md, BACKEND_QUICKSTART.md, IMPLEMENTATION_STATUS.md,
docs/IMPLEMENTATION_STATUS.md, AUTHENTICATION.md, ROLE_PERMISSIONS.md,
MACHINE_SENSOR_REGISTRY.md, docs/blueprint/{api,database}.md,
database/README.md and packages/contracts/README.md. Existing source parser, features,
model artifacts and earlier migration revisions were preserved.

## Limitations and next phase

No unresolved Phase5 blocker. Production deployment/CI execution was not performed.
This verification requires local NASA files and artifacts, intentionally excluded from
Git; it does not download anything. No authenticated demo org/machine remains in the
development database, so operators must select/provision their explicit existing
identities before running the command in docs/REPLAY_INGESTION.md.

Hash provenance through HTTP is an authorized assertion; only the local importer
verifies exact file bytes. Pagination is not a cross-request snapshot under backfill.
Atomicity is per bounded batch, not whole CLI import. Failed batches are not retained
as successful ingestion metadata. Conflict response does not enumerate differing rows.
No retention/deletion workflow, RLS, physical freshness or production identity hardening
is added. Downgrade refuses populated/version-bound history; backup/restore notes are
in the ingestion guide. Phase6 handoff: [docs/PHASE5_HANDOFF.md](../docs/PHASE5_HANDOFF.md).

Final cleanup executed successfully:

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py stop --bin 'C:\Program Files\PostgreSQL\18\bin'
```

Isolated PostgreSQL stopped; development data retained. No API verification server remains running.
