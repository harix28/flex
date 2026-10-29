# Phase 7 Handoff: Maintenance Work Orders and Human Approval Workflow

Version: 1.0 · Updated: 2026-10-26 · Target Audience: Phase 8 Engineering

---

## 1. Implemented Boundaries

Phase 7 implements the maintenance work order lifecycle, role-based approval gates, optimistic concurrency control, and technician execution tracking on top of Phase 6 persistent predictions.

- **Current Migration Head**: `0006_work_orders`, down revision `0005_predictions`.
- **Database Schema**: `database/migrations/versions/0006_work_orders.py`.
- **Core Tables**:
  - `work_orders`: Work order entity with optimistic concurrency version, snapshot evidence, and status.
  - `work_order_transitions`: Append-only transition history (`draft`, `approved`, `in_progress`, `blocked`, `completed`, `cancelled`).
  - `work_order_assignments`: Technician assignment timeline.
  - `work_order_notes`: Append-only plain-text execution notes.
  - `work_order_counters`: Organization-scoped sequential counter for human-readable work order numbers (`WO-00001`).
  - `work_order_idempotency`: Scoped idempotency store for draft creation requests.
- **Active Code**: `sentinel/work_orders/` package (`schemas.py`, `service.py`, `api.py`).
- **Audit Table**: `auth_audit_events` extended with `work_order_*` actions.
- **Model Bundle**: `runs/fd001-v1` (unmodified, verified against manifest).

---

## 2. Key Contracts and Invariants

### 1. Human Decision Authority
- Model predictions **never** approve maintenance work orders, assign personnel, or alter machine states.
- Maintenance drafts require human review and explicit approval by a `plant_manager` or `admin`.
- Completed maintenance records signify human completion of a task; they do **not** imply machine health recovery or reset cumulative operating cycle counters.

### 2. Immutable Prediction Evidence
- Prediction-linked drafts store an exact snapshot of model metadata at creation time:
  - `prediction_id`, `model_version`, `model_digest`, `bundle_digest`
  - `stream_id`, `cutoff_cycle`, `rul_cycles` (discrete cycles, never days/hours)
  - `prediction_status`, `release_status` (`experiment_only`)
  - `policy_version`, `snapshot_priority_band`
- Later predictions or sensor readings never overwrite or mutate this snapshot.
- If newer observations arrive after draft creation ($C_{\text{max\_obs}} > C_{\text{cutoff}}$), `is_evidence_outdated` is exposed as `true` in API responses without altering the original snapshot.

### 3. State Machine & Transition Rules
- Valid states: `draft`, `approved`, `in_progress`, `blocked`, `completed`, `cancelled`.
- Valid actions: `approve`, `cancel`, `start`, `block`, `resume`, `complete`.
- `completed` and `cancelled` are strictly **terminal**. No reopening is permitted in Phase 7.
- Generic `PATCH /api/v1/work-orders/{id}` cannot change status, organization, machine, or evidence. Status transitions can only be triggered via `POST /api/v1/work-orders/{id}/transitions`.
- A technician can only start work if assigned (`assigned_technician_id` must match or user must have manager/admin role).
- Reasons are mandatory for `block` and `cancel`; a summary is mandatory for `complete`.

### 4. Deduplication & Idempotency
- Database partial unique index `uq_active_prediction_wo_per_machine` prevents multiple active prediction work orders for the same machine.
- Repeat draft creation requests return the existing active work order with `"already_active": true`.
- Optional `Idempotency-Key` header prevents duplicate submissions: identical payload returns replayed work order; altered payload returns `HTTP 409 Conflict`.

### 5. Optimistic Concurrency Control (OCC)
- Every work order has a `version` integer starting at `1`.
- Any mutation (`PATCH`, `/assignment`, `/transitions`, `/notes`) requires `version` in the request body.
- Stale updates return `HTTP 409 Conflict (version_conflict)`.

### 6. Tenant Isolation & Permissions
- Strict tenant boundary: all work orders, notes, transitions, and machines are scoped by `tenant_id`.
- Cross-tenant queries return `HTTP 404 Not Found`.
- Technicians can only execute and add notes to work orders assigned to them within their tenant.

---

## 3. Verification Commands

To verify Phase 7 locally:

```powershell
# 1. Run unit tests
.\.venv\Scripts\python.exe -m pytest tests/test_work_orders_unit.py -q

# 2. Run PostgreSQL integration tests
.\.venv\Scripts\python.exe -m pytest tests/test_work_orders_postgres.py -q

# 3. Run complete test suite (213 tests)
.\.venv\Scripts\python.exe -m pytest -q

# 4. Run real HTTP loopback verification script
.\.venv\Scripts\python.exe scripts/verify-work-orders-local.py

# 5. Verify foundation and OpenAPI synchronization
.\.venv\Scripts\python.exe -m pytest tests/test_foundation.py -k "test_openapi_snapshots_match_factory"
```

---

## 4. Suggested Scope for Next Phase (Phase 8)

1. **Maintenance Metrics & Fleet Reporting**:
   - Aggregate open vs completed work orders by priority and machine type.
   - Mean time to review/approve (`created_at` to `approved_at`) and mean time to execute (`approved_at` to `completed_at`).
   - Track outdated evidence rate at approval time.
2. **Scheduled Work & Due Date Management**:
   - Operator calendar integration for planned maintenance downtime windows.
   - Threshold-based reminders for approaching planned/due dates.
3. **Role & Operational Dashboards**:
   - Specialized views for Plant Managers (draft review queue, assignment bottlenecks) and Technicians (my active tasks, pending notes).

## Phase 7 corrective follow-up

Use the corrected contracts in MAINTENANCE_WORKFLOW.md. Execution authorization is
rechecked for every action, including block/complete. A demoted viewer cannot execute
an old assignment. Managers must reassign inactive/ineligible assignees before execution.
Approval rejects outdated evidence with409; cancel and create a fresh reviewed draft.
List endpoints now support timezone-aware created_from/created_to and due_from/due_to.
Notes require version and return top-level work_order_version; update all clients.
No migration was needed: current head remains0006_work_orders. Do not rewrite old
migrations or model artifacts. Regression coverage is tests/test_work_order_regressions.py;
validation evidence is reports/PHASE7_FIXES_VALIDATION.md.

Corrective final verification:233 passed (121 independent,112 PostgreSQL),0 failures/skips;
real HTTP stale approval409, demoted execution403 and stale note409. Two library warnings
and the final database catalog observation are recorded in PHASE7_FIXES_VALIDATION.md.
