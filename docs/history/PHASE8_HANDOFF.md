> Corrective follow-up (2026-10-27): see [Phase 8–9 validation](../reports/PHASE8_9_FIXES_VALIDATION.md) and [current release/recovery contract](MODEL_RELEASE_AND_ROLLBACK.md). Historical test counts and release assumptions below are superseded by that follow-up. Schema remains `0007_mlops`.

# Phase 8 Handoff — Frontend Portal and Backend Integration

**Version**: 1.0  
**Date**: 2026-10-26  
**Status**: COMPLETE / ACCEPTED  
**Baseline**: Phase 7 Work Orders (`0006_work_orders`) & Phase 8 Portal (`apps/web`)

---

## 1. Scope Completed in Phase 8

1. **Frontend Architecture (`apps/web`)**:
   - Modern React 18 + TypeScript + Vite architecture.
   - Restrained industrial design system with aerospace dark theme and accessible contrast.
   - Fully typed API client layer (`src/services/api.ts`, `src/services/types.ts`) matching OpenAPI contracts.
   - HttpOnly session cookie support and in-memory CSRF token hydration.
   - Tenant-scoped state and role-based action gating (`admin`, `plant_manager`, `technician`, `viewer`).

2. **Core Pages & Views**:
   - **Login Page** (`/login`): Secure credentials entry and session establishment.
   - **Overview Page** (`/`): Priority summary cards, ranked machines table, band filters, and honest pagination.
   - **Machines Page** (`/machines`): Registry browser with exact-match asset filters.
   - **Machine Detail Page** (`/machines/:id`): Stored metadata, sensor channel mapping, interactive SVG trend chart with gap preservation, tabular toggle, prediction card, and related work orders.
   - **Work Orders Page** (`/work-orders`): Fleet maintenance table with status/priority/due date filtering.
   - **Work Order Detail Page** (`/work-orders/:id`): Concurrency-controlled transitions (`approve`, `assign`, `start`, `block`, `resume`, `complete`, `cancel`), immutable prediction evidence, outdated evidence alerts, append-only versioned notes, and full audit timeline.
   - **Registry Management Page** (`/registry`): Machine and sensor configuration, installation history, and logical channel bindings.
   - **Organization Members Page** (`/members`): Tenant membership overview and role assignments.

3. **Backend Integration Repairs**:
   - Fixed CORS origin validation for localhost development proxying (`SENTINEL_AUTH_ORIGINS`).
   - Verified that work order notes endpoint (`POST /notes`) transactionally returns `{note, work_order_version, request_id}`.
   - Validated that outdated evidence approval returns `409 outdated_evidence`.
   - Seeded demonstrative NASA C-MAPSS FD001 test partition engine 1 telemetry via explicit script.

---

## 2. Tested Behaviors and Evidence

- **Frontend Tests**: 17 component and unit tests in `apps/web/src/__tests__/` (100% passing).
- **Type Checking**: Clean `tsc --noEmit` with 0 warnings or errors.
- **Production Build**: Clean `vite build` producing optimized SPA artifacts in `apps/web/dist/`.
- **E2E Live Flow**: 10-step end-to-end integration flow verified on live servers via `scripts/verify_e2e_flow.py`.
- **Backend Tests**: 233 baseline pytest tests passing without regressions.

---

## 3. Known Limitations and Non-Goals

1. **Simulated Replay Only**: Telemetry is sourced from NASA C-MAPSS run-to-failure text datasets. No live hardware sensors or physical bus protocol drivers are connected.
2. **Experimental Causal Model**: Model bundle `runs/fd001-v1` predicts remaining cycles for FD001 engines. Failure probabilities and subsystem diagnostics are unmodeled and display as *"Unavailable"*.
3. **Single Active Work Order Policy**: The system permits at most one active prediction work order per machine to prevent duplicated maintenance operations.
4. **No Automated Shutdown**: Maintenance recommendations require human approval and sign-off. Work order completion does not automatically certify physical airworthiness.

---

## 4. Recommended Next Phase: Phase 9

- **Phase 9 Scope Proposal**: Multi-Engine Batch Prediction & Automated Fleet Health Reports.
  - Implement bulk causal inference runs for fleet-wide inspection planning.
  - Add scheduled PDF/CSV maintenance compliance export generation.
  - Introduce hardware edge ingestion simulator via secure MQTT/TLS.
