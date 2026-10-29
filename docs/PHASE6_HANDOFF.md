# Phase 6 Handoff: Persistent Predictions and Maintenance Priority

Version: 1.0 · Updated: 2026-10-26 · Target Audience: Phase 7 Engineering

## Implemented Boundaries

Phase 6 implements persistent RUL prediction and maintenance priority APIs on top of Phase 5 observation storage.

- **Current Migration Head**: `0005_predictions`, down revision `0004_replay`.
- **Database Schema**: `database/migrations/versions/0005_predictions.py`.
- **Core Table**: `predictions` (immutable via trigger `prevent_prediction_modifications`).
- **Audit Table**: `auth_audit_events` extended with actions `prediction_requested`, `prediction_completed`, `prediction_failed`, and target type `prediction`.
- **Active Code**: `sentinel/predictions/` package.
- **Model Bundle**: `runs/fd001-v1` (unmodified, verified against manifest).

---

## Key Contracts and Invariants

### 1. Ingestion vs Prediction Boundary
- Ingestion (`POST /api/v1/.../replay-batches`) only writes to `replay_observations`. It **never** triggers inference or creates predictions.
- Predictions (`POST /api/v1/machines/{id}/predictions`) are requested **explicitly** by authorized callers.
- Prediction GET endpoints (`GET .../predictions`, `GET .../predictions/latest`, `GET /api/v1/maintenance-priorities`) read existing persisted records and **never** silently run inference.

### 2. Causal Window Integrity
- Model trailing window is fixed at $W=30$ cycles for `fd001-v1`.
- For cutoff $C$, the window is $[C - 29, C]$.
- All 30 cycles must be strictly consecutive and contiguous.
- Missing readings, gaps, or insufficient history return `status: "unavailable"` with controlled reason codes (`insufficient_history`, `gaps_in_history`, `no_observations`).
- Gaps are **never** interpolated, padded, or zero-filled.
- No ground truth RUL labels or future cycles ($> C$) are ever accessed.

### 3. Deduplication & Idempotency
- Unique constraint `predictions_dedup` on `(tenant_id, machine_id, stream_id, requested_cutoff_cycle, input_digest, model_digest, inference_version)`.
- Input digest is SHA-256 of canonical JSON-serialized observations `[[cycle, settings, sensors], ...]`.
- Repeated requests return the existing record with `idempotency_replayed: true`.
- If observations are later backfilled to bridge a gap, a subsequent prediction evaluates the newly complete window and creates a new available record.

### 4. Domain Semantics
- **Units**: Remaining Useful Life is strictly measured in **cycles**. Cycles are discrete aircraft flight cycles, not calendar days or hours.
- **Confidence**: `failure_probability` and `interval` are strictly `null`. The global RMSE of the model is not a per-engine confidence interval.
- **Diagnosis**: `diagnosis_basis` is `'unavailable'`.
- **Release Status**: `release_status` is `'experiment_only'`.

### 5. Maintenance Priority & Outdated Tracking
- Priority is evaluated by policy `v1-experimental` using named bands (`urgent`, `high`, `medium`, `low`, `unknown`).
- Thresholds ($\le 15$, $\le 35$, $\le 75$, $> 75$ cycles) are experimental simulation rules, not manufacturer limits.
- If observations in DB have advanced past the prediction cutoff ($C_{\text{max\_obs}} > C_{\text{pred}}$), the prediction is marked `is_outdated: true`, `is_current: false`.
- Outdated and unavailable predictions are visibly distinct in `/api/v1/maintenance-priorities` and never masquerade as healthy.

---

## Suggested Scope for Phase 7

1. **Human-in-the-Loop Maintenance Action Gate**:
   - Allow technicians / plant managers to review `urgent` and `high` priority recommendations.
   - Require human approval before converting a priority recommendation into an actionable work order.
2. **Maintenance Action Records**:
   - Create work order schema linked to `machine_id` and `prediction_id`.
   - Prevent duplicate work orders for the same prediction snapshot.
3. **Model Release Governance**:
   - Model release promotion workflow with dual-signoff to promote from `experiment_only` to `production_candidate`.
