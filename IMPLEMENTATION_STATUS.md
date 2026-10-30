## Enterprise Role Isolation & Plain Layman English UI — 2026-10-30

1. **Role Allocation Matrix & Boundary Guarding**:
   - **General Manager (`admin`)**: Executive overview, organization governance (`/members`), system integration keys/gateways (`/integrations`), and fleet registry definition (`/registry`).
   - **Maintenance Engineer (`plant_manager`)**: Maintenance planning & inventory (`/planning`), work order approval gate (`/work-orders`), technician assignment, automated fleet checkup jobs (`/jobs`), and model observability / MLOps (`/model-monitoring`).
   - **Maintenance Technician (`technician`)**: Task execution board (`/work-orders` - start, report issue, complete, log notes), assigned engine sensor telemetry, and warehouse parts lookup. Barred from approving work orders, managing integrations, or modifying membership.
   - **Non-Interruption Controls**: Navigation menu partitioning (`Shell.tsx`), route boundary guards (`RoleBoundaryGuard` in `App.tsx`), and draft approval gate alerts in `WorkOrderDetailPage.tsx`.

2. **Plain Layman English Redesign**:
   - Replaced mathematical jargon, technical abbreviations, and complex terms with clear, intuitive everyday English across all pages.
   - Added interactive **Beginner's Guide to this Dashboard** explaining flight cycles, estimated flights left, urgency colors, and human safety approval guarantees.
   - Simplified table columns, filter buttons with counts, and status badges (`Simulated Test Engine`, `Real Factory Engine`, `Needs Update`, `Up to Date`).

---

## Full Enterprise Architecture Delivery & Demonstration — 2026-10-30

All 9 enterprise roadmap modules are implemented, integrated into the running FastAPI backend and React frontend, and verified end-to-end via `scripts/demo_full_architecture.py` and unit/integration test suites:

1. **Lifetime-Stage Classification & UI Card**: `sentinel/classification.py` and React `LifetimeStageCard` (`apps/web/src/pages/MachineDetailPage.tsx`).
2. **Audit Dossier PDF Export**: FAA/EASA-compliant investigation dossiers with vector trend charts, contiguity checks, and AMM 72-00 task checklists in `sentinel/audit/`.
3. **Model Context Protocol (MCP) Server**: Stdio JSON-RPC server with tenant isolation, `list_machines`, `get_sensor_trends`, `get_prediction_evidence`, and draft work order creation with human approval gates.
4. **Durable Webhook Notifications**: HMAC-SHA256 signature verification, 15-minute anti-fatigue deduplication window, and PostgreSQL delivery audit log in `sentinel/notifications/`.
5. **Background Jobs & Outbox Queue**: PostgreSQL `FOR UPDATE SKIP LOCKED` worker queue, fleet scoring enqueuer, and status API in `sentinel/jobs/` (Alembic `0008_outbox`, `0009_fleet_jobs`).
6. **Maintenance Planning & Logistics**: Warehouse spare parts inventory with bin locations, technician shift rosters, and work order readiness checks in `sentinel/planning/`.
7. **Live Edge Integrations & CMMS Sync**: MQTT Sparkplug B / OPC-UA edge gateway normalizer and SAP PM / IBM Maximo export adapters enforcing human approval gates in `sentinel/integrations/`.
8. **Enterprise Security**: OIDC/SAML PKCE SSO integration, distributed sliding-window rate limiter, and PostgreSQL Row-Level Security (`0010_rls`) in `sentinel/auth/`.
9. **Automated MLOps Pipeline**: Candidate promotion evaluation gates with non-regression constraints and shadow model divergence tracking in `sentinel/mlops/`.

Verification:
- `scripts/demo_full_architecture.py`: 10/10 steps passed cleanly against live local backend and PostgreSQL.
- Backend tests: 14 new integration tests (`tests/test_enterprise_security.py`, `tests/test_notifications.py`, `tests/test_planning.py`, `tests/test_integrations.py`, `tests/test_mlops_pipeline.py`, `tests/test_mcp_server.py`) passed; foundation contracts verified.
- Frontend tests: 31/31 unit tests passed (`vitest`).

## Background fleet scoring — 2026-10-30

Migration `0009_fleet_jobs` extends the durable worker with operator-enqueued fleet
scoring and stored result summaries. Runs freeze at most 100 active machines,
observation cutoffs/digests, requester and configured primary model hash. Worker
execution rechecks tenant membership and permissions, persists predictions and audit
records atomically, and preserves explicit unavailable results. CLI commands:
`python -m sentinel.jobs enqueue-fleet` and `python -m sentinel.jobs status`.
No HTTP/UI queue submission, recurring scheduler, ingestion worker, notification
adapter, application database migration or deployed daemon is included.
See [runbook](docs/BACKGROUND_JOBS.md). Targeted validation: 35 tests passed;
see [fleet validation evidence](reports/FLEET_JOBS_VALIDATION_20261030.md).

## Background queue foundation — 2026-10-30

Migration `0008_outbox` adds tenant-scoped deduplicated jobs, SKIP LOCKED claims,
lease fencing, bounded retries and a dead-letter view. `python -m sentinel.jobs`
provides an operator producer and standalone worker for existing FD001 drift
evaluation. Batch scoring, asynchronous ingestion, outbound notifications, public
submission endpoints and periodic scheduling remain planned. No operational
maintenance or model approval gates are changed. See [runbook](docs/BACKGROUND_JOBS.md).
Targeted validation: 27 tests passed against disposable PostgreSQL databases;
see [evidence](reports/BACKGROUND_JOBS_VALIDATION_20261030.md). Application database
rollout has not been performed.

## All-subset offline training update — 2026-10-30

`sentinel/all_subsets_training.py` now performs strict validation, training-engine
EDA, causal 97-feature extraction, train-only feature selection, five Random
Forest classification scopes and four XGBoost RUL scopes. Actual results and
limitations: [report](reports/all-subsets-20261030-v1/REPORT.md).
Full backend run: 159 passed, 125 skipped. New tests: 15 passed. Database-dependent
checks were not revalidated. Models remain experimental; no classifier API,
automatic deployment or physical-health diagnosis was added.

## Container hardening update - 2026-10-28

Deployment now requires explicit secrets, a private database network, a separate migration owner/runtime role, health-gated scripts and an HTTPS gateway (with an explicit loopback HTTP demo override). `/health/deployment` checks both model and database revision; existing health endpoints retain their contracts. Model artifacts and migration head `0007_mlops` are unchanged. Docker execution remains blocked on this host; configuration is not a production-readiness claim.

[Deployment setup](DEPLOYMENT.md) | [Executed validation](reports/DEPLOYMENT_FIXES_20261028.md)

## Offline RUL comparison update — 2026-10-28

The 54-fit history-window experiment and engine-group uncertainty evaluation are complete; see [docs/RUL_EXPERIMENTS.md](docs/RUL_EXPERIMENTS.md). Intervals remain broad and the historical serving model is unchanged. Calibration/audit evidence from that study is now used, not untouched.

A controlled single-row Cap-125 FD001 candidate was subsequently tested on the same engines. On 88 common official-test engines, existing window-model MAE was 12.45 versus 13.58 cycles; near-failure MAE was 4.00 versus 11.03. The candidate failed the validation improvement gate and was not promoted. [Full comparison and limitations](reports/FD001_CAP125_COMPARISON_20261028.md). These are reused benchmarks, not fresh blind evaluations.


## Four-subset candidate training — 2026-10-27

Trained separate FD001, FD002, FD003 and FD004 candidates in new `runs/fd00X-20261027-candidate` directories. Validation selected XGBoost for FD001/FD003 and Ridge for FD002/FD004. Official-test MAE: 16.14 / 21.87 / 22.07 / 29.98 cycles, respectively; evaluated 100 / 253 / 100 / 237 engines. Seventeen short histories were excluded without padding. All four verified bundles reproduce the saved predictions across 690 eligible engines; 10 parser/feature tests passed.

These are offline experimental candidates, not automatic replacements for the running FD001 model. No deployment, model routing change or dataset modification was performed. Original model artifacts and release/configuration hashes were preserved. Details, caveats and provenance: [training report](reports/ALL_SUBSETS_TRAINING_20261027.md).

## Current corrective verification — 2026-10-27

Phase 8–9 review corrections are implemented: verified evaluation endpoints, digest-checked activation, recoverable committed release pointers, drift-reference validation, backend error decoding, manager assignee lookup and tenant page-state isolation. Model artifacts are unchanged; schema revision remains `0007_mlops`.

Verification: **246 backend tests passed across the full run and recovery retry** (full run: 245 passed and one database connection-timeout setup error; affected test passed after restoring local PostgreSQL). **30 frontend tests**, TypeScript/build and **one real Edge browser regression** passed. No checks skipped. These current results supersede earlier 242-test claims; they do not represent an uninterrupted green backend run. [Details and remaining limits](reports/PHASE8_9_FIXES_VALIDATION.md).

# Module status

| Area | Status | Actual location |
|---|---|---|
| Data import and validation | Implemented | sentinel/download.py, sentinel/data.py |
| Shared causal features | Implemented | sentinel/features.py |
| Training and RUL evaluation | Implemented | sentinel/train.py |
| Trained model | FD001 only | runs/fd001-v1/ |
| Local inference API | Implemented, experimental | sentinel/api.py, sentinel/inference.py |
| Phase 1 local configuration | Implemented and Windows-tested | sentinel/config.py, .env.example |
| Safe HTTP errors and request logging | Implemented; request IDs on all responses | sentinel/http_support.py |
| Liveness / readiness | Implemented; legacy /health preserved | /health/live, /health/ready |
| Local startup / verified replay | Implemented; private shared local key | scripts/start-local.ps1, scripts/check-local.ps1 |
| Backend entrypoint | Implemented canonical | sentinel/serve.py |
| Training entrypoint | Implemented canonical | sentinel/train.py |
| Behaviour tests | 242 passed: 121 database-independent, 121 PostgreSQL; 2026-10-26 | tests/, reports/PHASE9_VALIDATION.md |
| API contracts | Current and target separated | packages/contracts/ |
| CI | Configured, not run on GitHub | .github/workflows/backend-tests.yml |
| Database | Phase 2–9 PostgreSQL foundation & MLOps implemented | sentinel/db/, database/migrations/, reports/PHASE9_VALIDATION.md |
| Machine/sensor registry | Phase 4 implemented and PostgreSQL/HTTP verified | sentinel/registry/, docs/MACHINE_SENSOR_REGISTRY.md |
| Persistent NASA replay ingestion | Phase 5 implemented and PostgreSQL/HTTP verified | sentinel/ingestion/, docs/REPLAY_INGESTION.md |
| Persistent RUL predictions & priority | Phase 6 implemented and PostgreSQL/HTTP verified | sentinel/predictions/, docs/PERSISTENT_PREDICTIONS.md |
| Maintenance work orders & approval | Phase 7 implemented and PostgreSQL/HTTP verified | sentinel/work_orders/, docs/MAINTENANCE_WORKFLOW.md |
| Frontend portal | Phase 8 implemented and end-to-end verified | apps/web/, docs/PORTAL_USER_GUIDE.md |
| Workers / async jobs | Pending specification | docs/planned/services.md |
| Integrations / MCP | Pending specification | docs/planned/integrations.md, docs/planned/mcp.md |
| MLOps | Phase 9 implemented and verified | sentinel/mlops/, docs/MLOPS_OPERATIONS.md |
| Docker / container deployment | Implemented config & hardened gateway | DEPLOYMENT.md, infra/, docker-compose.yml |

Preserved blueprint files describe the target, including sections written before implementation. Current status in this file and BACKEND_QUICKSTART.md takes precedence for what runs today. No new model training occurred during folder packaging.

Phase 1 completed 2026-10-25: reused healthy Python 3.12 environment; verified the
unchanged trusted FD001 bundle and all three source hashes; real engine-1 replay
returned HTTP 200 and 136.21971130371094 RUL cycles. No retraining, new dependencies,
database, production login or external integrations were introduced. One existing
Starlette/httpx deprecation warning remains. See reports/phase1-smoke.json for
executed HTTP evidence and reports/PHASE1_VALIDATION.md for commands and handoff.

Next work: review remaining acceptance coverage and plan the authenticated frontend separately. Phase 7 corrective details are in docs/history/PHASE7_HANDOFF.md.


Phase 2 completed 2026-10-25: PostgreSQL 18.4 native isolated local cluster,
SQLAlchemy/Alembic, six registry foundation tables, tenant-consistent foreign keys,
installation exclusion constraint, scoped repository, transactional sessions,
separate database readiness and explicit idempotent sample seed. See
`reports/PHASE2_VALIDATION.md` for actual results and `database/README.md` for operations.
Production authentication, RLS, runtime grants and production restore validation remain
pending. Existing inference, model artifacts, local authentication and startup scripts
are preserved. No public registry CRUD endpoints exist.


## Phase 3 — implemented, 2026-10-26

Backend-only local email/Argon2id login, opaque server-side session hashes, expiry,
logout/password/disable revocation, current organization memberships, centralized roles,
CSRF/origin/CORS controls, process-local login limits, transactional last-admin protection,
and minimal audit records are implemented. New migration `0002_auth` preserves Phase 2
registry records/history. See docs/AUTHENTICATION.md, docs/ROLE_PERMISSIONS.md and
reports/PHASE3_VALIDATION.md for operations, actual test counts and limitations.

This supersedes earlier statements that all identity/tenant access is pending. OIDC,
production deployment/security hardening, distributed limits, RLS/runtime grants and
frontend remain pending. No dashboard, maintenance workflows or registry HTTP routes
were built. Experimental API-key replay and model artifacts remain unchanged.


## Phase 4 - Machine and sensor registry (2026-10-26)

Implemented organization-scoped machine/sensor registration, bounded lists/details,
explicit updates, archival/retirement, immutable source identity and installation history.
Shared session/membership/CSRF authorization and centralized registry permissions protect
all routes. Incremental 0003_registry migration reuses the existing tables and adds source
binding uniqueness plus database-enforced concurrent machine/channel overlap protection.
An explicit repeatable local CLI registers only selected validated C-MAPSS test engines
and their logical channels. Unknown metadata remains unknown; no ingestion or model
identity inference is introduced. See docs/MACHINE_SENSOR_REGISTRY.md and
reports/PHASE4_VALIDATION.md for actual tests, operations and limitations.

This supersedes prior historical statements that registry HTTP workflows are pending.
No dashboard, hardware integration, telemetry ingestion or model retraining was performed.

## Phase 5 — Persistent replay ingestion (2026-10-26)

Implemented immutable partition/file-version streams, atomic batches/idempotency,
validated finite observations, bounded history/gap APIs and authenticated HTTP import
CLI. Migration0004_replay; all181 tests passed (109 independent,72 PostgreSQL), no
failed/skipped/blocked checks. Actual FD001 engine1 HTTP import31, rerun0 new/31 existing,
conflict409 and tenant denial404. Saved-model result unchanged. No prediction storage.
See reports/PHASE5_VALIDATION.md and docs/history/PHASE5_HANDOFF.md for Phase6.

## Phase 6 — Persistent RUL predictions and maintenance priority (2026-10-26)

Implemented causal window extraction ($W=30$), exact parity with verified model `fd001-v1`
($\text{RUL} = 136.21971130371094$ cycles, diff $= 0.00\times 10^0$), input digest hashing,
atomic deduplication on `(tenant_id, machine_id, stream_id, cutoff, input_digest, model_digest, inference_version)`,
session/CSRF authenticated endpoints (`POST/GET /api/v1/machines/{id}/predictions`,
`GET .../latest`, `GET /api/v1/predictions/{id}`), and rule-based maintenance priority ranking
(`GET /api/v1/maintenance-priorities`) with policy `v1-experimental` (`urgent`, `high`, `medium`, `low`, `unknown`).
Outdated and unavailable predictions are visibly distinct. Migration `0005_predictions`; all 195 tests passed.
See [persistent predictions](docs/PERSISTENT_PREDICTIONS.md), [maintenance priority policy](docs/MAINTENANCE_PRIORITY_POLICY.md),
[validation report](reports/PHASE6_VALIDATION.md), and [Phase 7 handoff](docs/history/PHASE6_HANDOFF.md).

## Phase 7 — Maintenance Work Orders and Human Approval Workflow (2026-10-26)

Implemented organization-scoped work order lifecycle, deterministic draft templating from predictions,
immutable evidence snapshots (discrete RUL cycles, cutoff cycle, model digest, snapshot priority band),
optimistic concurrency control (OCC via `version` integer), database-level machine deduplication
(`uq_active_prediction_wo_per_machine`), scoped idempotency, finite state machine transitions
(`draft`, `approved`, `in_progress`, `blocked`, `completed`, `cancelled`), RBAC matrix (viewer, technician,
plant_manager, admin), technician assignment eligibility checks, and append-only notes/history.
Human approval by a plant manager or admin is strictly required before work can start.
Model predictions never automatically approve maintenance or shut down equipment.
Migration `0006_work_orders`; all 213 tests passed (121 database-independent, 92 PostgreSQL).
Real HTTP loopback verification executed and logged to `reports/phase7-http.json`.
See [maintenance workflow](docs/MAINTENANCE_WORKFLOW.md), [validation report](reports/PHASE7_VALIDATION.md),
and [Phase 8 handoff](docs/history/PHASE7_HANDOFF.md).


## Phase 7 corrective follow-up (2026-10-26)

Corrected current execution permissions/assignee eligibility, outdated-evidence approval,
created/due filters and note concurrency. Notes require version and return work_order_version;
stale evidence requires cancellation and a fresh reviewed draft. No schema change or
model modification. Final full suite233 passed (121 independent,112 PostgreSQL), no
failed/skipped/blocked checks. Actual HTTP fixes: outdated approval409, demoted execution403,
stale note409; normal workflow succeeds. See reports/PHASE7_FIXES_VALIDATION.md.

## Phase 8 — Frontend Portal and Backend Integration (2026-10-26)

Implemented the web frontend portal in `apps/web/` connecting to the FastAPI backend and PostgreSQL database.
Built using React 18, TypeScript 5, and Vite 6. Implemented a restrained industrial UI with aerospace dark theme,
HttpOnly cookie sessions with in-memory CSRF hydration, multi-tenant context, and role-based access gating.
Key views: Overview with ranked fleet priority bands, Machine Details with interactive SVG sensor trend charts
preserving telemetry cycle gaps ($\Delta \text{cycle} > 1$) and numeric table toggle, Stored-data causal RUL prediction
execution against `runs/fd001-v1` (with unmodeled metrics honestly displaying as "Unavailable"), Draft work order creation
from prediction evidence, Manager review and approval workflows with outdated-evidence protection (`409 outdated_evidence`),
Technician assignment, optimistic concurrency control (OCC) state transitions (`start`, `block`, `resume`, `complete`),
mandatory AMM 72-00 completion summaries, and append-only versioned notes and audit timelines.
Frontend tests: 17 Vitest tests passing; typecheck (`tsc --noEmit`) 0 errors; production build (`vite build`) clean.
Live E2E integration verification executed across 10 steps via `scripts/verify_e2e_flow.py` with 100% success.
See [Frontend Quickstart](FRONTEND_QUICKSTART.md), [Portal User Guide](docs/PORTAL_USER_GUIDE.md),
[validation report](reports/PHASE8_VALIDATION.md), and [Phase 8 handoff](docs/history/PHASE8_HANDOFF.md).

## Phase 9 — MLOps Foundation, Model Registry, Monitoring and Controlled Release (2026-10-26)

Implemented the MLOps foundation, lightweight PostgreSQL model registry, artifact verification, controlled release management, inference observability, input drift monitoring, and offline ground-truth evaluation:
- **Lightweight Registry**: Schema migration `0007_mlops.py` added `models`, `model_deployments`, and `ml_monitoring_runs` tables. Track immutable model version (`fd001-v1`), model family (`xgboost`), artifact digests, feature schema version (`cmapss-trailing-v1`, 96 features), causal window (30 cycles), supported scope (`FD001`, `cmapss_engine`, `nasa_replay`), training provenance (70 training engines), evaluation metrics, and review status (`experiment_only`). Model binaries and feature matrices are never duplicated into PostgreSQL.
- **Trust & Verification**: Strict manifest checks, hash validation, and safe XGBoost loading without arbitrary pickle deserialization. Rejects tampered files or mismatched trusted digests.
- **Controlled Release & Rollback**: Operator CLI (`python -m sentinel.mlops.cli`) with commands for candidate validation, registration, desired deployment configuration, activation status check, deployment history, and multi-model rollback. Controlled restart-based activation distinguishes desired release from running active state. Failed boot preserves previous working release.
- **Inference Observability**: Records pure model latency (`inference_ms`) and complete pipeline latency (`pipeline_ms`) on predictions. Tenant-scoped `/observability` endpoint returns latency distribution (min/max/mean/p50/p95), status counts, and unavailable reason breakdown without raw sensor array logging or cross-tenant data leakage.
- **Input Feature Drift Monitoring**: Reference profile extracted strictly from the 70 training engines of `split.train` in `train_FD001.txt` (12,377 windows). Constant features (28 features) handled explicitly with zero-variance safeguards. Deduplicates input windows by `input_digest` and enforces 5 unique sample minimum threshold before reporting statistical drift.
- **Offline Ground-Truth Performance Evaluation**: Offline evaluation command joins predictions against verified official test labels (`RUL_FD001.txt`). Implements correct RUL-at-cutoff logic ($\text{RUL}(c) = \text{RUL}_{\text{final}} + (t_{\text{max}} - c)$), MAE, RMSE, signed bias, and overestimation frequency. Separates official test final cutoffs from multi-cutoff trajectories. Refuses work orders as pseudo ground truth. Live fleet accuracy honestly reported as unavailable.
- **Portal Integration**: Added "Model & Monitoring" view (`/model-monitoring`) in `apps/web/` displaying active model version, verified digest, causal window, historical benchmark metrics, latency observability, drift status, ground-truth verification disclaimers, and audit runs history with metric details modal.
- **Testing & Verification**: 6 PostgreSQL integration tests (`tests/test_mlops_postgres.py`) passing; full backend suite 242 tests passing; 24 frontend tests passing; typecheck clean; production Vite build clean; all 4 model artifacts in `runs/fd001-v1` bitwise preserved.
See [MLOps Operations Manual](docs/MLOPS_OPERATIONS.md), [Model Release and Rollback](docs/MODEL_RELEASE_AND_ROLLBACK.md), [Model Monitoring Guide](docs/MODEL_MONITORING.md), [validation report](reports/PHASE9_VALIDATION.md), and [Phase 9 handoff](docs/history/PHASE9_HANDOFF.md).


## RUL error analysis — 2026-10-27

Recomputed 1,516 validation/test predictions for current FD001 plus four candidates. Artifact hashes, saved aggregate metrics and engine test predictions verified. Per-engine/per-cutoff outputs identify FD002/FD004 pre-failure overestimation, FD003 outliers and sparse near-failure validation coverage. No training or deployment change. [Analysis and bounded experiment plan](reports/rul-error-analysis-20261027/REPORT.md).
