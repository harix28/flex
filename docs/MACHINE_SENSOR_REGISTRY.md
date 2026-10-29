# Phase 4 machine and sensor registry

Implemented backend-only registry, 2026-10-26. Registration is **not live ingestion**,
physical connectivity verification, a health assessment or a prediction. Identities come
from authorized registration, never from ML inference. No dashboard, hardware integration,
telemetry ingestion, QR scanner or new model training is included.

## Entities and provenance

The existing `machines`, `sensors` and `installations` tables are extended by incremental
migration `0003_registry`; there are no duplicate registry tables. Existing UUIDs, tenant
FKs and codes are preserved. `tenants` means organizations throughout this API.

Machines store tenant-scoped stable `asset_code`, display name, machine type, optional
manufacturer/model/serial, site/area/location, lifecycle and source. Lifecycle is
`active`, `inactive` or `archived`, separate from legacy operating status and health.
Every registry response explicitly says `health_status: unknown`; model compatibility
is `not_evaluated`. New registration never marks an asset healthy. The saved fd001-v1
bundle remains scoped to its verified FD001 replay contract, not every subset or hardware.

New records require `data_source: nasa_replay | physical_device`. Replay machines have
`source_binding: {dataset: "C-MAPSS", subset: "FD001"..."FD004", engine_id: positive int,
split: "test"}` and label **Simulated dataset asset**. Source binding is unique per
organization/dataset/subset/engine, including archived machines. FD001 engine 1 and FD002
engine 1 are distinct. Phase 4 deliberately supports the **test partition only**: train
and test IDs must never be silently conflated. Supporting training trajectories later
requires an explicit identity/uniqueness decision. API binding validation is structural;
the registration CLI additionally verifies local file structure and engine presence.

Physical records cannot carry a replay source binding. Their response says **Registered
physical asset; connectivity unverified**. No prediction is attached to physical records.
Legacy Phase 2 records without source information remain NULL/unclassified; no source,
hardware provenance or model compatibility is guessed. Legacy lifecycle is inactive,
except previously retired machines become archived. Legacy rows require a reviewed
operator provenance migration before new API installations; source identity is not a
mass-assignable update field.

Sensors store tenant-scoped stable `sensor_code`, display name, kind, source, optional
hardware identifier, unit/reference and active/retired status. Physical units require an
operator-supplied authoritative metadata reference; the service labels this provenance
`operator_supplied_reference` and does not claim automated verification of that document.
Omitted/unknown units are returned as null. The existing non-null canonical_unit column
uses an explicit `unknown` marker for new unknown units; legacy values are retained in
storage but not presented as verified units for unclassified sensors.

For replay, sensors are **logical dataset channels**, not devices installed on real
aircraft. IDs are `sensor_01` through `sensor_21`, in exactly the existing inference
order. The three operating settings are separately defined as `setting_1`, `setting_2`,
`setting_3`; they are not sensors and cannot be installed as sensor channels. The immutable
version-1 catalog is derived from `sentinel.data.SENSORS` / `SETTINGS` and exposed by the
registry channels endpoint. Units, physical names and component mappings are null/unknown.
Generic display labels such as “Logical sensor_01” identify a column, not a physical part.
Replay sensors cannot assert physical hardware IDs, physical units or component mappings.

## Installation history and integrity

Installations associate same-organization machine and sensor UUIDs with a channel/position,
timezone-aware installed/removed timestamps and optional note. All timestamps are stored
as timestamptz in UTC. Ranges are half-open `[installed_at, removed_at)`; null end is
unbounded. Removal must be strictly after installation. Adjacent replacements are allowed.

PostgreSQL GiST exclusions prevent overlaps for both a sensor and a machine/channel slot,
including closed historical ranges and concurrent requests. Composite tenant foreign keys
reject cross-tenant associations. A trigger locks the parent rows and rejects new mappings
to archived machines, retired sensors, mismatched sources or wrong replay channels. API
writes also check these states. Existing legacy mappings are preserved; they are not
reclassified as physical/replay. A migration encountering overlapping legacy slots fails
transactionally for operator review rather than deleting or truncating history.

Installation identity/start/slot is immutable. Removal closes a record without deletion;
a repeated identical removal is idempotent, a conflicting removal is 409. Closed periods
cannot be reopened/re-timed. Sensor replacement creates a new record after the old range
ends. Archived machines and retired sensors retain historical records, and existing open
mappings can still be removed; archival/retirement does not silently invent removal times.
Registry writes and minimal audit events are one transaction.

## Authentication and final role matrix

All routes are under `/api/v1/organizations/{tenant_id}`. This follows the Phase 3
organization route convention and is equivalent to the requested machine/sensor paths.
Every request derives the acting user from a valid session and verifies current active
membership in the routed organization. The tenant UUID is a scope request, not identity.
No endpoint permits changing tenant, machine/sensor code or source binding after creation.
Experimental API keys cannot authenticate these routes. Cookie mutations require the
existing Origin and session-bound CSRF token. See [authentication](AUTHENTICATION.md).

| Implemented permission | viewer | technician | plant_manager | admin |
|---|---|---|---|---|
| registry.read | Yes | Yes | Yes | Yes |
| registry.manage (machine/sensor creation, updates, archive/retire) | No | No | Yes | Yes |
| installations.manage (create/close mappings) | No | Yes | Yes | Yes |
| members.manage (unchanged) | No | No | No | Yes |

Permissions live in `sentinel/auth/permissions.py`; common session/CSRF checks are shared
in `sentinel/auth/context.py`, extracted from the tested Phase 3 boundary. Organization
mutations lock the organization row, recheck the session and current membership, then
write. This coarse serialization is intentional for this small local registry. Direct
privileged SQL remains outside application authorization; production RLS/grants are pending.

## API routes

Prefix all paths below with `/api/v1/organizations/{tenant_id}`:

| Method/path | Operation |
|---|---|
| GET /registry/channels | Versioned 21 sensor / 3 operating-setting definitions |
| POST /machines | Register a machine; 201 |
| GET /machines | Bounded list and exact-match filters |
| GET /machines/{id} | Details, stable code and canonical detail API path |
| PATCH /machines/{id} | Explicit display/location/lifecycle fields |
| POST /machines/{id}/archive | Idempotent archive; preserve identity/history |
| POST /sensors | Register physical or logical sensor; 201 |
| GET /sensors | Bounded list and exact-match filters |
| GET /sensors/{id} | Sensor details |
| PATCH /sensors/{id} | Explicit display/kind/unit/hardware/status fields |
| POST /machines/{id}/installations | Create mapping; 201 |
| GET /machines/{id}/installations | Ordered installation history |
| POST /installations/{id}/remove | Close mapping with removed_at |

No hard-delete endpoints exist. Archived machines cannot be edited/reactivated, retired
sensors cannot be reactivated. Code/source/channel identity is immutable; sensor kind/unit
changes are revalidated against the source. Unknown JSON fields, invalid enums, null
required patch values and naive timestamps return sanitized 422.

Lists accept limit 1–100 (default 25), offset 0–100000 and return `items,next_offset` plus
request_id. Machines sort by asset_code/UUID; sensors by sensor_code/UUID; installations
by installed time/UUID. This is deterministic offset pagination, not a snapshot across
concurrent edits. Filters are explicit exact matches: machines support asset_code,
lifecycle_status, data_source, machine_type, site; sensors support sensor_code, status,
data_source, kind, channel_id. Installation `open_only=true` selects null end times, not
a claim that a future-dated installation is currently physically active. No SQL expression
or arbitrary sorting interface exists.

Missing authentication gives 401, insufficient role gives 403, inaccessible organization
or record gives 404, input errors give 422, uniqueness/overlap/state conflicts give 409.
Database unavailability is controlled 503 and does not change model readiness.

Example replay machine body:

```json
{"asset_code":"NASA-FD001-TEST-1","name":"SIMULATED FD001 test engine 1",
 "machine_type":"cmapss_engine","data_source":"nasa_replay",
 "source_binding":{"dataset":"C-MAPSS","subset":"FD001","engine_id":1,"split":"test"}}
```

Example logical sensor body:

```json
{"sensor_code":"NASA-FD001-TEST-1-sensor_01","name":"Logical sensor_01",
 "kind":"cmapss_channel","data_source":"nasa_replay","channel_id":"sensor_01"}
```

Example mapping body (replace sensor UUID with the registered sensor):

```json
{"sensor_id":"00000000-0000-0000-0000-000000000001","channel":"sensor_01",
 "installed_at":"2026-01-01T00:00:00Z","note":"Logical demo mapping, not physical installation"}
```

## Register and inspect the first replay machine

Start PostgreSQL and upgrade as in [backend quickstart](../BACKEND_QUICKSTART.md). Use an
existing organization and authorized user; bootstrap only explicitly through Phase 3 if
none exist. Obtain organization/user UUIDs from authenticated `/api/v1/auth/me` or your
operator records. Then, from the project root (replace the two UUID placeholders):

```powershell
.\.venv\Scripts\python.exe -m sentinel.registry register-replay --env-file .runtime/postgres.env --tenant-id YOUR_ORG_UUID --actor-user-id YOUR_ADMIN_OR_MANAGER_UUID --subset FD001 --engine-id 1
```

Repeat `--engine-id` for additional explicitly selected engines, maximum 20. The default
data directory is project `data/raw`; override with `--data-dir`. The command reads only
`test_SUBSET.txt`, checks the existing 26-column parser/finite values/consecutive cycles
and selected engine presence, and reports the file SHA256 as provenance. A computed hash
alone is not proof of official source authenticity; the existing model check separately
verifies FD001 files against saved trusted evidence. There are no automatic downloads,
predictions, raw histories in registry tables, users or organizations created by this command.

Each engine creates one machine, 21 logical sensors and 21 mappings (43 records). Three
settings remain separate definitions. Mapping start is registration time and explicitly
not a physical installation or source sampling timestamp. Rerunning reports 43 existing
records, not duplicates. Each engine is a savepoint: any conflicting code/binding/sensor/
installation rolls back that engine's additions/audits and is reported as conflict;
independent selected engines can succeed. Exit 0 means no conflicts, 2 means reported
conflicts, 1 means invalid input/prerequisite failure. Existing records are not overwritten,
reopened or unretired. Renaming display fields does not change their identity.

This is a privileged database-operator CLI. `--actor-user-id` records an existing active
member with registry/install permissions, but is not proof of human authentication. CLI
access is controlled by local database credentials, just like the existing operator tools.
HTTP callers always use verified sessions; an actor UUID is never accepted as HTTP identity.

After login, GET `/api/v1/organizations/YOUR_ORG_UUID/machines?asset_code=NASA-FD001-TEST-1`.
Follow the returned machine's `detail_api_path`, then append `/installations` to inspect
its 21 logical mappings. The response includes stable machine code and path suitable for
a future QR label, with no tokens, credentials or personal information. A technician
scans/enters the code, the application loads the registered machine, and displays sensors
from installation records. The ML model never determines which machine was scanned.

## Migration, audit, verification and limits

Migration `0003_registry` adds fields to existing tables, source-binding uniqueness,
slot overlap exclusion, timestamp/installation guard triggers and generic target fields
to the existing auth_audit_events table. Actions record actor, tenant, target type/UUID,
request ID and timestamp; no unrestricted request bodies or credentials are recorded.
No existing migrations are rewritten. The initial six tables and old records remain.

Downgrade loses new source/lifecycle/metadata fields and the added slot constraint; it
refuses if registry audit records exist, rather than deleting them. Use disposable test
databases for downgrade tests; otherwise use a reviewed backup/restore plan. There is no
automatic data reset or overlap cleanup.

See [Phase 4 evidence](../reports/PHASE4_VALIDATION.md). PostgreSQL tests create and clean
up only randomly named disposable databases through the existing fixture. Missing explicit
SENTINEL_TEST_ADMIN_URL means visible skips. `scripts/verify-registry-local.py` performs
real HTTP registry checks and two real CLI registrations, then runs the unchanged
hash-verified prediction replay separately. It shuts down its temporary server and drops
only its generated database; passwords/cookies are never written to the report.

Limitations: test-partition replay only, metadata references are operator declarations,
no physical connectivity/telemetry, no ingestion/history readings, no compatibility
assignment to assets, offset pagination, coarse per-organization write serialization,
and existing Phase 3 production-security limitations. No new dependencies were required.
Phase 5 now implements persistent replay ingestion, quality validation and sensor reading history
using these registered identities and valid installation intervals.


## Phase 5 implemented extension (2026-10-26)

Current migration is `0004_replay`. `sentinel/ingestion/` implements persistent NASA
replay observations, immutable partition/file-version streams, atomic batches and
bounded history/quality APIs with the existing sessions, CSRF and tenant permissions.
The authoritative new contract is `docs/REPLAY_INGESTION.md`; Phase 6 integration
details are in `docs/PHASE5_HANDOFF.md`. Older phase-specific text above is historical.
Machine source bindings now accept `split: train|test` and optional `file_sha256`
(required for new train registrations). Different trajectory/version requires a new
machine. No prediction persistence or physical-device ingestion was implemented.
