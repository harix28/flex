# Working instructions for another AI

## Before changing anything

Read this pack's start page, gap register and the relevant master-guide sections. Inspect the actual repository if available; a bundled snapshot can become stale. Read the applicable `AGENTS.md` files. Check Git status and identify uncommitted/user changes. Never replace current source with the bundled snapshot indiscriminately.

Choose one concrete vertical slice. Locate its handler, schema, service, database migration, frontend client/types/page and tests. Search exact symbol references instead of trusting a similarly named service. Compare current runtime OpenAPI to the frontend and stored export. Determine which behaviors are implemented, prototype-only or merely planned.

## Invariants to preserve

- Tenant is resolved from trusted identity/membership; user-supplied UUID alone is not authorization.
- Recheck account, membership, role and assignee eligibility when the action occurs.
- Use the established CSRF/origin/session boundary for state-changing browser requests.
- Keep raw telemetry immutable and retain source dataset/partition/engine/file/stream identity.
- Do not fill missing sensor values with zero or silently bridge data gaps.
- Never use future observations, official test labels or full lifetime as current inference features.
- Separate RUL cycles, lifetime stage, priority policy, failure probability and physical diagnosis.
- Preserve unknown/unavailable state; zero, healthy and missing are not interchangeable.
- Hash-verify trusted artifacts and load safe formats; no arbitrary pickle execution.
- Use stable source-event and idempotency keys; reject conflicting replay instead of disabling retries.
- Preserve immutable prediction/work-order evidence and append attributable history.
- Do not automatically approve maintenance, dispatch technicians, control equipment or promote models.
- Do not claim compliance, signed evidence, real notification delivery, live IoT or downtime savings without implementation and measured evidence.
- Do not print/commit/upload private environment files, tokens, model binaries, raw telemetry or private credentials.

## Implementation checklist

For a DB change, add a forward Alembic revision, update readiness expectation, inspect runtime grants, write downgrade/restore instructions and exercise disposable-database migration behavior. Do not run schema reference SQL as a substitute. For an API change, use explicit schemas/bounds, preserve safe errors, update exported OpenAPI and matching UI types, and test unauthorized/cross-tenant/malformed requests. For a worker change, test duplicate delivery, crashes, expired leases, stale claimant rejection, transaction rollback and bounded retry/dead-letter behavior. External side effects require their own durable idempotency design.

For a model change, freeze provenance/splits/features, select without test leakage, report held-out metrics and populations, verify artifact parity, retain baseline comparison and require a reviewed release. Do not retrain simply to make a smoke check pass. For an export, validate actual rendered content and unknown states; a file generating successfully is not proof of correctness. For an assistant tool, test actual authorized execution and negative cases, not only tool advertisement.

## Verification commands and limits

Use the repository virtual environment. Backend integration tests need explicit `SENTINEL_TEST_ADMIN_URL` with permission to create disposable databases. Do not derive authority from an unrelated production connection. The project has no SQLite fallback for its PostgreSQL guarantees. Frontend tests and build run from `apps/web`. Avoid overstating coverage: report exact commands, passed/failed/skipped counts and environment. At this snapshot collection is blocked by an empty training module; do not conceal that with a selective green summary.

## How to answer the user

Lead with the outcome. State changed files/behavior, why, actual validation, remaining limits and whether migration/deployment occurred. Use source references for claims. If blocked by missing credentials, artifacts or a conflicting change, explain exactly what can still be completed and what requires external input. Do not invent connectivity, model metrics, findings or approval. Treat the user's new message as steering the current task unless they clearly replace it.

## Context-window strategy

Keep the start page/gap register as working memory. Load relevant source snapshot files on demand. Use the symbol/route/test index to target retrieval. If context is compressed, retain objective, accepted decisions, invariants, current modified files, test evidence and unresolved blockers. Do not discard the distinction between historical evidence and current working-tree reality.
