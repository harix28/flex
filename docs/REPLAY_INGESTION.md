# Persistent NASA replay ingestion (Phase 5)

Implemented in `sentinel/ingestion/`, migration `0004_replay`. Observations only;
no prediction persistence, live-device ingestion, health classification or dashboard.
Phase 4 registry and Phase 3 session authentication are prerequisites. PostgreSQL 15+
is required for NULLS NOT DISTINCT indexes; validation used PostgreSQL 18.

## Source and channel contract

A stream is one `(organization, C-MAPSS, subset, partition, engine_id, file_sha256)`.
Partition is `train` or `test`; engine 1 in train and engine 1 in test are different
trajectories. SHA-256 is lowercase hex of the complete, exact source file bytes.
Each machine has at most one immutable stream. New partition or file version requires
a new registered machine with a different asset_code and explicit source binding.
The registry binding uses `split`; ingestion uses `partition` for the same value.
New train bindings must include `file_sha256`. Test bindings may include it; an
unversioned Phase 4 test binding is pinned on its first successful batch, in the
same transaction. Failed ingestion cannot pin a version. Already pinned versions
cannot be changed, including through direct ordinary SQL updates.

`sentinel.data.SETTINGS`, `SENSORS`, and `COLUMNS` are authoritative:
`setting_1, setting_2, setting_3`; then `sensor_01` through `sensor_21`.
JSON arrays store three settings and twenty-one measurements as PostgreSQL float8
(double precision / IEEE binary64). No rounding, normalization of measurements,
unit conversion, interpolation or zero-filling; signed zero is canonicalized to zero.
Cycles and engine IDs are integers 1..2147483647. Numbers must be finite; booleans,
strings, null measurements and extra fields (including RUL) are rejected.
`schema_version` is integer 1. `observed_at` must be null or absent because C-MAPSS
has no original aircraft timestamps. `ingested_at` is actual UTC database time.
Source cycle is never converted into wall time. Logical channel order does not
imply a physical installation or a wall-clock sensor-installation interval.

## Persistence and transactions

Regular PostgreSQL tables are sufficient; no new storage dependency:

- `replay_streams`: immutable source identity and schema version, one per machine.
- `replay_batches`: actor, request ID, payload digest, bounded idempotency key,
  source link, requested/inserted/existing counts, cycle bounds and ingestion time.
  This is also the durable successful-outcome/idempotency record.
- `replay_observations`: tenant/machine/stream/cycle, arrays, first-insertion batch,
  null observed_at, actual ingested_at. Primary key `(tenant_id,stream_id,cycle)`.

Composite foreign keys include tenant and machine throughout, including the full
machine source identity and batch actor membership. Indexes support tenant/machine/
cycle history, batch lookup and provenance. DB checks enforce finite array shapes;
triggers prohibit ordinary updates/deletes of historical rows and source bindings.
Raw files and official test RUL labels are never stored. Only the input file hash
is persisted. HTTP callers assert the hash; the server does not open a filesystem
path or prove submitted values came from that file. The local CLI hashes and parses
the same bytes using the existing strict parser. Import remains an authorized action.

Batches contain 1..500 distinct cycles; request body limit is 1 MiB. All rows validate
before any write. Machine/tenant row locks serialize writes, and PK/unique/FK/check
constraints enforce integrity across connections. A valid batch and metadata commit
together. Any malformed row or differing existing observation rolls back the entire
batch. A multi-batch CLI import is atomic per batch, not for the whole file.
Historical batches may arrive out of order. The strict full-file NASA parser still
rejects missing cycles inside an engine's input file; the API accepts validated
partial selections without requiring arrival order.

Identical stored rows return accurate inserted/existing counts without duplicates.
A changed value at an existing cycle returns 409 `observation_conflict`; no overwrite.
Every POST requires `Idempotency-Key`, 1..128 characters from `[A-Za-z0-9._:-]`.
Scope is organization + immutable machine/source + `replay_ingest`. Canonical payload
hashing sorts cycles and includes source identity, defaults, all measurements and null
observed_at. Same key/same payload returns the original batch/counts and
`idempotency_replayed:true`; the new request ID remains separate. Different payload
returns 409 `idempotency_conflict`. A fresh key for identical observations creates a
new batch with inserted_count=0. Failed batches do not reserve keys. Records have no
expiry/retention cleanup in this phase. Retry transient 503 with the same key.

## Authentication and routes

All paths below begin `/api/v1/organizations/{tenant_id}`. Tenant IDs in bodies are
forbidden. The path is checked against current active membership on every operation;
resource queries are also tenant-scoped. Unknown/cross-tenant resources return 404.
Session cookie required; experimental API keys grant no access. All writes require
an allowed Origin and session-bound `X-CSRF-Token`. Login requires Origin and
`X-CSRF-Protection: 1`; see AUTHENTICATION.md. Permissions:

| Operation | admin | plant_manager | technician | viewer |
|---|---|---|---|---|
| replay.ingest | Yes | Yes | No | No |
| replay.read | Yes | Yes | Yes | Yes |

- `POST /machines/{machine_id}/replay-batches`: HTTP 200 with batch, stream,
  idempotency_replayed, request_id. New ingestion into archived machines is 409;
  an original successful idempotency outcome remains readable. Physical machines
  are 422 `replay_only` on replay endpoints.
- `GET /machines/{machine_id}/observations`: start_cycle (default 1), end_cycle
  (default INT32 max), after_cycle (exclusive, default 0), limit (1..500, default100).
  Response items ascend by cycle, with stream identity, channel schema and
  next_after_cycle (null at page end). Range is inclusive. No unbounded response.
  Pagination is keyset-based, not a cross-request snapshot: a later historical
  backfill behind the cursor requires restarting the scan.
- `GET /machines/{machine_id}/data-quality`: inclusive start_cycle/end_cycle, max
  span10,000. Default start1; omitted end=min(start+999, max(start,latest storedcycle)).
  Count/first/latest cycle and latest_ingested_at are scoped to this requested range.
  Gaps are inclusive absent-cycle intervals, including boundary gaps, without filling.
  Empty range yields count0, null first/latest/time, and the requested range as a gap.
  Duplicate imports do not advance latest observation ingestion time. Schema
  compatibility means canonical channels only, not model compatibility or health.
- `GET /ingestion-batches/{batch_id}`: original successful outcome and full stream.

Body shape (measurement arrays below are illustrative, not a replacement for NASA data):

```json
{"source":{"dataset":"C-MAPSS","subset":"FD001","partition":"test","engine_id":1,
"file_sha256":"<64 lowercase hex characters>","schema_version":1},
"observations":[{"cycle":1,"settings":[0.1,0.2,0.3],
"sensors":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21],"observed_at":null}]}
```

## Local import

Start PostgreSQL, upgrade, and start the API with session authentication enabled
using BACKEND_QUICKSTART.md. Explicitly provision your authorized user and register
a replay machine first (existing Phase 4 registry CLI or authenticated registry API).
The importer never creates users, organizations, machines, or downloads data.
Find the machine UUID through `/machines?asset_code=NASA-FD001-TEST-1`.
Run from repository root, replacing the three identity placeholders:

```powershell
.\.venv\Scripts\python.exe -m sentinel.ingestion --base-url http://127.0.0.1:8001 --allow-local-http --email YOUR_ADMIN_EMAIL --tenant-id YOUR_ORG_UUID --machine-id YOUR_REGISTERED_MACHINE_UUID --data-dir data/raw --subset FD001 --partition test --engine-id 1 --batch-size 500
```

The password is prompted invisibly; do not put credentials in command arguments.
`--start-cycle` and `--end-cycle` select an inclusive optional range. File path is
constructed locally as `data-dir/{partition}_{subset}.txt`. No server path is accepted.
HTTPS is required except explicit `--allow-local-http` for localhost/loopback. Redirects
are disabled. Login/logout use the same session/CSRF service as other clients.
Deterministic per-payload keys make reruns safe. CLI inserted/existing totals describe
this run; each batch retains its original outcome and idempotency_replayed flag.
On 409 it reports a conflicting batch and stops; the exact number of changed rows is
unknown (`conflicting_observations:null`), because the API rejects the whole batch.
Exit0 success, exit2 conflict, exit1 validation/network/authentication failure.

## Migration and recovery

`python -m sentinel.db upgrade --env-file .runtime/postgres.env` applies 0004_replay
forward from0003_registry without changing existing UUIDs, roles or installations.
Back up before deployment. Downgrade refuses any streams or bound/train machines;
never discard historical observations to force a rollback. Restore a verified
pre-migration backup into a separate database and revert application code together
if rollback is required. Empty disposable databases support tested downgrade/upgrade.
Database owner privileges remain trusted; this is application tenant isolation plus
composite constraints, not PostgreSQL row-level security or tamper-proof storage.

See [validation](../reports/PHASE5_VALIDATION.md), [actual HTTP evidence](../reports/phase5-http.json)
and [Phase 6 handoff](PHASE5_HANDOFF.md).
