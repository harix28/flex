# Test Strategy

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Test layers

Unit: parser, unit conversion, quality rules, causal windows, labels, transition predicates and priority logic. Integration: real PostgreSQL constraints/transactions, OIDC validation, tenant isolation, idempotent API mutations and outbox retries. End-to-end: role-specific portal journeys with deterministic replay. ML: leakage, reproducibility, baseline comparison, calibration and alert replay. Operational: restore, rollback and dependency outage.

| Test ID | Scenario | Expected result |
|---|---|---|
| T01 | Other tenant requests machine ID | 404; no evidence leak |
| T02 | Same source event repeated | One persisted frame/prediction per model |
| T03 | Same key, different request body | 409 conflict |
| T04 | Required sensor disconnected | Unknown/unavailable; no zero-risk badge |
| T05 | Old frame arrives after new one | Historical storage; current pointer unchanged |
| T06 | Wrong unit/unknown mapping | Rejected or quarantined, explicit reason |
| T07 | Two concurrent work-order updates | One wins; one gets version conflict |
| T08 | Technician tries manager approval | 403; no transition |
| T09 | Repair marked done | Verification pending, not automatically closed |
| T10 | Training engine appears in calibration | Pipeline fails before training |
| T11 | Future data affects earlier features | Causal-window invariant fails |
| T12 | Model feature order mismatches | Load/scoring rejected |
| T13 | Worker dies after commit before ack | Retry yields no duplicate work |
| T14 | Unreviewed candidate deployment | Blocked |
| T15 | Rollback after incompatible release | Prior full compatible bundle restored |
| T16 | Malicious manual instructs approval | No privileged tool action |
| T17 | Replay paused | Replay label/clock policy shown correctly |
| T18 | Database restore drill | Declared RPO/RTO measured, integrity checked |

## Test fixtures

Two tenants, separate roles, same human with explicit multiple memberships, verified/unverified installations, healthy/degrading/offline/retired assets, duplicate and out-of-order frames, approved and unauthorized drafts. ML fixtures must use distinct engine IDs and controlled synthetic signals for transform correctness; performance claims require actual held-out data.

## Load test

Declare asset count, cadence, readings/frame and concurrency. Measure ingest acceptance, queue depth, prediction delay, fleet p95 and DB growth. Initial planning load is 100 assets × 21 readings/minute. Do not extrapolate this to high-frequency vibration ingestion without a separate architecture test.

## Release gates

No critical auth/tenant defects, all P0 acceptance tests pass, migrations reviewed, actual model report exists, artifact verification passes, replay provenance visible, recovery workflow tested. Record executed command, environment, commit and result. This pack's documentation checker is not evidence that these application tests have run.
