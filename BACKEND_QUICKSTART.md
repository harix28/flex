## Container hardening update - 2026-10-28

Deployment now requires explicit secrets, a private database network, a separate migration owner/runtime role, health-gated scripts and an HTTPS gateway (with an explicit loopback HTTP demo override). `/health/deployment` checks both model and database revision; existing health endpoints retain their contracts. Model artifacts and migration head `0007_mlops` are unchanged. Docker execution remains blocked on this host; configuration is not a production-readiness claim.

[Deployment setup](DEPLOYMENT.md) | [Executed validation](reports/DEPLOYMENT_FIXES_20261028.md)

# Meridian Sentinel â€” local backend foundation

Phase 1 verified on Windows, Python 3.12.15, 2026-10-25. This is a local,
replay-only experiment with API-key authentication, not production login or live
machine integration. The existing FD001 model and feature pipeline are unchanged.

## Existing environment

Open PowerShell in `Meridian_Sentinel_Full_Architecture`. Reuse `.venv`:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

The checked environment is healthy; no packages were installed for Phase 1.
If `.venv` is absent, create it with `py -3.12 -m venv .venv`, then install with
`.\.venv\Scripts\python.exe -m pip install -r requirements.windows.lock.txt`.
For an existing environment, inspect installed versions and install only
missing/incompatible dependencies. `requirements.txt` pins direct dependencies;
the Windows and Linux lock files retain their existing platform closures.
Phase 1 uses only existing dependencies and the Python standard library.

## Start and replay

Terminal 1:

```powershell
.\scripts\start-local.ps1
```

Keep this terminal open. The script checks Python 3.12, initializes private local
configuration, and runs the canonical entrypoint `python -m sentinel.serve`.
Stop it with **Ctrl+C** in this terminal. The script runs in the foreground.

Terminal 2, in the same project:

```powershell
.\scripts\check-local.ps1
```

This verifies the bundle, model/report hashes and three FD001 source hashes,
validates train/test histories, writes a real engine-1 request to
`.runtime/replay-engine1.json`, and sends it to the running server. It prints the
HTTP status and prediction, never the key or full request. It does not retrain or
modify data/model artifacts.

The default URL is `http://127.0.0.1:8000`. **This workspace's private `.env` uses
port 8001**, because an existing Python 3.14 process was already listening on
8000 during verification. Both scripts read the configured port automatically.
The Phase 1 verification server was left running in the background on
`http://127.0.0.1:8001`; see `reports/PHASE1_VALIDATION.md` for its shutdown command.
After stopping that verification server, use the foreground workflow above.

For a temporary port override, pass the same override to both commands:

```powershell
.\scripts\start-local.ps1 -Port 8002
# In terminal 2:
.\scripts\check-local.ps1 -Port 8002
```

## Configuration and credentials

Precedence is **explicit CLI overrides > process environment > project `.env`
> defaults**. A present but empty process variable is an override, not permission
to silently fall back. Settings loading does not mutate the process environment.
Relative model paths resolve beside the selected environment file. The default
file is the project-root `.env`, regardless of the caller's current directory.

| Setting | Validation / default |
|---|---|
| `SENTINEL_API_KEY` | Required, 24â€“256 printable ASCII characters, no spaces or placeholders |
| `SENTINEL_MODEL_DIR` | Existing directory; required by the server command |
| `SENTINEL_BUNDLE_SHA256` | Trusted 64-character lowercase SHA256; required with model directory |
| `DATABASE_URL` | Optional PostgreSQL psycopg URL; blank keeps inference independent; see database guide |
| `SENTINEL_HOST` | `127.0.0.1` only in this phase |
| `SENTINEL_PORT` | Integer 1â€“65535; default 8000 |

`.env.example` contains a blank key placeholder and the supplied bundle's trusted
manifest hash. Startup generates a cryptographically random key when none is
configured, stores it in `.env`, and reuses it on later starts. On Windows the
file's ACL is restricted to the current account before writing the secret; on
POSIX the file mode is 0600. `.env`, `.runtime/`, logs, raw data and runs are
gitignored. Never commit or paste the actual `.env`.

Server and replay independently load the same `.env`, so no key copying between
terminals is needed. A process `SENTINEL_API_KEY` overrides the file and must be
supplied identically in both terminals; startup does not save that process key.
A malformed key is rejected.

Supported `.env` syntax: blank lines, whole-line `#` comments, `KEY=value`, and
single/double quotes surrounding a literal value. No variable interpolation,
shell commands, multiline values, duplicate assignments or inline comments.

The canonical server supports `--env-file`, `--bundle`, `--sha256` and `--port`.
Existing explicit bundle/hash commands remain supported. The factory remains
`sentinel.api.create_app`, re-exported by `services.api.app` for compatibility.
Use the canonical server command to retain loopback binding and safe logging.

## API behavior

| Endpoint | Meaning |
|---|---|
| `GET /health` | Compatible legacy response: process status, model_loaded, mode |
| `GET /health/database` | 200 with reachable migrated database; 503 if missing/unavailable; independent of model readiness |
| `GET /health/live` | 200 when the process can answer |
| `GET /health/ready` | 200 when validated configuration and model are loaded; 503 without a model |
| `GET /api/v1/experimental/model` | Authenticated model metadata and measured report |
| `POST /api/v1/experimental/predict` | Authenticated replay-only RUL prediction |
| `GET /docs` | Local API documentation |

The factory can construct a model-less app for health tests; the canonical server
refuses to start without a configured, verified model. Bad hashes, schema or
artifact access fail before serving traffic. Readiness means loaded at startup,
not a repeated disk-integrity scan on every request.

Protected endpoints require `X-API-Key`. Requests contain subset, positive engine
ID, `data_mode: replay`, and consecutive observations with exactly 3 settings and
21 finite sensor values in NASA column order. IDs/cycles are bounded at
2,147,483,647. Limit: 1 MiB body, 1,000 observations. Supplied model: 30-cycle
window. Short history returns HTTP 200 with `status: unavailable` and null RUL;
wrong subset also returns unavailable. Invalid readings/gaps return 422; missing
or wrong keys return 401; absent model returns 503.

Every response has a server-generated `X-Request-ID` and `Cache-Control: no-store`.
Error bodies include the same request ID and sanitized codes, including 404,
405, 413 and unexpected 500 errors. Logs contain request IDs/statuses, not full
telemetry, keys, exception messages or query strings. Failure probability and
interval remain null; component diagnosis remains unavailable.

## Data and model integrity

The trusted `runs/fd001-v1/bundle.json` SHA256 is:

```text
06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd
```

The manifest verifies model/report bytes against the operator's trusted expected
hash. `sentinel.check` also compares `train_FD001.txt`, `test_FD001.txt` and
`RUL_FD001.txt` against the saved report. A matching hash does not make an arbitrary
operator-supplied model trustworthy.

Existing local NASA files were verified and reused. If `data/raw` is absent or
empty, use the existing official downloader:

```powershell
.\.venv\Scripts\python.exe -m sentinel.download --out data/raw
```

Never replace a nonempty directory blindly. If files are partial or hashes fail,
preserve them and investigate; download separately to an empty directory and
verify it before choosing to replace local data. A manually obtained official
archive can be passed with `--archive PATH_TO_ZIP`. Download failures are not
replaced with synthetic data. No downloads or retraining were needed for Phase 1.

Lower-level commands used by the check script:

```powershell
.\.venv\Scripts\python.exe -m sentinel.check
.\.venv\Scripts\python.exe -m sentinel.replay --request .runtime/replay-engine1.json
```

## Troubleshooting

- **Port already in use:** inspect the listener; do not stop unrelated processes.
  Set a free `SENTINEL_PORT` in `.env`, or use matching `-Port` overrides.
- **401:** remove stale process-key overrides or ensure both terminals use the
  same key. Restart the server after editing `.env`; settings load at startup.
- **Connection refused:** keep terminal 1 open and confirm the configured port.
- **Configuration error:** check field names, file syntax, directory existence
  and hash format. Values are deliberately omitted from error messages.
- **Bundle rejected:** verify the trusted hash and original artifact files; never
  bypass verification or trust a new hash merely to suppress an error.
- **Permission failure:** use the same Windows account that created `.env` and a
  filesystem supporting ACLs. Startup stops before saving a key if restriction fails.
- **Test warning:** the pinned Starlette release deprecates the httpx TestClient
  transport. Tests pass; the warning remains visible. No dependency migration was
  introduced solely to suppress it.

## Measured result and next scope

The supplied FD001 model's official-test MAE is 16.7939 cycles, RMSE 21.6085,
and bias +9.8855 over 100 engines. These are simulation metrics, not guarantees
or plant validation. Cycles are not hours/days. The Phase 1 engine-1 API replay
returned 136.21971130371094 cycles at observed cycle 31 and matched its saved
evaluation prediction within 0.0001 cycle. See `reports/phase1-smoke.json`.

Phase 2 database foundation is implemented and PostgreSQL-tested. See
[database operations](database/README.md) and [Phase 2 validation](reports/PHASE2_VALIDATION.md).
Phase 3 local login, sessions, roles and authenticated organization isolation are implemented. Production hardening, dashboard, maintenance,
MCP and deployment remain unimplemented. No calibrated probability or diagnosis
has been added.


## Phase 2 PostgreSQL startup and checks

Use the complete [database guide](database/README.md) for credentials, API connection,
shutdown, migrations, isolated tests and destructive downgrade warnings. Quick start:

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.db seed-demo --env-file .runtime/postgres.env
```

The separate local cluster uses port 55432. No changes are required to the existing
inference startup scripts. See the Phase 3 section for optional application login.


## Phase 3 backend authentication

See [authentication setup and CSRF examples](docs/AUTHENTICATION.md),
[role matrix](docs/ROLE_PERMISSIONS.md) and [executed verification](reports/PHASE3_VALIDATION.md).
After migrating, explicitly provision an administrator with hidden password prompts:

```powershell
.\.venv\Scripts\python.exe -m sentinel.auth bootstrap --env-file .runtime/postgres.env
$env:DATABASE_URL = (Get-Content -LiteralPath .runtime/postgres.env | Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13)
$env:SENTINEL_AUTH_ENABLED = 'true'
$env:SENTINEL_AUTH_LOCALHOST = 'true'
$env:SENTINEL_AUTH_ORIGINS = 'http://127.0.0.1:8001'
.\scripts\start-local.ps1 -Port 8001
```

No default admin/password is supplied. Login requires an allowed Origin and custom
CSRF-protection header; later mutations require the session CSRF token. Application
sessions cannot be replaced by the experimental API key. Stop the API with Ctrl+C;
stop PostgreSQL with the existing native helper. Local mode is not production-ready.


## Phase 4 machine and sensor registry

Run the existing database upgrade command to apply `0003_registry`, then use the same
Phase 3 session/cookie/CSRF setup. Registry routes are under
`/api/v1/organizations/{tenant_id}/machines`, `/sensors` and `/installations`.
An authorized existing organization/user can register selected local replay engines:

```powershell
.\.venv\Scripts\python.exe -m sentinel.registry register-replay --env-file .runtime/postgres.env --tenant-id YOUR_ORG_UUID --actor-user-id YOUR_ADMIN_OR_MANAGER_UUID --subset FD001 --engine-id 1
```

Replace the UUID placeholders; no users/organizations are implicitly created. Inspect
`/machines?asset_code=NASA-FD001-TEST-1`, then follow the returned detail_api_path and its
`/installations` subpath. See [registry guide](docs/MACHINE_SENSOR_REGISTRY.md) for payloads,
permission matrix, CLI conflicts, unknown metadata, QR identification and limitations.
See [validation](reports/PHASE4_VALIDATION.md) for actual HTTP/database/inference evidence.
Shutdown stays Ctrl+C for the API and the native PostgreSQL helper's stop action.

## Phase 5 persistent replay observations

Apply the current migration head, `0004_replay`, using the same private configuration:

```powershell
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
```

Start the API with the Phase 3 session configuration above. Select an existing replay
machine from the Phase 4 registry, then replace the identity placeholders and run:

```powershell
.\.venv\Scripts\python.exe -m sentinel.ingestion --base-url http://127.0.0.1:8001 --allow-local-http --email YOUR_ADMIN_EMAIL --tenant-id YOUR_ORG_UUID --machine-id YOUR_REGISTERED_MACHINE_UUID --data-dir data/raw --subset FD001 --partition test --engine-id 1 --batch-size 500
```

Password is prompted invisibly. The CLI verifies the file selection against that
machine and uses authenticated HTTP; it creates no users or assets. On first import,
an unversioned Phase 4 test binding is pinned to this exact file hash. Other versions
or partitions require a newly registered machine. Read `/observations?limit=30` and
`/data-quality?start_cycle=1&end_cycle=31` beneath the machine's detail_api_path.
See [full contract and recovery](docs/REPLAY_INGESTION.md),
[validation](reports/PHASE5_VALIDATION.md) and [Phase 6 handoff](docs/PHASE5_HANDOFF.md).

## Phase 6 persistent RUL predictions and maintenance priority

Apply the current migration head, `0005_predictions`:

```powershell
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
```

After ingesting observations for a registered FD001 test machine, request a prediction
using the authenticated session API:

```powershell
# 1. Request prediction at latest stored cycle (or specify cutoff_cycle in JSON body)
# POST /api/v1/machines/{machine_id}/predictions

# 2. View prediction history
# GET /api/v1/machines/{machine_id}/predictions?limit=25

# 3. View latest prediction (with is_current / is_outdated flags)
# GET /api/v1/machines/{machine_id}/predictions/latest

# 4. View maintenance priority ranking for organization
# GET /api/v1/maintenance-priorities?limit=50
```

To run the automated real HTTP verification script:

```powershell
$env:SENTINEL_TEST_ADMIN_URL = "postgresql+psycopg://meridian_local:PASSWORD@127.0.0.1:55432/postgres"
See [persistent predictions](docs/PERSISTENT_PREDICTIONS.md), [maintenance priority policy](docs/MAINTENANCE_PRIORITY_POLICY.md),
[validation](reports/PHASE6_VALIDATION.md) and [Phase 7 handoff](docs/PHASE6_HANDOFF.md).

## Phase 7 maintenance work orders and human approval workflow

Apply the current migration head, `0006_work_orders`:

```powershell
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
```

Create, approve, and track maintenance work orders via authenticated session API:

```powershell
# 1. Create prediction-linked draft (captures immutable evidence snapshot and disclaimer)
# POST /api/v1/predictions/{prediction_id}/work-order-draft

# 2. Or create manual draft for a machine
# POST /api/v1/work-orders

# 3. List work orders (filter by machine_id, status, priority, assignee_id)
# GET /api/v1/work-orders?status=draft&limit=25

# 4. View work order detail with snapshot evidence and outdated flag
# GET /api/v1/work-orders/{work_order_id}

# 5. Approve draft (as plant_manager or admin; required before work starts)
# POST /api/v1/work-orders/{work_order_id}/transitions
# Body: {"action": "approve", "expected_version": 1}

# 6. Assign eligible technician (as plant_manager or admin)
# POST /api/v1/work-orders/{work_order_id}/assignment
# Body: {"technician_id": "...", "expected_version": 2}

# 7. Start work (as assigned technician, plant_manager, or admin)
# POST /api/v1/work-orders/{work_order_id}/transitions
# Body: {"action": "start", "expected_version": 3}

# 8. Append technician notes
# POST /api/v1/work-orders/{work_order_id}/notes
# Body: {"note_text": "Completed inspection of fan rotor blades. Clearances nominal."}

# 9. Complete work order (with summary)
# POST /api/v1/work-orders/{work_order_id}/transitions
# Body: {"action": "complete", "summary": "Inspection complete per AMM 72-00.", "expected_version": 4}

# 10. View full history (transitions, assignments, and notes timeline)
# GET /api/v1/work-orders/{work_order_id}/history
```

To run the automated real HTTP loopback verification script on disposable PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts/verify-work-orders-local.py
```

See [maintenance workflow](docs/MAINTENANCE_WORKFLOW.md),
[validation](reports/PHASE7_VALIDATION.md) and [Phase 8 handoff](docs/PHASE7_HANDOFF.md).


## Phase 7 corrected client contract

Work-order notes now require `{"version": CURRENT_VERSION, "note_text": "Plain text"}`.
Read `work_order_version` from the response before the next edit or transition.
Approval409 `outdated_evidence` requires explicit cancellation and a fresh draft from
a current prediction. Execute requests recheck current assignee eligibility; managers
can reassign open tasks without removing assignment history. Work-order lists accept
created_from/created_to (timezone-aware timestamps) and due_from/due_to (dates).
See docs/MAINTENANCE_WORKFLOW.md and reports/PHASE7_FIXES_VALIDATION.md.

### Explicit release-managed startup

Set `SENTINEL_RELEASE_POINTER=.runtime/active_release.json` in the selected environment file only when using committed MLOps releases. This mode validates the pointer against PostgreSQL and overrides the model directory/digest as a pair. Without it, the existing explicit model settings remain authoritative. Recover a failed post-commit pointer publication with `python -m sentinel.mlops.cli sync-release-pointer`; see `docs/MODEL_RELEASE_AND_ROLLBACK.md`. No restart or deployment is needed to run the regression tests.
