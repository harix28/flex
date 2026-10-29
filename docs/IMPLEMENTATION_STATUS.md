## Container hardening update - 2026-10-28

Deployment now requires explicit secrets, a private database network, a separate migration owner/runtime role, health-gated scripts and an HTTPS gateway (with an explicit loopback HTTP demo override). `/health/deployment` checks both model and database revision; existing health endpoints retain their contracts. Model artifacts and migration head `0007_mlops` are unchanged. Docker execution remains blocked on this host; configuration is not a production-readiness claim.

[Deployment setup](../DEPLOYMENT.md) | [Executed validation](../reports/DEPLOYMENT_FIXES_20261028.md)

## Offline RUL comparison update — 2026-10-28

The 54-fit history-window experiment and engine-group uncertainty evaluation are complete; see [../docs/RUL_EXPERIMENTS.md](../docs/RUL_EXPERIMENTS.md). Intervals remain broad and the historical serving model is unchanged. Calibration/audit evidence from that study is now used, not untouched.

A controlled single-row Cap-125 FD001 candidate was subsequently tested on the same engines. On 88 common official-test engines, existing window-model MAE was 12.45 versus 13.58 cycles; near-failure MAE was 4.00 versus 11.03. The candidate failed the validation improvement gate and was not promoted. [Full comparison and limitations](../reports/FD001_CAP125_COMPARISON_20261028.md). These are reused benchmarks, not fresh blind evaluations.


## Four-subset candidate training — 2026-10-27

Trained separate FD001, FD002, FD003 and FD004 candidates in new `runs/fd00X-20261027-candidate` directories. Validation selected XGBoost for FD001/FD003 and Ridge for FD002/FD004. Official-test MAE: 16.14 / 21.87 / 22.07 / 29.98 cycles, respectively; evaluated 100 / 253 / 100 / 237 engines. Seventeen short histories were excluded without padding. All four verified bundles reproduce the saved predictions across 690 eligible engines; 10 parser/feature tests passed.

These are offline experimental candidates, not automatic replacements for the running FD001 model. No deployment, model routing change or dataset modification was performed. Original model artifacts and release/configuration hashes were preserved. Details, caveats and provenance: [training report](../reports/ALL_SUBSETS_TRAINING_20261027.md).

## Current corrective verification — 2026-10-27

Phase 8–9 review corrections are implemented: verified evaluation endpoints, digest-checked activation, recoverable committed release pointers, drift-reference validation, backend error decoding, manager assignee lookup and tenant page-state isolation. Model artifacts are unchanged; schema revision remains `0007_mlops`.

Verification: **246 backend tests passed across the full run and recovery retry** (full run: 245 passed and one database connection-timeout setup error; affected test passed after restoring local PostgreSQL). **30 frontend tests**, TypeScript/build and **one real Edge browser regression** passed. No checks skipped. These current results supersede earlier 242-test claims; they do not represent an uninterrupted green backend run. [Details and remaining limits](../reports/PHASE8_9_FIXES_VALIDATION.md).

# Implementation status and milestone history

Current Phase 9 verification: 242 backend tests passed (121 database-independent, 121 PostgreSQL),
24 frontend Vitest tests passed, TypeScript typecheck clean (0 errors), production build verified,
and live MLOps CLI and REST verification executed. Features immutable model registry, artifact verification,
controlled restart-based release and rollback, inference latency observability, input drift monitoring,
offline ground-truth performance evaluation, and Model & Monitoring portal page.
See [Phase 9 validation](../reports/PHASE9_VALIDATION.md), [MLOps Operations](MLOPS_OPERATIONS.md),
and [Phase 9 handoff](PHASE9_HANDOFF.md). Earlier sections below are historical.

## Phase 1 backend foundation â€” completed 2026-10-25

The existing model/backend is preserved. Added validated environment configuration
(process environment over local .env), private shared local-key initialization,
canonical loopback startup, liveness/readiness, sanitized error/log handling,
bounded ID/cycle fields, verified data/replay commands and synchronized experimental
OpenAPI snapshots. Windows Python 3.12.15: 53 tests passed, one existing TestClient
deprecation warning. Real engine-1 replay: HTTP 200, RUL 136.21971130371094 cycles.
The model and FD001 data checksums match the trusted saved artifacts. No dependency
changes or retraining. See ../reports/PHASE1_VALIDATION.md and ../BACKEND_QUICKSTART.md.

The remaining sections record the original ML milestone; production features below
are still deferred. Phase 2 handoff is database foundation, not dashboard work.

## Original ML milestone

The latest user direction prioritizes ML/backend before dashboard. This overrides the earlier frontend-first attempt. No Lovable code, service or dependency is used here.

Implemented: strict C-MAPSS parser for four subsets, deterministic engine split, shared 30-cycle feature transform, constant/Ridge/XGBoost comparison, frozen candidate selection before test evaluation, native JSON artifact, checksummed model/report manifest, inference API and behaviour tests.

Data split: 70% train / 15% validation / 15% reserved calibration engines, seed 42. RUL calibration and probabilities are deferred, so reserved engines are NOT used. Training samples at most 100 windows/engine with equal total engine weight. Validation uses six fixed equally spaced truncations per engine and reports engine-balanced metrics. This differs from official-test truncation distribution and is a limitation. No claimed confidence intervals.

Features: 24 channels (3 settings + 21 sensors), each with last/mean/population-std/linear-slope = 96 features. IDs, cycles and target labels are not model features. No padding or imputation. XGBoost needs no scaling; Ridge preprocessing fits training data only. Nonnegative clipping is recorded and evaluated. Labels are uncapped cycles.

Model selection metric is validation engine-balanced RMSE. One constant, one Ridge and two predeclared XGBoost candidates are compared. The selected XGBoost is kept as trained on 70 engines; no silent retraining on validation/calibration. The official test was evaluated once after selection. Replaying it through the API is a serialization parity check, not additional model selection.

All runs are experiment-only. JSON report states version, hashes, split IDs, dependencies and measured values. File-level code hashes are included in the package manifest. Raw data and trained model directories are gitignored. The download ZIP contains the model as a downloadable run output, not a Git commit.

Deferred from original docs: production tenant API, registry mappings, durable persistence, events/jobs, security roles, maintenance workflow, MLOps registry/promotions, calibrated horizon classifier, anomaly detector, component diagnosis, condition-specific optimization for FD002/FD004 and live telemetry.

Security boundary: loopback-only local server, explicit env key, finite-value/schema/body bounds and fixed model path supplied by operator. No model-upload endpoint, no untrusted pickle, no public deployment. This is not the final authentication or multitenancy system.


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

## Phase 5 — Persistent replay observations (2026-10-26)

Migration0004_replay adds immutable stream/provenance, batch/idempotency and observation
tables with tenant-aware constraints. Authenticated replay APIs and import CLI are
implemented; source parser and models remain unchanged. History is bounded and sorted,
gaps explicit, observed_at null. No predictions, physical ingestion or dashboard added.
See REPLAY_INGESTION.md for the current contract and PHASE5_HANDOFF.md for next work.

## Phase 6 — Persistent RUL predictions and maintenance priority (2026-10-26)

Migration `0005_predictions` adds `predictions` table, deduplication constraints, immutable trigger,
and extended audit logging. Implemented trailing causal window extraction ($W=30$), exact parity with
verified model `fd001-v1` ($136.21971130371094$ cycles, diff $= 0.00\times 10^0$), SHA-256 input digests,
idempotency, session/CSRF-authenticated endpoints (`POST/GET /api/v1/machines/{id}/predictions`,
`GET .../latest`, `GET /api/v1/predictions/{id}`), and fleet maintenance priority ranking
(`GET /api/v1/maintenance-priorities`) with policy `v1-experimental`. Outdated predictions and unavailable
attempts are visibly distinct. All 195 tests passed. See [PERSISTENT_PREDICTIONS.md](PERSISTENT_PREDICTIONS.md),
[MAINTENANCE_PRIORITY_POLICY.md](MAINTENANCE_PRIORITY_POLICY.md), and [PHASE6_HANDOFF.md](PHASE6_HANDOFF.md).

## Phase 7 — Maintenance Work Orders and Human Approval Workflow (2026-10-26)

Migration `0006_work_orders` adds `work_orders`, `work_order_transitions`, `work_order_assignments`,
`work_order_notes`, `work_order_counters`, `work_order_idempotency`, and audit types. Implemented
prediction-linked and manual draft creation, deterministic human review templates, immutable evidence snapshots,
optimistic concurrency control via integer `version`, database-level active work order deduplication per machine,
role-based state transitions (`draft`, `approved`, `in_progress`, `blocked`, `completed`, `cancelled`),
technician assignment validation, append-only notes/history, and terminal state protection.
Human approval by a plant manager or admin is strictly required before work can start. Model predictions
never automatically approve maintenance or shut down equipment. All 213 tests passed (121 database-independent,
92 PostgreSQL). Real loopback HTTP verification executed against disposable PostgreSQL.
See [MAINTENANCE_WORKFLOW.md](MAINTENANCE_WORKFLOW.md), [PHASE7_VALIDATION.md](../reports/PHASE7_VALIDATION.md),
and [PHASE7_HANDOFF.md](PHASE7_HANDOFF.md).


## Phase 7 corrective follow-up

The four CODEBASE_ASSESSMENT.md findings are corrected: execution permissions are checked
on every action, stale approval is rejected, created/due filters are supported and notes
are versioned. All233 tests passed; real HTTP verification passed. See
[corrective validation](../reports/PHASE7_FIXES_VALIDATION.md). Migration head remains
0006_work_orders; frontend and production hardening remain outside this change.

## Phase 8 — Frontend Portal and Backend Integration (2026-10-26)

Phase 8 implements the complete web frontend portal in `apps/web/` connecting to the local FastAPI backend and PostgreSQL database.
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
See [Frontend Quickstart](../FRONTEND_QUICKSTART.md), [Portal User Guide](PORTAL_USER_GUIDE.md),
[validation report](../reports/PHASE8_VALIDATION.md), and [Phase 8 handoff](PHASE8_HANDOFF.md).

## Phase 9 — MLOps Foundation, Model Registry, Monitoring and Controlled Release (2026-10-26)

Phase 9 establishes the MLOps foundation, lightweight PostgreSQL model registry, artifact verification, controlled release management, inference observability, input drift monitoring, and offline ground-truth evaluation:
- **Lightweight Registry**: Schema migration `0007_mlops.py` added `models`, `model_deployments`, and `ml_monitoring_runs` tables. Tracks immutable model version (`fd001-v1`), model family (`xgboost`), artifact digests, feature schema version (`cmapss-trailing-v1`, 96 features), causal window (30 cycles), supported scope (`FD001`, `cmapss_engine`, `nasa_replay`), training provenance (70 training engines), evaluation metrics, and review status (`experiment_only`).
- **Trust & Verification**: Manifest checks, SHA-256 verification, and safe XGBoost deserialization without arbitrary pickle loading. Rejects tampered artifacts or mismatched trusted digests.
- **Controlled Release & Rollback**: Operator CLI (`python -m sentinel.mlops.cli`) for candidate validation, registration, desired deployment configuration, activation status check, and multi-model rollback. Restart-based activation distinguishes desired release from running active state. Failed boot preserves previous working release.
- **Inference Observability**: Records pure model latency (`inference_ms`) and complete pipeline latency (`pipeline_ms`) on predictions. Tenant-scoped `/observability` endpoint returns latency distribution (min/max/mean/p50/p95), status counts, and unavailable reason breakdown without raw sensor array logging or cross-tenant leakage.
- **Input Feature Drift Monitoring**: Reference profile extracted strictly from the 70 training engines of `split.train` in `train_FD001.txt` (12,377 windows). Constant features (28 features) handled explicitly with zero-variance safeguards. Deduplicates input windows by `input_digest` and enforces 5 unique sample minimum threshold before reporting statistical drift.
- **Offline Ground-Truth Performance Evaluation**: Offline evaluation command joins predictions against verified official test labels (`RUL_FD001.txt`). Implements correct RUL-at-cutoff logic ($\text{RUL}(c) = \text{RUL}_{\text{final}} + (t_{\text{max}} - c)$), MAE, RMSE, signed bias, and overestimation frequency. Separates official test final cutoffs from multi-cutoff trajectories. Refuses work orders as pseudo ground truth. Live fleet accuracy honestly reported as unavailable.
- **Portal Integration**: Added "Model & Monitoring" view (`/model-monitoring`) in `apps/web/` displaying active model version, verified digest, causal window, historical benchmark metrics, latency observability, drift status, ground-truth verification disclaimers, and audit runs history with metric details modal.
- **Testing & Verification**: 6 PostgreSQL integration tests (`tests/test_mlops_postgres.py`) passing; full backend suite 242 tests passing; 24 frontend tests passing; typecheck clean; production Vite build clean; all 4 model artifacts in `runs/fd001-v1` bitwise preserved.
See [MLOps Operations Manual](MLOPS_OPERATIONS.md), [Model Release and Rollback](MODEL_RELEASE_AND_ROLLBACK.md), [Model Monitoring Guide](MODEL_MONITORING.md), [validation report](../reports/PHASE9_VALIDATION.md), and [Phase 9 handoff](PHASE9_HANDOFF.md).

## RUL error analysis — 2026-10-27

Recomputed 1,516 validation/test predictions for current FD001 plus four candidates. Artifact hashes, saved aggregate metrics and engine test predictions verified. Per-engine/per-cutoff outputs identify FD002/FD004 pre-failure overestimation, FD003 outliers and sparse near-failure validation coverage. No training or deployment change. [Analysis and bounded experiment plan](../reports/rul-error-analysis-20261027/REPORT.md).
