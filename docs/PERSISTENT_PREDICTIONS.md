# Persistent RUL Predictions and Window Provenance

Version: 1.0 · Updated: 2026-10-26 · Status: Phase 6 Implemented (Experimental ML)

## Overview

Phase 6 connects stored immutable NASA replay observations ([REPLAY_INGESTION.md](REPLAY_INGESTION.md))
to Meridian Sentinel's existing verified ML model (`runs/fd001-v1`), persisting reproducible prediction
provenance and exposing maintenance priority APIs.

Predictions are requested explicitly via API or the operator-enqueued
[fleet scoring worker](BACKGROUND_JOBS.md). Ingestion does not implicitly trigger scoring.

```
+---------------------+     +--------------------+     +---------------------+
| Stored Observations | --> | Causal Window      | --> | Verified Predictor  |
| (replay_obs table)  |     | (30 cycles, no gap)|     | (runs/fd001-v1)     |
+---------------------+     +--------------------+     +---------------------+
                                                                  |
                                                                  v
+---------------------+     +--------------------+     +---------------------+
| Maintenance Priority| <-- | Deduplicated Record| <-- | Persisted RUL Cycle |
| (urgent/high/med/low|     | (predictions table)|     | (cycles, policy v1) |
+---------------------+     +--------------------+     +---------------------+
```

## Fundamental Domain Principles

### 1. Cycles Are Flight Cycles, Not Calendar Days or Hours
The NASA C-MAPSS FD001 dataset models turbofan engine operational run-to-failure trajectories measured in
discrete operating **cycles**. Each cycle corresponds to a flight cycle (takeoff, cruise, descent, landing).
- Cycles **must never** be converted into calendar days, hours, or wall-clock timestamps.
- Telemetry ingestion timestamps (`ingested_at`) reflect database storage arrival, not aircraft flight time.
- Sensor observation timestamps (`observed_at`) are explicitly `NULL` for replay data.

### 2. Maintenance Priority Is a Rule-Based Policy, Not Failure Probability
The model outputs estimated remaining useful life in cycles ($\widehat{\text{RUL}}$).
- **Failure probability is explicitly `null`**: A global regression RMSE ($\approx 41.8$ cycles) is not a per-engine failure probability.
- **Confidence interval is explicitly `null`**: No calibrated uncertainty method (e.g. conformal prediction) exists for this baseline model.
- **Priority band** (`urgent`, `high`, `medium`, `low`, `unknown`) is evaluated by a deterministic, transparent policy (`v1-experimental`).

### 3. Subsystem Diagnosis Remains Unavailable
- The FD001 model predicts bulk system-level remaining cycles from 21 sensor channels and 3 operational settings.
- Component-level failure attribution (e.g., HPC blade wear, bearing fault, combustor crack) is not modeled in FD001.
- `diagnosis_basis` is preserved strictly as `'unavailable'`.

---

## Causal Window Selection & Validation

To predict RUL at a cutoff cycle $C$ for a machine with configured model trailing window $W = 30$:
1. **Machine & Source Validation**:
   - The machine must be registered with `data_source = 'nasa_replay'` and `machine_type = 'cmapss_engine'`.
   - The machine's configured subset must match the model's supported subset (`FD001`). Physical devices or other C-MAPSS subsets (FD002–FD004) return explicit `unavailable` status with `unsupported_machine` or `unsupported_subset`.
2. **Cutoff Cycle Resolution**:
   - If `cutoff_cycle` is provided in the request, that cycle is used as $C$.
   - If omitted, $C$ defaults to the latest committed observation cycle for that machine's stream ($\max(\text{cycle})$).
3. **Historical Window Extraction**:
   - Requires observations in the exact cycle range $[C - W + 1, C]$.
   - No future observations ($\text{cycle} > C$) or ground-truth labels are ever accessed or leaked.
4. **Consecutive Continuity & Gaps**:
   - Every consecutive pair of cycles must satisfy $\text{cycle}_{i+1} - \text{cycle}_i = 1$.
   - If total observations $< W$ or the earliest cycle $> C - W + 1$, the outcome is `unavailable` with reason `insufficient_history`.
   - If any cycle in the trailing window is missing, the outcome is `unavailable` with reason `gaps_in_history`.
   - **No imputation rule**: Missing observations are never filled with zeros, padded, interpolated, or bypassed.
5. **Recovery After Backfill**:
   - If a previously incomplete window is later backfilled via ingestion, subsequent prediction requests for that cutoff evaluate the now-complete window and succeed.

---

## Idempotency and Deterministic Deduplication

Every prediction attempt computes an SHA-256 digest over the canonical JSON serialization of the selected input observations:
```python
input_digest = sha256(json.dumps([[cycle, settings, sensors], ...]))
```

The database enforces unique constraint `predictions_dedup` on:
```sql
(tenant_id, machine_id, stream_id, requested_cutoff_cycle, input_digest, model_digest, inference_version)
```
- Multiple identical requests reuse the existing persisted record (`idempotency_replayed: true`).
- Concurrent duplicate requests are resolved safely via `s.begin_nested()` and unique constraint recovery without long-held table locks.

---

## Status and Reason Classification

| Status | Reason | Explanation | Priority Band |
| :--- | :--- | :--- | :--- |
| `available` | `null` | Contiguous 30-cycle window verified, inference evaluated | `urgent` / `high` / `medium` / `low` |
| `unavailable` | `no_observations` | Machine has zero stored observations | `unknown` |
| `unavailable` | `insufficient_history` | Stored history $< 30$ cycles at cutoff | `unknown` |
| `unavailable` | `gaps_in_history` | Missing cycle(s) within the trailing 30-cycle window | `unknown` |
| `unavailable` | `unsupported_machine` | Machine is physical or non-replay | `unknown` |
| `unavailable` | `unsupported_subset` | Machine bound to subset other than FD001 | `unknown` |
| `unavailable` | `invalid_stored_input` | Stored readings contain non-finite numbers or invalid shape | `unknown` |
| `unavailable` | `nonfinite_model_output`| Model inference produced NaN or infinite RUL | `unknown` |

---

## Outdated vs Current Predictions

When fetching the latest prediction (`GET .../predictions/latest`) or generating maintenance priority rankings:
- Let $C_{\text{pred}}$ be the prediction's `requested_cutoff_cycle`.
- Let $C_{\text{latest}}$ be the latest stored observation cycle in the database.
- If $C_{\text{latest}} > C_{\text{pred}}$, the prediction is **outdated** (`is_outdated: true`, `is_current: false`).
- An outdated prediction indicates that new telemetry has arrived since the prediction was requested.
- Outdated predictions are visibly highlighted and never masquerade as current operational status.

---

## API Endpoints

All prediction and priority endpoints require session authentication (`meridian_session` cookie), CSRF protection for write requests (`X-CSRF-Token`), and tenant membership authorization.

### 1. Request Prediction
`POST /api/v1/machines/{machine_id}/predictions`  
`POST /api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions`

- **Permissions**: `predictions.create` (`technician`, `plant_manager`, `admin`).
- **Request Body (optional)**:
  ```json
  {
    "cutoff_cycle": 31
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "prediction": {
      "id": "53ac7ebb-d07d-41f1-85c8-f185f3b877b7",
      "tenant_id": "9c09e97d-6eeb-4d0d-ad30-0f305581af87",
      "machine_id": "687dd780-1ec1-4855-acbf-b2fa6c0cb60c",
      "stream_id": "d5227529-fade-4072-bd8c-948edadff076",
      "actor_id": "29473e09-6a1c-4b53-b564-216d371fe597",
      "request_id": "58bf6532-88d9-446e-a463-1206efa12abf",
      "status": "available",
      "reason": null,
      "requested_cutoff_cycle": 31,
      "observed_cutoff_cycle": 31,
      "input_start_cycle": 2,
      "input_end_cycle": 31,
      "input_window_start_cycle": 2,
      "input_window_end_cycle": 31,
      "input_observation_count": 30,
      "input_digest": "5e4a0e3147d4b2a2912ad55671da4e0f748fa46893748810e2595e23762b355e",
      "model_version": "fd001-v1",
      "model_digest": "b3e9ed3f0319b8095848ad6ce74cb8cc64cfd91adc06647d7cb95eaf57be478f",
      "bundle_digest": "d9955867513db3984fa3a3467ebafdb56f8e0704f11997d7ff05e1d07987f839",
      "inference_version": 1,
      "feature_schema_version": 1,
      "rul_cycles": 136.21971130371094,
      "rul_units": "cycles",
      "failure_probability": null,
      "interval": null,
      "diagnosis_basis": "unavailable",
      "release_status": "experiment_only",
      "policy_version": "v1-experimental",
      "priority_band": "low",
      "priority_rule": "Estimated RUL 136.2 cycles > 75 cycles: low priority / normal operational tracking",
      "created_at": "2026-10-26T09:12:17.754309Z",
      "idempotency_replayed": false
    },
    "request_id": "58bf6532-88d9-446e-a463-1206efa12abf"
  }
  ```

### 2. List Predictions for a Machine
`GET /api/v1/machines/{machine_id}/predictions?limit=25&offset=0&status=available`

- **Permissions**: `predictions.read` (all tenant members).
- **Query Params**: `limit` (1..100, default 25), `offset` (ge 0), `status` (`available` | `unavailable`).
- **Response**: Bounded paginated list sorted by `(requested_cutoff_cycle DESC, created_at DESC, id DESC)`.

### 3. Get Latest Prediction for a Machine
`GET /api/v1/machines/{machine_id}/predictions/latest`

- **Permissions**: `predictions.read`.
- **Response**: Extends `PredictionRecord` with `is_current`, `is_outdated`, and `latest_observation_cycle`.
- **404 Not Found**: If no predictions have been requested yet for this machine.

### 4. Get Prediction by ID
`GET /api/v1/predictions/{prediction_id}`

- **Permissions**: `predictions.read` for the owning tenant.
- **Tenant Isolation**: Returns 404 if accessed by a member of another organization.
