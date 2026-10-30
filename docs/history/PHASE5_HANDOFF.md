# Phase 5 handoff to Antigravity for Phase 6

Phase 5 stores immutable validated NASA replay observations. Phase 6 prediction
persistence is not implemented. Reuse this repository, session authorization and
existing saved-model inference; do not retrain or replace artifacts.

## Implemented boundaries

Migration head: `0004_replay`, parent `0003_registry`. Actual schema is in
`database/migrations/versions/0004_replay.py`. Runtime readiness requires that head.
New tables: replay_streams, replay_batches, replay_observations. See
[ingestion contract](REPLAY_INGESTION.md) for all fields, uniqueness, immutable triggers,
transaction/idempotency behavior, API routes, examples and recovery limitations.

Canonical stream identity includes tenant, C-MAPSS, subset, train/test partition,
engine ID and exact whole-file SHA256. Train and test IDs never merge. Each machine
has one source and cannot switch version/partition; register a different machine.
Phase 4 unversioned test machines pin their hash in the first successful transaction.
Source metadata comes from replay_streams, not arbitrary request-supplied values.

Canonical order from `sentinel/data.py`: COLUMNS = engine_id,cycle, VALUES;
VALUES = SETTINGS (setting_1..3) + SENSORS (sensor_01..21). Input measurements are
binary64 JSON numbers / PostgreSQL double precision arrays; source cycle is int32.
No original aircraft timestamps exist. observed_at is NULL and ingested_at is actual
UTC arrival time. Do not join cycle to wall-clock installation intervals or infer
physical freshness from ingestion time. Sensor history is logical channel history.
No RUL ground truth is stored, parsed by the importer, or supplied to feature extraction.

## Selecting a causal contiguous window

Authenticate and authorize the organization/machine first. Resolve its stream and
schema. Use cutoff C >= W, choose start=C-W+1, and query **only** that stream's range.
For current bundle W=30; C=31 selects cycles2..31. HTTP example:
`GET /api/v1/organizations/{tenant}/machines/{machine}/observations?start_cycle=2&end_cycle=31&limit=30`.
For larger windows follow next_after_cycle within the same range (max page500).
Backfills can occur between HTTP pages; Phase 6 should preferably select a bounded
window in a single database transaction/query, or use a repeatable-read snapshot.

```sql
SELECT cycle, settings, sensors, batch_id, ingested_at
FROM replay_observations
WHERE tenant_id = :authorized_tenant AND machine_id = :machine
  AND stream_id = :resolved_stream AND cycle BETWEEN :start AND :cutoff
ORDER BY cycle ASC;
```

Require exactly W records, first=start, last=cutoff, and every adjacent cycle differs
by one. Reject/defer missing windows explicitly; never interpolate, zero-fill, use
future cycles or substitute older rows across a gap. Reconstruct records as
`[stream.engine_id, row.cycle, *row.settings, *row.sensors]`, preserving order. Persist
future prediction input identity/cutoff/bundle identity explicitly when designing
Phase 6, without mutating observation history. Do not use ingested_at as simulation
cutoff. A late historical backfill may make a previously unavailable window available.

## Existing inference integration points

`sentinel.inference.Predictor(directory, expected_manifest_sha256)` verifies bundle,
model and report hashes. `predict(subset, records)` calls existing strict
`validate_frame`, checks one engine and bundle window, then `window_features` from
`sentinel/features.py`; it accepts the reconstructed canonical26-column rows.
The current bundle is FD001/window30, experiment_only. Unsupported subsets and short
history return unavailable; probability/interval remain null. Current replay result
at engine1 test cycle31 is136.21971130371094 RUL cycles. Preserve that behavior.
Train-file persistence does not establish held-out evaluation validity or authorize
new training. Do not load official test RUL labels into model input.

`POST /api/v1/experimental/predict` remains the independent API-key experiment.
It does not persist predictions and grants no registry/history access. Phase 6 must
reuse `AuthContext`, live membership and centralized permissions for tenant resources;
never treat experimental API keys as user sessions. Derive tenant from authorized
path/context, not the request body. Current replay.ingest = admin/plant_manager;
replay.read = all four current roles. Mutations require session-bound CSRF and allowed
Origin; absent membership/scoped resource is404. New Phase 6 permissions need an
explicit design rather than inheriting broad API-key access.

## Setup and verification

Follow BACKEND_QUICKSTART.md for native PostgreSQL helper, private env configuration,
explicit administrator provisioning, registry and authenticated server startup.
No demo user/trajectory was left behind by Phase 5 verification. The local development
database was upgraded forward; disposable integration/HTTP databases are removed.
Run import using the exact command in REPLAY_INGESTION.md with existing identity UUIDs.

```powershell
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
$env:SENTINEL_TEST_ADMIN_URL = (Get-Content .runtime/postgres.env | Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13)
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify-ingestion-local.py
.\.venv\Scripts\python.exe -m sentinel.check
```

Tests require explicit CREATEDB/extension-capable PostgreSQL credentials. They create
only generated meridian_test_* databases and never use SQLite. Local real-file checks
need existing data/raw/test_FD001.txt and saved bundle artifacts; no API startup download.
Read [PHASE5_VALIDATION.md](../reports/PHASE5_VALIDATION.md) for executed commands, final
counts, warning and limitations; [phase5-http.json](../reports/phase5-http.json) contains
actual status codes, original/retry counts, source hash and small sanitized history.
No production deployment, RLS, retention/deletion workflow, external identity provider,
physical device ingestion or prediction persistence was added. No Phase 6 prerequisite
is deliberately deferred beyond those explicit scope boundaries.
