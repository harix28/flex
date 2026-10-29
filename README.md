## Container hardening update - 2026-10-28

Deployment now requires explicit secrets, a private database network, a separate migration owner/runtime role, health-gated scripts and an HTTPS gateway (with an explicit loopback HTTP demo override). `/health/deployment` checks both model and database revision; existing health endpoints retain their contracts. Model artifacts and migration head `0007_mlops` are unchanged. Docker execution remains blocked on this host; configuration is not a production-readiness claim.

[Deployment setup](DEPLOYMENT.md) | [Executed validation](reports/DEPLOYMENT_FIXES_20261028.md)

# Meridian Sentinel — full architecture folder structure

This is a complete organized project scaffold **with the working first ML/backend milestone included**. Full folder coverage does not mean every module is implemented. Every planned module has a README stating its status and responsibility.

## Start here

1. `FOLDER_STRUCTURE.md`: complete directory map and status guide.
2. `BACKEND_QUICKSTART.md`: tested model/backend commands and Windows setup.
3. `ARCHITECTURE_OVERVIEW.md`: flows and module boundaries.
4. `IMPLEMENTATION_STATUS.md`: implemented vs pending.
5. `docs/blueprint/readme.md`: original detailed specification and 15 offline flowcharts (`docs/blueprint/Flowcharts.html`).

The root `sentinel/` package remains the tested implementation. Architecture folders wrap or refer to it; there are no duplicate feature pipelines. Run commands from this repository root.

## Implemented now

NASA downloader/parser; causal sensor features; disjoint engine partitions; constant/Ridge/XGBoost comparison; trained FD001 RUL artifact; evaluation report; hash-checked loading; experimental local FastAPI; verified PostgreSQL foundation and backend-only application authentication. Real test metrics: MAE 16.79 cycles, RMSE 21.61 cycles on 100 official test engines. These are simulation results, not plant validation.

Phase 1 adds validated local configuration, private shared API-key setup, safe
request logging/errors, liveness/readiness, and Windows startup/replay scripts.
Run `scripts/start-local.ps1`, keep its terminal open, then run
`scripts/check-local.ps1` in a second terminal. See BACKEND_QUICKSTART.md and
reports/PHASE1_VALIDATION.md for current setup and executed evidence.

## Pending

Frontend, production identity hardening, physical ingestion/outbox, workers, horizon classifier/calibration, MCP, integrations, MLflow/promotions/monitoring and deployment infrastructure. Their folders contain responsibility notes, not fake implementations.

## Quick verification

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m ml.training.train --help
```

See BACKEND_QUICKSTART.md to serve the included model. No public deployment or frontend install is needed. Raw NASA files are excluded; download command creates them. Model run outputs included for local use remain gitignored. Secrets and virtual environments are excluded.


Phase 3 adds Argon2id local login, hashed opaque sessions, CSRF, current organization
membership authorization, last-admin protection and minimal security audits. It is
backend-only and not production-ready. Begin with [authentication setup](docs/AUTHENTICATION.md),
[role permissions](docs/ROLE_PERMISSIONS.md) and [executed validation](reports/PHASE3_VALIDATION.md).
The experimental replay API key remains a separate interface with no tenant privilege.


Phase 4 adds the authenticated machine/sensor registry and installation history, including
logical NASA replay registration. See [registry guide](docs/MACHINE_SENSOR_REGISTRY.md)
and [executed validation](reports/PHASE4_VALIDATION.md). Registering an asset does not
mark it healthy, connect hardware or ingest telemetry. Phase 5 now persists replay observations; see [replay ingestion](docs/REPLAY_INGESTION.md).

Phase 5 adds immutable versioned NASA streams, atomic idempotent batches, bounded history
and data-quality APIs, and an authenticated local import CLI. No predictions are stored.
See [executed validation](reports/PHASE5_VALIDATION.md) and [Phase 6 handoff](docs/PHASE5_HANDOFF.md).

Phase 6 adds persistent RUL predictions and maintenance priority APIs. Stored observations
are extracted into causal 30-cycle trailing windows, evaluated against the verified `fd001-v1`
bundle, deduplicated via input digest and database constraints, and ranked via configurable
priority policy `v1-experimental` (`urgent`/`high`/`medium`/`low`/`unknown`).
See [persistent predictions](docs/PERSISTENT_PREDICTIONS.md), [maintenance priority policy](docs/MAINTENANCE_PRIORITY_POLICY.md),
[executed validation](reports/PHASE6_VALIDATION.md), and [Phase 7 handoff](docs/PHASE6_HANDOFF.md).

Phase 7 adds maintenance work order lifecycle management and human approval workflows.
Drafts can be created manually or linked to persistent predictions with an immutable evidence
snapshot (discrete RUL cycles, cutoff cycle, model digest, priority band) and deterministic review
templates. Implements database-level deduplication per machine, optimistic concurrency control (OCC),
role-based transitions (`draft`, `approved`, `in_progress`, `blocked`, `completed`, `cancelled`),
technician assignments, and append-only notes/history. Human approval is strictly required before work starts.
Model predictions never auto-approve work orders or shut down machines.
See [maintenance workflow](docs/MAINTENANCE_WORKFLOW.md), [executed validation](reports/PHASE7_VALIDATION.md),
and [Phase 8 handoff](docs/PHASE7_HANDOFF.md).


Phase 7 follow-up corrects execution permissions, rejects outdated-evidence approval,
adds created/due range filters and makes notes versioned. See
[validation](reports/PHASE7_FIXES_VALIDATION.md) and [client contract](docs/MAINTENANCE_WORKFLOW.md).

Phase 8 adds the user-facing web portal in `apps/web/` connecting directly to the local FastAPI backend and PostgreSQL database.
Built with React 18, TypeScript, and Vite. Features a restrained industrial design system, HttpOnly session authentication with in-memory CSRF hydration, ranked fleet overview with maintenance priority bands, interactive SVG sensor trend charts with telemetry gap preservation, numeric table view toggle, causal RUL inference execution, draft work order creation from prediction evidence, manager approval workflows, technician assignments, optimistic concurrency control (OCC) state transitions, and append-only versioned notes and audit timelines.
See [Frontend Quickstart](FRONTEND_QUICKSTART.md), [Portal User Guide](docs/PORTAL_USER_GUIDE.md), [executed validation](reports/PHASE8_VALIDATION.md), and [Phase 8 handoff](docs/PHASE8_HANDOFF.md).

Phase 9 adds the MLOps operational foundation, immutable model registry, inference observability, controlled release management, input feature drift monitoring, and offline ground-truth evaluation.
Features include a lightweight PostgreSQL registry (`models`, `model_deployments`, `ml_monitoring_runs`), strict artifact hash verification, operator-only release and rollback CLI (`python -m sentinel.mlops.cli`), atomic release pointers with restart-based activation, pure model latency tracking (`inference_ms` vs `pipeline_ms`), input drift detection against a versioned baseline strictly derived from the 70 training engines of `split.train` (12,377 windows, 28 constant features handled explicitly), offline ground-truth evaluation with verified NASA test labels (`RUL_FD001.txt`), tenant-scoped REST APIs under `/api/v1/organizations/{id}/ml/...`, and a dedicated "Model & Monitoring" portal page.
See [MLOps Operations Manual](docs/MLOPS_OPERATIONS.md), [Model Release and Rollback](docs/MODEL_RELEASE_AND_ROLLBACK.md), [Model Monitoring Guide](docs/MODEL_MONITORING.md), [executed validation](reports/PHASE9_VALIDATION.md), and [Phase 9 handoff](docs/PHASE9_HANDOFF.md).

### Phase 8–9 corrective follow-up

See [release and recovery rules](docs/MODEL_RELEASE_AND_ROLLBACK.md) and [validation report](reports/PHASE8_9_FIXES_VALIDATION.md). Evaluation now uses complete verified trajectory endpoints; drift cache reuse verifies provenance; activation checks artifact identity. The portal decodes backend conflicts, supports manager technician lookup and clears page state on tenant switches. No model retraining or artifact replacement is required.
