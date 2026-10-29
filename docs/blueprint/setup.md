# Setup and Developer Onboarding

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## What runs today

This ZIP contains Markdown, JSON contracts, reference SQL and a documentation checker. It does not include React/FastAPI application source, containers, trained artifacts or NASA data. The following check is executable with Python 3.10+ and standard library:

```bash
python scripts/validate_docs.py
```

Open readme.md in a Mermaid-capable Markdown viewer. A plain text viewer shows diagram source, not rendered diagrams.

## Application setup sequence to implement

1. Select a supported Python runtime and Node LTS, then commit exact locks and runtime files. Avoid unpinned latest dependencies.
2. Scaffold frontend/API/worker directories described in project_implementation.md.
3. Provision local PostgreSQL, private artifact storage and a development OIDC provider. Bind admin ports to localhost.
4. Copy .env.example to a local secret file, supply development-only credentials; never commit it.
5. Implement Alembic migrations from reviewed schema, then create tenant and role fixtures using a seed command. No universal default password.
6. Download C-MAPSS from the NASA source, review distribution terms and verify archive/file hashes. Keep raw files outside Git.
7. Run parser validation, produce engine split manifest, train baseline, evaluate and register an immutable bundle.
8. Start API and worker, then frontend. Load asset/sensor registry and start labeled replay.
9. Verify unavailable state before history is sufficient; run one complete incident-to-verification flow.

## Future command contract (not supplied yet)

The implementation should provide `make dev`, `make migrate`, `make seed-demo`, `make replay`, `make test`, `make train-baseline`, and `make evaluate`. Each command must fail with a clear missing-dependency message. Do not paste these into a shell expecting this docs-only ZIP to launch a portal.

## Configuration categories

DATABASE_URL, OIDC issuer/client/redirect, SESSION_SECRET, CSRF secret, allowed origins, artifact location, tracking URI, DATA_MODE, freshness policy, inference window and risk horizon. Startup validates mandatory values. Secrets are not printed in startup logs. `DATA_MODE=replay` is the default; `live` requires a configured and verified adapter.

## Onboarding verification

Sign in with viewer/technician/manager test identities; inspect permissions; ingest the example only after replacing IDs with seeded records; reject mismatched mapping; view actual measured model report; inspect audit event. Failure at any step is a blocker for that capability, not a reason to silently switch to fake successful responses.
