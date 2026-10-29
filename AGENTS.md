# Repository Instructions for Coding Agents

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Scope

These instructions apply to this Meridian Sentinel repository. The experimental
ML backend and Phase 1 local foundation are implemented in `sentinel/`; most other
architecture folders remain specifications. See IMPLEMENTATION_STATUS.md for
current scope. Do not report modules as implemented until code and meaningful
tests exist.

## Work rules

1. Read PRD.md, architecture.md and the relevant feature contract before editing.
2. Build one vertical slice at a time. Preserve tenant isolation, explicit unknown status and human approval gates.
3. Never invent model metrics, live data connectivity, incident findings or component labels.
4. Keep API, DB, UI enums and OpenAPI synchronized. Schema changes require forward migration and rollback/restore notes.
5. Do not commit secrets, raw private telemetry, model binaries or datasets. Commit manifests/checksums and .env.example placeholders.
6. Validate external inputs with explicit schemas. No untrusted pickle/model loading; trusted artifacts must be hash-verified and isolated.
7. Use source event IDs and idempotency keys. Do not solve duplicate operations by disabling retries.
8. Unit tests target behavior, not implementation shape. Add integration tests for auth, tenant boundaries, transitions, deduplication and data leakage prevention.
9. Do not silently replace missing sensor readings with zero, convert cycles to days, or auto-approve work orders/model deployments.
10. UI copy must distinguish replay/synthetic/live, suspected/confirmed and unmeasured/measured.
11. Do not expose integration secrets to browser or assistant context. Do not use arbitrary external MCP servers without reviewed scopes and endpoints.
12. Report files changed, tested behavior, failures and remaining limitations. Never claim commands were executed if only documented.

## Expected commands after bootstrap

Run `.venv/Scripts/python.exe -m pytest -q` on Windows from the project root.
Use `python -m sentinel.serve` for local startup and `python -m sentinel.check`
to verify the existing artifacts/data and prepare a real replay. Training is
implemented but must not run as part of foundation checks. Formatter, typecheck
and database migration commands remain to be established; do not claim them run.

## Completion criteria

Relevant acceptance IDs pass; generated OpenAPI agrees with reviewed contract; schema migration reviewed; security tests pass; demo label remains visible; no fabricated metrics; runbook updated for new failure modes. Human approval is required for production model release and operational maintenance approval by application policy.
