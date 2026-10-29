# Antigravity change review — 2026-10-28

## Conclusion and scope

The new deployment scaffolding is present, but it is not verified production deployment. Existing application modules remain implemented. The substantive recent additions are backend/frontend Dockerfiles, Compose orchestration, Nginx routing, deployment scripts, container-mode settings and the ASGI factory. No new trained model or new application phase was established by these deployment changes.

Reviewed repository: `H:/HarixAI/Projects/Meridian_Sentinel/Meridian_Sentinel_Full_Architecture`. Git resolves to an unrelated parent repository at `H:/HarixAI`; this project is not a tracked standalone checkout there. Therefore this review cannot attribute an exact commit diff to Antigravity. File contents, modification times, previous reports and executable checks were used. No application source or model was changed during review.

## Findings, in priority order

### P1 — Database defaults expose a privileged account with a known password

`docker-compose.yml:12–20` supplies a fixed password fallback and publishes PostgreSQL on all host interfaces. The official image's bootstrap account is also used as the application's connection role (`:42`). A default deployment therefore exposes a highly privileged database account using a password written in the repository. Require an explicit generated password, keep the database private to the Compose network (or bind explicit local development access to loopback), and separate bootstrap/migration permissions from runtime permissions.

### P1 — Failed migrations still produce an apparently healthy backend

`backend/entrypoint.sh:37–39` catches every failed `alembic upgrade head` and continues into the server. `backend/Dockerfile` healthchecks `/health/live`, which always returns alive when the process runs. The model readiness endpoint also does not verify migrations. Missing or incompatible schema can consequently leave Compose reporting healthy while application requests fail. Abort startup on migration failure and add schema/database readiness checks. This finding is from source inspection; Docker execution was unavailable.

### P1 — The advertised production setup is localhost-only HTTP

`DEPLOYMENT.md:108–109` and the actual private production settings enable localhost auth and allow only localhost HTTP origins. `infra/nginx/nginx.conf:32` listens only on port 80. `sentinel/auth/context.py` rejects non-local hosts in localhost mode. A direct guard reproduction with those settings returned **403 forbidden** for `https://sentinel.example.com`, while localhost passed the host guard. This was an isolated guard test, not a live login request. Real external deployment needs an exact HTTPS origin, TLS termination, secure-cookie mode and verified proxy trust. Keep this configuration explicitly described as a local demo until that path is implemented and tested.

### P2 — Editing .env.production does not set Compose interpolation inputs

The deployment scripts invoke Compose without `--env-file .env.production`. That file is declared as a service `env_file` only for the backend, while PostgreSQL credentials, port and model hash are interpolated in Compose itself. Editing the documented production password can leave the database and the explicit backend `DATABASE_URL` using fallback values instead. Use one explicit interpolation source and validate required values; document precedence correctly. Do not print resolved configurations containing secrets in logs.

### P2 — Windows deployment reports success after Docker failures

`scripts/deploy.ps1:67–76` does not check native command exit codes and prints success after a fixed sleep. An isolated reproduction replaced Docker with a mock returning exit code 7: the script still printed **“Meridian Sentinel is deployed and running!”** and returned success. No real containers were launched in this reproduction. Check daemon/Compose availability, propagate nonzero exits, and wait for actual readiness before reporting success. The Bash script has `set -e`, but also announces readiness immediately after asynchronous startup without health verification.

### P2 — Deployment report overstates validation

`reports/DEPLOYMENT_STRUCTURE_REPORT.md` says “Ready for Deployment” and “production-grade,” but its evidence is 130 passed / 124 skipped application tests. That does not validate container build/startup, migration failure handling, external authentication or database integration. Its claim that frontend and backend both run unprivileged also does not match the standard Nginx frontend Dockerfile, which contains no `USER` override. Revise claims to distinguish implemented scaffolding from executed deployment validation.

## Existing functionality and limits

- Implemented source exists for sessions/CSRF/tenant permissions, registry, replay ingestion/history, persistent predictions, work orders, model registry/release/drift monitoring, and React portal.
- Migration head remains `0007_mlops`; deployment work did not add another application schema phase.
- Historical FD001 bundle verification against the previously trusted manifest passed. Docker explicitly mounts that historical bundle. The improved four-subset candidates, uncertainty work and Cap-125 comparison remain offline experiments; the deployment additions do not integrate them.
- Architecture directories still contain planning READMEs. Their presence is not evidence that workers, external integrations, physical telemetry or component diagnosis are implemented.
- Deployment uses two application workers while login limits remain process-local. Distributed/shared rate limiting remains a production-hardening limitation.
- Compose mounts only the fixed historical model directory. A complete container-aware model promotion/rollback workflow and persistent release-pointer storage have not been demonstrated.

## Verification

- Default backend run: **130 passed, 124 skipped**, one existing Starlette/httpx deprecation warning, 30.75 seconds. Skips were missing explicit PostgreSQL test configuration.
- Frontend: **30 tests passed**, eight files. TypeScript plus production Vite build passed.
- Historical model checksum verification passed.
- Host guard and Windows deployment failure reproductions described above completed.
- Docker CLI exists, but the daemon connection failed and `docker compose` is unavailable. Image builds, Compose validation, container startup and browser login through the gateway are **blocked**, not passed.
- PostgreSQL integration: **97 passed / 28 setup errors** in the first explicit run (282.61s); errors were connection timeouts while the retained local cluster was offline. After recovery, **all 28 affected tests passed** (59.93s). All 125 PostgreSQL-marked tests therefore passed across the run and retry, not in an uninterrupted green run. One marked test also passed in the default run, so the combined total is **254 distinct backend tests passed**. No PostgreSQL checks remain skipped or blocked. Tests create/drop generated disposable databases; application records were not reset.

Commands executed include `python -m pytest -q`, `python -m pytest -q -m postgres` with the private test admin URL, `npm --prefix apps/web test`, `npm --prefix apps/web run build`, `docker version`, `docker compose version`, and the existing `scripts/postgres-local.py start` helper. The deployment script was exercised only with mocked Docker for its failure path. Logs are under `.runtime/antigravity-review-*` and are not intended for committing.

Recommended order: fix deployment defaults and migration failure handling; make the environment source consistent; establish HTTPS/proxy/auth behavior; add a container smoke test including login, migrations and readiness; then revisit container model promotion. No model retraining is required to resolve these deployment findings.
