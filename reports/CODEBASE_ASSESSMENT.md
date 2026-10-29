# Codebase completion assessment — 2026-10-26

Scope: existing H:/HarixAI/Projects/Meridian_Sentinel/Meridian_Sentinel_Full_Architecture.
Assessment of actual source, migrations, mounted APIs, tests and locally executed HTTP
flows. This is not a production security certification or exhaustive requirements audit.

## Corrective follow-up

The four findings below describe the pre-fix state. They are addressed by the subsequent
Phase7 corrective changes; see [PHASE7_FIXES_VALIDATION.md](PHASE7_FIXES_VALIDATION.md)
for updated behavior and verification. Original observations remain as historical evidence.

## Current implementation

The repository now contains implementation through Phase 7. This supersedes the earlier
inspection when Phase 6 source was missing. Current head is 0006_work_orders; the
predictions and work_orders routers are mounted in sentinel/api.py.

| Area | Actual state |
|---|---|
| Phase 1 local backend | Implemented configuration, HTTP bounds/errors, health checks and startup tooling |
| Phase 2 database | Implemented PostgreSQL, Alembic and scoped repository/constraints |
| Phase 3 identity | Implemented local Argon2 login, sessions, CSRF, roles and tenant membership |
| Phase 4 registry | Implemented machine/sensor registry, source binding and installation history |
| Phase 5 replay | Implemented strict observations, provenance, atomic/idempotent batches, history and gaps |
| Phase 6 predictions | Implemented stored RUL predictions, causal windows, model/input provenance and priority APIs |
| Phase 7 maintenance | Implemented main work-order flow, but requirement/security gaps remain below |
| ML | FD001 regression and reproducible local evaluation exist; not calibrated failure probability or component diagnosis |
| Web portal | Planning READMEs only under apps/web; no implemented React application |
| Workers/outbox | Planning READMEs only; predictions require explicit API calls |
| Hardware/CMMS/notifications/MCP | Planning READMEs, not operating integrations |
| MLOps/deployment/observability | Local artifacts exist, but planned registry/promotion/monitoring and production infrastructure do not |

A single overall percentage is not defensible: the remaining frontend, integrations,
ML validation and production operations have no agreed effort weights. The accurate
milestone is a substantial local replay/backend prototype, with Phase 7 not fully
complete and the end-user product still unbuilt.

## Confirmed Phase 7 gaps

1. **Execution authorization after role change.** Routes authorize transitions with
   work_orders.read. block/complete permit an assigned user without rechecking their
   work_orders.execute permission. An active technician downgraded to viewer can still
   complete their existing assignment. In an isolated PostgreSQL probe, the completion
   request returned HTTP200 and changed status to completed after roles became viewer.
   Sources: sentinel/work_orders/api.py:379; sentinel/work_orders/service.py:524.
2. **Outdated evidence approval.** The view exposes is_evidence_outdated, but the approve
   branch does not reject stale evidence or require explicit acknowledgement. A draft
   based on real FD001 cycles1..30 remained approvable after cycle31 was ingested.
   The detail response said outdated=true; approval without any acknowledgement returned
   HTTP200/approved. Source: sentinel/work_orders/service.py:479.
3. **Missing requested date filters.** Work-order list routes/service support machine,
   state, priority, assignee and pagination, but not created/due date ranges requested
   for Phase 7. Source: sentinel/work_orders/service.py:700.
4. **Notes bypass the expected-version contract.** WorkOrderNoteCreate has no expected
   version and add_note neither checks nor increments the order version. Append-only
   notes may be an intentional product choice, but it is an undocumented exception to
   the requested optimistic concurrency contract for every work-order mutation.
   Sources: sentinel/work_orders/schemas.py:83; service.py:671.

The first two observations were reproduced using isolated PostgreSQL records, not
inferred solely from code. Diagnostic probes live in ignored .runtime/test_assessment_gaps.py.
Their two passing assertions confirm undesired behavior; they do not mean these
requirements passed. No application code was changed to conceal or fix the findings.

## Verification performed

- PostgreSQL readiness check passed at current configured migration head.
- sentinel.check passed: current configured bundle, model/report and three FD001 files.
- Real Phase 7 HTTP script passed: ingestion, prediction, draft, deduplication, manager
  approval/assignment, technician start/block/resume/completion and history all HTTP200
  (machine registration201). Terminal transition400; cross-tenant read/write404.
- Two targeted PostgreSQL probes reproduced the authorization and stale-evidence gaps
  described above; both returned the unexpected HTTP200 outcome.
- The first full-suite attempt encountered local PostgreSQL connection timeouts:
  189 passed,24 setup errors,2 warnings in408.58s. PostgreSQL was restarted and the full
  suite rerun; final result is recorded below. These setup errors are not presented as
  application assertion failures or successful integration checks.

The existing reports' blanket claim that all Phase 7 requirements are complete is too
strong. Passing normal-flow tests does not cover the reproduced cases. The status
file also retains an obsolete line saying Phase 6 is next, despite the new Phase 7 table.
GitHub CI is configured but has no PostgreSQL service/test-admin URL; database tests
skip unless that external dependency is supplied. Local ignored data/model files are
additional prerequisites for the current real-data tests.

## Recommended sequence

1. Fix the Phase 7 execution authorization and outdated-approval policy, with regression tests.
2. Complete date filtering and clarify/apply concurrency rules for notes; audit remaining
   Phase 7 acceptance cases such as concurrent changes and assignee revocation.
3. Build an authenticated frontend over these existing APIs: fleet, machine/history,
   predictions and work-order workflows.
4. Add explicit background job/operational deployment requirements and verify backups,
   monitoring, credential handling, load and recovery before a real pilot.
5. Treat real sensors and broader model support as separately validated integrations.

Only ignored diagnostic files and verification evidence were produced during this
assessment; application code, migrations and model artifacts were not edited.

## Final regression result

Fresh full-suite rerun after PostgreSQL startup: **213 passed,0 failed,0 skipped**,
1 existing Starlette/httpx TestClient deprecation warning,362.19seconds.
The two separate diagnostic probes also completed and confirmed the two undesired
HTTP200 outcomes above. No production-readiness conclusion follows from this count.

Executed commands included `python -m pytest -q`,
`python -m pytest .runtime/test_assessment_gaps.py -q -s`,
`python scripts/verify-work-orders-local.py`, `python -m sentinel.check`,
`python -m sentinel.db check --env-file .runtime/postgres.env`, and the native
PostgreSQL helper start command. Credentials were loaded from private local configuration
without printing them. Regression tests and diagnostic probes used disposable databases.
