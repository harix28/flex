# Meridian Sentinel — MLOps Operations Manual

Version: 1.0 · Updated: 2026-10-26 · Scope: Phase 9 MLOps Foundation

---

## 1. Overview & Trust Philosophy

Meridian Sentinel Phase 9 implements an aerospace-grade, audit-traceable MLOps operational foundation for industrial asset predictive maintenance. 

### Core Tenets
1. **Immutable Artifact Identity**: Models are identified by their immutable filesystem directory and verified SHA-256 digests (`bundle.json`, `model.json`, `report.json`). Large model binaries and feature matrices are **never** duplicated into PostgreSQL.
2. **Explicit Operator Promotion**: Machine learning models are never auto-promoted based on test metrics or pipeline completion. All deployment changes require an explicit operator actor and justification reason.
3. **Controlled Restart-Based Activation**: A release is configured by the operator via the CLI, atomically written to `.runtime/active_release.json`, and activated by restarting the backend daemon (`python -m sentinel.serve`). Desired configuration is strictly separated from active running state.
4. **Tenant Isolation**: Organization admins and viewers have read-only visibility into their tenant's inference telemetry, drift status, and historical offline evaluations. Global model registration, deployment configuration, and rollback remain operator-only.
5. **No Production Flight Dispatch Claims**: All telemetry, monitoring, and prediction outputs are explicitly tagged as simulated turbofan demonstrations (`experiment_only`) and are not certified for production aircraft flight dispatch or unapproved plant overhauls.

---

## 2. Operator CLI Quick Reference

The primary administrative interface is `sentinel.mlops.cli`.

```bash
# Set database connection environment if not in .env
$env:DATABASE_URL = "postgresql+psycopg://meridian_local:<password>@127.0.0.1:55432/meridian_dev"

# Inspect registered models
python -m sentinel.mlops.cli list-models

# Validate candidate model directory against serving contract
python -m sentinel.mlops.cli validate-candidate --model-dir runs/fd001-v1

# Register a verified model bundle with trusted SHA-256 digest
python -m sentinel.mlops.cli register-model --model-dir runs/fd001-v1 --trusted-sha256 06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd --actor "operator:admin" --reason "Phase 9 baseline registration"

# Configure desired model release
python -m sentinel.mlops.cli deploy-model --model-version fd001-v1 --actor "operator:admin" --reason "Phase 9 release configuration"

# Inspect desired vs active release status
python -m sentinel.mlops.cli status

# Inspect release and rollback audit trail
python -m sentinel.mlops.cli list-deployments

# Rollback to previously verified and deployed model
python -m sentinel.mlops.cli rollback-model --target-version fd001-v1 --actor "operator:admin" --reason "Rollback to verified baseline"

# Run offline input feature drift monitoring
python -m sentinel.mlops.cli run-drift-monitoring --tenant-id 26c21516-f3ca-4b43-bc8b-f8067155e4da --min-samples 5

# Run offline ground-truth performance evaluation with verified NASA labels
python -m sentinel.mlops.cli run-evaluation --tenant-id 26c21516-f3ca-4b43-bc8b-f8067155e4da --labels-path data/raw/RUL_FD001.txt
```

---

## 3. Subcommand Specifications

### 3.1 `validate-candidate`
Validates that a local bundle conforms to the Meridian Sentinel serving contract prior to registration:
- Verifies directory contains `bundle.json`, `model.json`, and `report.json`.
- Validates `bundle.json` schema: `version`, `model_type`, `subset`, `window`, `feature_schema`, `features`, `model_sha256`, `report_sha256`.
- Verifies exact match against the canonical 96 trailing causal feature names.
- Computes SHA-256 of `model.json` and `report.json` and asserts exact match against manifest.
- Safely loads `model.json` using `xgboost.XGBRegressor().load_model()` without arbitrary Python `pickle.load`.

### 3.2 `register-model`
Registers the verified metadata into PostgreSQL table `models`:
- Re-registration of an identical bundle digest is idempotent.
- Attempting to overwrite an existing `model_version` with a different bundle digest is rejected (`ConfigurationError`).
- Emits audit record in `auth_audit_events` with `action='model_registered'`.

### 3.3 `deploy-model`
Configures a desired release target in `model_deployments`:
- Verifies model exists in registry and physical artifacts on disk match registered digest.
- Marks previous desired deployment as `superseded`.
- Inserts new record with `action='deploy'`, `status='desired'`.
- Atomically writes release pointer to `.runtime/active_release.json`.
- Emits audit event `model_deployed`.

### 3.4 `rollback-model`
Rolls back to a previously deployed, registered model:
- Verifies target model is registered and was previously deployed in historical deployments.
- Verifies target model is not already the desired deployment.
- Verifies physical artifacts on disk match registered target digest.
- Sets target release in `.runtime/active_release.json` with `action='rollback'`.
- Inserts deployment record with `action='rollback'`, `status='desired'`.
- Emits audit event `model_rollback`.

### 3.5 `status`
Inspects desired release configuration versus the running server process:
- `Overall Deployment State`: `active`, `pending_restart`, `desired_not_running`, `active_untracked`, or `unconfigured`.
- `Running Model Version`: Version reported by running predictor or CLI context.
- `Desired Release`: Target version, action, actor, timestamp.
- `Active Release`: Activated version and activation timestamp.

---

## 4. Tenant-Scoped REST Endpoints

All tenant REST endpoints require session authentication with `predictions.read` permission. Cross-tenant access is rejected with `404 Not Found` (anti-enumeration) or `403 Forbidden`.

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/organizations/{org_id}/ml/model-info` | GET | Active serving model identity, feature schema, causal window, verified SHA-256, frozen validation benchmark metrics. |
| `/api/v1/organizations/{org_id}/ml/observability` | GET | Operational telemetry: total/available/unavailable counts, unavailable reason breakdown, pure inference latency distribution (`inference_ms`) vs complete pipeline latency (`pipeline_ms`), outdated count. |
| `/api/v1/organizations/{org_id}/ml/monitoring` | GET | Paginated list of recorded drift and ground-truth evaluation runs. |
| `/api/v1/organizations/{org_id}/ml/monitoring/{run_id}` | GET | Detailed diagnostic run payload with per-feature statistical shifts or label join metrics. |

---

## 5. Security & Audit Trail

All administrative and operational actions generate structured audit entries in `auth_audit_events`:
- Actions: `model_registered`, `model_deployed`, `model_activated`, `model_rollback`, `model_monitoring_run`.
- Metadata: `actor` (CLI operator identity or user UUID), `target_type='model'` or `'monitoring_run'`, `target_id`, `request_id`, and structured `details` JSONB payload.
- No secrets, credentials, or raw sensor observation arrays are logged into audit events or application server logs.
