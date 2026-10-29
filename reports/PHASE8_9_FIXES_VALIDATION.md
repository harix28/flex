# Phase 8–9 corrective validation

Date: 2026-10-27. Follow-up to `PHASE8_9_CODE_REVIEW.md`.

## Implemented corrections

- Evaluation uses the endpoint in the complete verified test source, scoped to matching source-file identity. Model/report/source/label hashes are checked; partial ingestion cannot redefine ground truth. Empty matching-machine evaluations persist `insufficient_data`.
- Activation checks version and bundle/model/report digests. Successful activation supersedes previous active rows. Desired releases take precedence in status; offline status does not claim a running process was verified. Rejected/archived candidates and non-local environments are refused.
- Release metadata and reconstructable audit payload commit before pointer publication. Serialized publication reads the latest committed release. Database rollback leaves the pointer unchanged; post-commit filesystem failures are recoverable through `sync-release-pointer`. Explicit `SENTINEL_RELEASE_POINTER` startup validates committed identity, including with `--env-file`.
- Drift reference reuse verifies bundle/report/dataset hashes, training-engine selection, window and ordered feature schema. Incompatible caches are rebuilt; wrong requested model versions do not silently use the baseline reference.
- The client preserves backend error envelopes and request IDs. Conflict text tells users to refresh rather than falsely claiming refresh occurred.
- Admins/managers can retrieve active eligible technicians through a read-only, tenant-scoped, paginated endpoint without membership administration or email exposure. Assignment writes retain CSRF, eligibility and version checks.
- Tenant switches remount all scoped page content; detail-ID switches remount detail pages. Old page requests cannot populate the newly mounted tenant view.
- Monitoring displays verified identity for unregistered serving artifacts and distinguishes `active_untracked`; it no longer defaults unknown deployment state to ACTIVE.
- OpenAPI snapshots were regenerated. No schema migration: revision remains `0007_mlops`.

## Verification results

- Final full backend run: **245 passed, 1 PostgreSQL connection-timeout setup error**, 0 assertion failures, 0 skipped; two warnings. The local database was subsequently unresponsive. A retry while it remained unavailable also timed out. Started the existing retained local PostgreSQL cluster with `scripts/postgres-local.py` (no reset), then reran only the affected `test_assignee_eligibility_and_tenant_boundary`: **1 passed**. Thus all **246 backend tests passed across the full run and targeted recovery retry**; this is not a claim of one uninterrupted green run. Warnings concern Starlette/httpx deprecation and a Pydantic alias declaration.

- Frontend: **30 tests passed**, eight test files; TypeScript and production build passed.
- Headless Microsoft Edge with the actual built React portal and a temporary loopback FastAPI server backed by disposable PostgreSQL: **1 browser regression passed**.
- Earlier focused PostgreSQL regression run: **7 passed**. These are included in the final backend suite.
- Initial full run: 245 passed / 1 failed because the new route was missing from checked-in OpenAPI snapshots. Corrected by generating the schema from the application factory; no test was weakened.
- Initial browser run reached successful assignment/conflict/tenant checks but failed on an incorrectly named test heading. Corrected the selector to the actual page heading and added verified-digest/untracked-state assertions; the rerun passed.
- Saved artifact SHA-256 values match the review baseline:
  - bundle: `06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd`
  - model: `b3e9ed3f0319b8095848ad6ce74cb8cc64cfd91adc06647d7cb95eaf57be478f`
  - report: `a47046cd495015b881040d8fe24767a644eb255fafa331b0c4a2dfd226ecf951`

## Actual isolated results

| Operation | Result |
| --- | --- |
| Manager browser login | HTTP 200 |
| Manager eligible-assignee lookup | HTTP 200 |
| Manager assignment through portal | HTTP 200 |
| Stale-version assignment through portal | HTTP 409, actionable conflict message |
| Switch to second organization with first organization's order ID | HTTP 404; prior order no longer displayed |
| Monitoring page | Verified bundle digest and ACTIVE_UNTRACKED rendered; screenshot inspected |
| Partial FD001 engine 1 prediction at cutoff 30 | HTTP 200; evaluated true RUL 113 |
| Ingest final cycle 31 and reevaluate previous cutoff | Earlier evaluation unchanged |
| Wrong running artifact identity | Desired release marked failed; no false active state |
| Transaction rollback after desired-release creation | Existing pointer unchanged |
| Simulated disk failure after commit | Failure surfaced; explicit synchronization regenerated pointer from committed metadata |
| Empty-tenant evaluation | Persisted insufficient_data; no constraint violation |

All browser/test users, machines and orders were generated in disposable databases. No demo credentials were used, and no real release was deployed. Runtime pointer preservation was checked separately from artifact hashes.

## Commands executed

```powershell
# Private connection URL loaded into the environment, never printed.
$env:SENTINEL_TEST_ADMIN_URL = (Get-Content .runtime/postgres.env | Where-Object { $_ -like 'DATABASE_URL=*' }) -replace '^DATABASE_URL=',''
.venv/Scripts/python.exe -m pytest -q tests/test_mlops_postgres.py
.venv/Scripts/python.exe -m pytest -q tests/test_phase89_regressions.py
.venv/Scripts/python.exe -m pytest -q
# Recovery after local database became unavailable:
.venv/Scripts/python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
.venv/Scripts/python.exe -m pytest -q tests/test_work_orders_postgres.py::test_assignee_eligibility_and_tenant_boundary

& 'C:\Program Files\nodejs\npm.cmd' --prefix apps/web test
& 'C:\Program Files\nodejs\npm.cmd' --prefix apps/web run typecheck
& 'C:\Program Files\nodejs\npm.cmd' --prefix apps/web run build

# Playwright installed only in ignored runtime storage; Edge was already installed.
.venv/Scripts/python.exe -m pip install --target .runtime/browser-deps playwright
$env:PYTHONPATH = "$PWD\.runtime\browser-deps;$PWD"
.venv/Scripts/python.exe -m pytest -q -s scripts/verify_portal_browser.py
.venv/Scripts/python.exe -m sentinel.mlops.cli --help
```

Evidence logs: `.runtime/phase89-final-backend.txt`, `.runtime/phase89-final-frontend.txt`, `.runtime/phase89-fixed-build.txt`, `.runtime/phase89-browser.txt`, `.runtime/phase89-timeout-recovered.txt`. Sanitized browser screenshot: `.runtime/phase89-browser-monitoring.png`.

## Files changed

- Backend: `sentinel/auth/api.py`, `sentinel/config.py`, `sentinel/api.py`, `sentinel/inference.py`, `sentinel/mlops/api.py`, `sentinel/mlops/deployment.py`, `sentinel/mlops/drift.py`, `sentinel/mlops/evaluation.py`, `sentinel/mlops/cli.py`.
- Frontend: `apps/web/src/App.tsx`, `services/api.ts`, `services/types.ts`, `pages/WorkOrderDetailPage.tsx`, `pages/ModelMonitoringPage.tsx`, `components/work-orders/WorkOrderActionModal.tsx` (the last five paths are within `apps/web/src`).
- Tests: `tests/conftest.py`, `tests/test_mlops_postgres.py`, `tests/test_phase89_regressions.py`, `apps/web/src/__tests__/ApiContracts.test.ts`, `apps/web/src/__tests__/TenantBoundary.test.tsx`, `scripts/verify_portal_browser.py`.
- Contracts: `packages/contracts/experimental.openapi.json`, `reports/openapi.json`.
- Documentation: README, backend/frontend quickstarts, API documentation, implementation-status documents, Phase 8/9 handoffs, release/monitoring guides and this report. Previous review retained as historical evidence with a follow-up link.

## Limits and operational handoff

The implementation remains an experimental local NASA replay system. This correction does not add physical ingestion, workers, external maintenance integrations, production certification or automatic promotion. Browser coverage verifies the corrected workflow, not every portal view or accessibility requirement.

Release management supports one local environment. PostgreSQL and the filesystem are not a shared transaction; post-commit publication failure requires explicit pointer recovery. Legacy deployments without reconstructable audit payload need a new verified release configuration. No migration or model retraining is required. Default CLI monitoring/evaluation targets the verified FD001 baseline; other references require explicit verified service configuration.

Use `docs/MODEL_RELEASE_AND_ROLLBACK.md` for updated startup/recovery behavior. Existing model artifacts, datasets and configured release were preserved. No commits or unrelated parent-repository cleanup were performed.
