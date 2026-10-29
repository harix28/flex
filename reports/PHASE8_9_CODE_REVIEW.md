> Historical review. Corrections and current verification are recorded in [Phase 8–9 fixes](PHASE8_9_FIXES_VALIDATION.md).

# Phase 8–9 codebase review

Date: 2026-10-26

## Scope and verdict

Inspected the existing project at `H:\HarixAI\Projects\Meridian_Sentinel\Meridian_Sentinel_Full_Architecture`, including repository instructions, implementation/status documents, backend modules, migrations, frontend integration and tests. The workspace path `H:\HarixAI\Meridian_Sentinel` supplied in the desktop context does not exist; the explicitly confirmed project path above was used.

Phases 8 and 9 contain actual implementations, not only planning documents. Phase 8 is substantially implemented with unresolved integration defects. Phase 9 is an implemented foundation with correctness gaps in activation, evaluation and drift provenance; it should not yet be accepted as complete. Passing existing tests does not establish all documented acceptance claims.

| Area | Observed implementation | Assessment |
| --- | --- | --- |
| Local backend and saved inference | FastAPI, configuration, strict C-MAPSS parsing, saved FD001 model | Implemented; regression suite passes |
| PostgreSQL foundation | Incremental Alembic migrations through `0007_mlops` | Implemented; disposable PostgreSQL tests pass |
| Authentication and tenants | Sessions, CSRF, centralized roles, tenant-scoped APIs | Implemented; backend regression tests pass |
| Machine/sensor registry | Replay bindings, physical/replay distinctions, channels/installations | Implemented |
| Persistent replay | Provenance, observations, batches, history, quality, idempotency | Implemented |
| Persistent predictions | Stored causal windows, model/input provenance, maintenance priority | Implemented; saved-model parity tests pass |
| Maintenance workflow | Human approval, assignment, versioned transitions/notes/history | Implemented; earlier corrective tests pass |
| Phase 8 portal | Login, tenant context, fleet/machines, observations, predictions, work orders, registry and members | Substantial implementation; integration issues below |
| Phase 9 MLOps | Registry/verification, operator release CLI, observability, drift/evaluation, monitoring UI | Foundation present; correctness issues below |
| Background workers, external integrations and infrastructure | Worker, CMMS, IoT, notifications and other architecture folders include pending specifications | Do not count these as working integrations |

This is a source and test review, not a production certification or an exhaustive browser/security audit. No defensible percentage of the entire planned product follows from phase numbers alone.

## Findings

### 1. High: evaluation uses ingestion progress as the true trajectory endpoint

`sentinel/mlops/evaluation.py:90–99,145–161` calculates the maximum *stored* cycle and uses it as the endpoint for official final RUL labels. Historical ingestion is allowed to be partial. This produces wrong labels, error metrics and final-cutoff classification; metrics can change merely because more observations are ingested. The maximum is also keyed by engine ID rather than immutable source-stream identity.

Reproduced against disposable PostgreSQL with the real FD001 test engine 1 file: its full endpoint is cycle 31. Ingested only cycles 1–30, requested a stored-data prediction (HTTP 200), and ran the real evaluation service. It reported true RUL 112 at cycle 30. Correct ground truth is `112 + (31 - 30) = 113`.

Resolve the endpoint from a verified matching complete dataset/reference, preserve stream/file-version identity, and test partial ingestion and later arrival. Do not use ingestion progress as the ground-truth endpoint.

### 2. High: release activation does not verify the running artifact digest

`sentinel/mlops/deployment.py:217–240` reads `running_digest` but activates a desired release solely on version equality. A matching label does not prove that the desired artifact is running.

Reproduced against disposable PostgreSQL: registered and configured the verified baseline, supplied a predictor with the correct version and an all-zero model digest, and observed `status = active`. The existing release test itself uses `mock-sha` and expects success.

Compare the running artifact identity with the registered desired artifact before activation. Add mismatched-digest failure coverage.

Related source findings: deployment queries/superseding updates are not scoped by target environment; previous active rows are not superseded on activation; status checks can report an old active version before considering a newer desired release (`deployment.py:274–295`).

### 3. Medium: frontend discards structured backend error codes

`apps/web/src/services/api.ts:100–114` understands `detail` or top-level `code`, but the backend returns `{error: {code: ...}, request_id: ...}`. Conflict-specific handling cannot reliably recognize the real response.

Executed the actual TypeScript API client after transpilation with a mocked fetch response using the backend envelope. Result: HTTP 409, expected `outdated_evidence`, actual `ApiError.code = unknown_error`. This probe is a client contract reproduction, not a live HTTP request.

Parse the backend envelope and test real response shapes, including version conflicts, stale evidence, forbidden and authentication errors.

### 4. Medium: plant managers cannot load technicians for assignment

`apps/web/src/pages/WorkOrderDetailPage.tsx:68–76` loads the organization member list for eligible assignees and silently ignores failure. `sentinel/auth/api.py:157–163` requires `members.manage`, which is admin-only in `sentinel/auth/permissions.py`. Plant managers have work-order assignment permission but not this member-list permission.

Actual isolated TestClient HTTP result: authenticated plant-manager GET of the member-list endpoint returns 403. Consequently the portal's assignment selector cannot obtain technicians through its current lookup. Provide a narrowly authorized eligible-assignee lookup; do not grant broad membership administration merely to populate the selector.

### 5. Medium: tenant changes can retain old work-order detail

Source finding: `apps/web/src/pages/WorkOrderDetailPage.tsx:49–91` starts a new fetch on tenant change without clearing old work-order/history state. Error rendering is conditional on there being no existing work order. `App.tsx` does not key that detail page by tenant. A failed lookup in the new tenant can therefore leave the prior tenant's order visible under the new tenant selection. Requests also lack stale-response suppression on this path.

This is a client-context defect, not evidence that backend tenant authorization can be bypassed. Clear/key tenant-scoped detail state and cancel or ignore superseded requests. Browser reproduction was not performed in this review.

### 6. Medium: cached drift references bypass provenance checks

`sentinel/mlops/drift.py:22–25` returns any parseable cached JSON without checking the requested model, dataset hash, feature schema or training split. `evaluate_input_drift` loads the default reference rather than selecting a verified reference for its requested model version.

Reproduced by supplying a cache identifying a different model and empty feature statistics, with nonexistent model/data paths: the loader accepted the cache without verification. Bind cache identity to verified model/data/schema provenance and reject or rebuild incompatible references.

### 7. Medium: evaluation with no matching machines violates its schema

`sentinel/mlops/evaluation.py:64–85` inserts monitoring status `unavailable`. Migration `database/migrations/versions/0007_mlops.py:70` permits only `available`, `insufficient_data`, `incompatible_reference`, and `failed`.

Reproduced against disposable PostgreSQL: evaluation for a tenant without matching machines raises `IntegrityError`, instead of returning its intended controlled result. Synchronize the service and database status contract.

### Additional release concerns from source inspection

- `sentinel/mlops/deployment.py:78–110` writes the release pointer before the surrounding database transaction commits. Atomic file replacement does not provide atomicity between PostgreSQL and the filesystem; a later rollback can leave them inconsistent. A rollback-failure injection was not run.
- `sentinel/config.py:98–110` consults the release pointer only when no model directory and no explicit env-file/environ argument are supplied. Explicit model configuration takes precedence. Document and test restart activation with the actual launch configuration instead of assuming every restart follows the pointer.
- Existing release tests write the default repository release-pointer file. This review redirected those writes into a temporary directory and checked that the configured pointer was byte-for-byte unchanged.

## Actual checks

| Check | Result |
| --- | --- |
| Complete existing backend pytest suite, real disposable PostgreSQL enabled | **239 passed**, 0 failed, 0 skipped, 2 warnings; 287.69 seconds |
| Frontend Vitest | **24 passed**, 6 files |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed; Vite 6.4.5 |
| Additional diagnostic pytest probes | **2 passed**, confirming the defective behaviors described above; these are reproduction assertions, not acceptance passes |
| Actual API-client backend-error-envelope probe | Confirmed 409 code becomes `unknown_error` |
| Browser end-to-end walkthrough | Not run |
| Real deployment/rollback of the configured environment | Not performed |

The backend warnings concern Starlette/httpx deprecation and a Pydantic `end_cycle` alias declaration. The observed suite count is **239**, whereas Phase 9 documentation claims **242**. This review did not remove or alter tests; the current collected suite is the source of this result.

Commands used, from the project root unless indicated:

```powershell
# Read private PostgreSQL URL into the test environment without printing it.
$env:SENTINEL_TEST_ADMIN_URL = (Get-Content .runtime/postgres.env | Where-Object { $_ -like 'DATABASE_URL=*' }) -replace '^DATABASE_URL=',''

# Wrapper invokes pytest and redirects only release-file defaults to temporary storage.
.venv/Scripts/python.exe .runtime/run_phase89_assessment.py -q
.venv/Scripts/python.exe .runtime/run_phase89_assessment.py -q -s .runtime/test_phase89_review.py

# From apps/web:
& 'C:\Program Files\nodejs\npm.cmd' test
& 'C:\Program Files\nodejs\npm.cmd' run typecheck
& 'C:\Program Files\nodejs\npm.cmd' run build
```

Source inspection used `rg`, `Get-Content` and targeted file reads. The native local PostgreSQL cluster was started for isolated tests. Runtime evidence is in `.runtime/phase89-backend-tests.txt`, `.runtime/phase89-frontend-tests.txt`, `.runtime/phase89-build.txt`, and `.runtime/phase89-review-probes.txt`.

## Changes and handoff

No application code was changed. This review added this report plus local `.runtime` diagnostic scripts/logs; frontend validation regenerated build output. No model training or artifact replacement was performed. The configured release pointer was preserved, and diagnostic database records were confined to disposable test databases.

Git resolves the repository root to `H:/HarixAI`, not the Meridian project directory. Its status includes unrelated parent-directory changes; none were staged, committed or cleaned up.

Existing implementation handoffs remain `docs/PHASE8_HANDOFF.md` and `docs/PHASE9_HANDOFF.md`. Address these findings and add integration/regression tests before treating the corresponding acceptance claims as verified.
