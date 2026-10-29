# Phase 6 Validation Report — Persistent RUL Predictions and Maintenance Priority

Date: 2026-10-26  
Status: Passed (100% test pass rate, verified against real HTTP and native PostgreSQL 18)

---

## 1. Executive Summary

Phase 6 implements the complete persistent RUL prediction and maintenance priority API slice within the existing Meridian Sentinel repository:
- **Stored Observations to Predictions**: Contiguous trailing causal windows ($W=30$) extracted from PostgreSQL `replay_observations`.
- **Zero Hallucination / Leakage**: Strict consecutive cycle enforcement, zero interpolation, no future observation or ground-truth RUL label access.
- **Model Verification & Parity**: Inference executed via existing verified bundle `runs/fd001-v1` with zero modification or retraining. Resulting RUL achieved exact byte/float parity with direct model inference ($136.21971130371094$ cycles, diff $= 0.00\times 10^0$).
- **Idempotency & Concurrency**: Input digest computation (SHA-256) and database constraint deduplication preventing duplicate records.
- **Transparent Maintenance Priority**: Rule-based priority evaluation (`v1-experimental`) categorizing engines into `urgent`, `high`, `medium`, `low`, and `unknown` bands with clear explanations and outdated-state detection.
- **Security & Multi-Tenancy**: Session-authenticated (`meridian_session`), CSRF-protected, and strictly scoped by tenant isolation and role permissions (`predictions.read`, `predictions.create`).

---

## 2. Prerequisite Baseline & Phase 5 Verification

Before introducing Phase 6 changes:
1. Audited repository documentation (`PRD.md`, `architecture.md`, `Models.md`, `docs/PHASE5_HANDOFF.md`, `reports/PHASE5_VALIDATION.md`).
2. Confirmed existing Python backend, native PostgreSQL 18 on port 55432, Alembic migration state at `0004_replay`.
3. Executed baseline test suite: 181 passed tests across database-independent and PostgreSQL tests.
4. Executed `python -m sentinel.check` confirming all 3 FD001 dataset files, bundle hash (`d9955867...`), and model hash (`b3e9ed3f...`) matched trusted configuration.
5. Executed `scripts/verify-ingestion-local.py` confirming Phase 5 replay batch ingestion, observation storage (31 cycles), and experimental direct prediction.

---

## 3. Schema & Database Implementation

Migration: `database/migrations/versions/0005_predictions.py` (Revision `0005_predictions`, Down Revision `0004_replay`).

### New Tables & Constraints:
- **`predictions` Table**:
  - `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
  - `tenant_id uuid NOT NULL`, `machine_id uuid NOT NULL`, `stream_id uuid`
  - `actor_id uuid NOT NULL`, `request_id uuid NOT NULL`
  - `status text NOT NULL CHECK (status IN ('available','unavailable'))`
  - `reason text CHECK (reason IS NULL OR reason IN ('no_observations','insufficient_history','gaps_in_history','unsupported_machine','unsupported_subset','unsupported_model','nonfinite_model_output','invalid_stored_input'))`
  - `requested_cutoff_cycle integer NOT NULL`, `observed_cutoff_cycle integer`
  - `input_start_cycle integer`, `input_end_cycle integer`, `input_observation_count integer NOT NULL`
  - `input_digest text NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$')`
  - `model_version text NOT NULL`, `model_digest text NOT NULL`, `bundle_digest text NOT NULL`
  - `inference_version integer NOT NULL DEFAULT 1`, `feature_schema_version integer NOT NULL DEFAULT 1`
  - `rul_cycles double precision`, `failure_probability double precision CHECK (failure_probability IS NULL)`
  - `interval_lower double precision CHECK (interval_lower IS NULL)`, `interval_upper double precision CHECK (interval_upper IS NULL)`
  - `diagnosis_basis text NOT NULL DEFAULT 'unavailable'`, `release_status text NOT NULL DEFAULT 'experiment_only'`
  - `policy_version text NOT NULL DEFAULT 'v1-experimental'`, `priority_band text`
  - `created_at timestamptz NOT NULL DEFAULT clock_timestamp()`
  - Foreign keys to `machines(tenant_id, id)` and `memberships(tenant_id, user_id)`.
  - Composite foreign key to `replay_streams(tenant_id, machine_id, id)`.
- **Deduplication Constraint**:
  `UNIQUE NULLS NOT DISTINCT (tenant_id, machine_id, stream_id, requested_cutoff_cycle, input_digest, model_digest, inference_version)`.
- **Immutability Trigger**: `prevent_prediction_modifications` preventing `UPDATE` or `DELETE` operations on `predictions`.
- **Audit Integration**: Extended `auth_audit_events` action check to include `prediction_requested`, `prediction_completed`, `prediction_failed`, and target type `prediction`.

---

## 4. Test Results

### Test Suite Execution
- **Total Tests Passed**: **195 passed**, **0 failed, 0 skipped**.
- **Execution Time**: ~168s for full suite including disposable PostgreSQL database creations and tear-downs.

### Coverage Breakdown:
1. `tests/test_predictions_postgres.py` (10 integration tests):
   - `test_prediction_from_stored_observations_and_direct_parity`: End-to-end prediction creation, input digest, policy evaluation, exact parity with direct Predictor.
   - `test_cutoff_selection_and_no_future_leakage`: Selection of intermediate cutoffs without leaking later observations or labels.
   - `test_insufficient_history_and_gaps`: Unavailable outcomes when observations $< 30$ or contain gaps.
   - `test_gap_filled_allows_new_successful_prediction`: Ingestion of missing cycle allows a subsequent prediction to become available.
   - `test_unsupported_machine_and_subset`: Physical devices and non-FD001 subsets return controlled unavailable outcomes.
   - `test_concurrency_and_race_safety`: 3 concurrent requests via ThreadPoolExecutor and Barrier yield exactly 1 inserted prediction record and 2 idempotency-replayed responses.
   - `test_tenant_isolation_role_checks_and_csrf`: Cross-tenant denial (404), CSRF rejection (403), viewer creation denial (403), viewer read success (200).
   - `test_latest_prediction_and_outdated_tracking`: Historical predictions do not overwrite newer latest results; advancing observations mark predictions outdated.
   - `test_maintenance_priority_ranking_and_pagination`: 7-tier ranking, tie-breaking, summary counts, and pagination limits.
   - `test_audit_event_written_for_prediction`: Verification of audit trail in `auth_audit_events`.
2. `tests/test_predictions_unit.py` (4 unit tests):
   - `test_priority_policy_threshold_validation`: Validates strictly ascending positive thresholds.
   - `test_priority_policy_evaluation`: Tests boundary evaluations for urgent, high, medium, low, and unknown.
   - `test_input_digest_determinism_and_sensitivity`: Tests SHA-256 reproducibility and sensitivity to ordering and values.
   - `test_prediction_request_schema`: Validates schema bounds ($1 \le \text{cycle} \le 2147483647$).
3. Foundation & OpenAPI Sync:
   - `test_openapi_snapshots_match_factory`: OpenAPI snapshots synchronized with FastAPI router.

---

## 5. Real End-to-End HTTP Verification

Executed via `scripts/verify-predictions-local.py` against disposable PostgreSQL:

### Real HTTP Responses:
```json
{
  "http_statuses": {
    "login_admin_a": 200,
    "register_machine": 201,
    "stored_window": 200,
    "create_prediction": 200,
    "list_predictions": 200,
    "get_latest_prediction": 200,
    "get_prediction_by_id": 200,
    "get_maintenance_priorities": 200,
    "unavailable_insufficient_history": 200,
    "register_phys_machine": 201,
    "unavailable_phys_machine": 200,
    "login_admin_b": 200,
    "cross_tenant_predictions_list": 404,
    "cross_tenant_predictions_post": 404,
    "cross_tenant_predictions_latest": 404,
    "cross_tenant_prediction_detail": 404
  }
}
```

### Direct Inference Parity:
- Persisted Prediction RUL: `136.21971130371094` cycles
- Direct Model Inference RUL: `136.21971130371094` cycles
- Absolute Float Difference: `0.00e+00`

### Model Artifact Integrity:
- Model SHA-256: `b3e9ed3f0319b8095848ad6ce74cb8cc64cfd91adc06647d7cb95eaf57be478f` (Unchanged)
- Bundle SHA-256: `d9955867513db3984fa3a3467ebafdb56f8e0704f11997d7ff05e1d07987f839` (Unchanged)
- All 3 FD001 source files verified; no retraining, overwriting, or weight mutations.

---

## 6. Files Changed and Added

### Added Files:
- `database/migrations/versions/0005_predictions.py`: Incremental migration for `predictions` table, deduplication, immutability trigger, and audit events.
- `sentinel/predictions/__init__.py`: Package entrypoint exporting router and policy.
- `sentinel/predictions/policy.py`: Priority policy domain model, threshold validation, and rule evaluation.
- `sentinel/predictions/schemas.py`: Pydantic request/response schemas.
- `sentinel/predictions/service.py`: Service layer for window extraction, Predictor execution, deduplication, and ranking.
- `sentinel/predictions/api.py`: FastAPI routes with session auth, CSRF, and tenant scoping.
- `tests/test_predictions_unit.py`: Unit tests for policy, hashing, and schemas.
- `tests/test_predictions_postgres.py`: Comprehensive PostgreSQL integration tests.
- `scripts/verify-predictions-local.py`: Real loopback HTTP verification script.
- `docs/PERSISTENT_PREDICTIONS.md`: Full specification of window selection and persistent prediction APIs.
- `docs/MAINTENANCE_PRIORITY_POLICY.md`: Maintenance priority policy specification and thresholds.
- `docs/PHASE6_HANDOFF.md`: Handoff documentation for Phase 7.
- `reports/phase6-http.json`: Sanitized HTTP evidence log.
- `reports/PHASE6_VALIDATION.md`: This validation report.

### Modified Files:
- `sentinel/db/__init__.py`: Updated `REVISION = '0005_predictions'`.
- `sentinel/auth/permissions.py`: Added `predictions.read` and `predictions.create` permissions.
- `sentinel/api.py`: Mounted `predictions_router` into FastAPI application.
- `tests/test_postgres.py`: Included `predictions` in expected tables list.
- `packages/contracts/experimental.openapi.json`: Synchronized OpenAPI specification.
- `reports/openapi.json`: Synchronized OpenAPI specification.
- `README.md`, `BACKEND_QUICKSTART.md`, `IMPLEMENTATION_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`: Updated documentation and implementation status.

---

## 7. Limitations & Remaining Scope

1. **Experimental ML Status**: Model release status remains `experiment_only`. The model applies strictly to NASA C-MAPSS subset FD001 and must not be applied to physical assets or other operational subsets.
2. **Confidence Intervals & Failure Probability**: Not implemented. Confidence intervals and failure probabilities are explicitly `null` until calibrated uncertainty estimation is developed.
3. **No Automatic Inference Workers**: Predictions must be explicitly requested via POST API; no background jobs or continuous inference pipelines are triggered on observation arrival.
4. **No Automated Work Orders**: Work orders, maintenance ticket creation, and notifications remain future scope and are not implemented in Phase 6.

---

## 8. Recommended Next Backend Task

**Phase 7: Maintenance Action Management & Model Release Lifecycle**
1. Implement human-in-the-loop maintenance action approvals based on priority band recommendations.
2. Build model release governance gating production release promotion from `experiment_only`.
3. Provide work order draft generation with explicit technician review requirements.
