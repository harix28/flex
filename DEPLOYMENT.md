# Container deployment

Updated 2026-10-28. Source configuration and application checks are implemented. Docker build/startup and browser smoke testing remain unverified on this host.

## Configuration

Use a running Docker Engine and Compose v2.24.4+ (local override uses `!override`). Copy `.env.container.example` to a PRIVATE env file. Scripts default to `.env.production` and never overwrite it. Generate THREE DISTINCT secrets using `python -c "import secrets; print(secrets.token_urlsafe(36))"` for POSTGRES_PASSWORD, SENTINEL_RUNTIME_PASSWORD and SENTINEL_API_KEY. Database passwords must be URL-safe because Compose interpolates connection URLs. There are no password defaults.

Shell variables take precedence over the explicitly selected env file; unset conflicting values. Never publish resolved Compose configuration. The old private `.env.production` is preserved and must be updated, including the separate runtime password. Environment changes do not change existing database credentials. Volumes created with the old `sentinel` owner require deliberate backup/restore or DBA-managed credential transition. Never delete volumes to bypass credential errors.

## HTTPS deployment

Put a hostname-valid certificate chain at `config/tls/fullchain.pem` and its matching key at `config/tls/privkey.pem`. Both are ignored by Git/build context and mounted read-only. Missing certificates prevent gateway startup. Set SENTINEL_AUTH_ORIGINS to the exact browser origin including a nonstandard port, e.g. `https://localhost:8443`. Default gateway binding is loopback port 8443. Explicitly configure GATEWAY_BIND and GATEWAY_PORT for intended external access, and match the auth origin.

Backend, frontend and PostgreSQL have no published ports. Nginx preserves Host including the port, sets the scheme, and overwrites forwarded client addresses. Backend trusts forwarding within this private boundary; never publish its port or attach untrusted containers to the network. Secure cookies and HTTPS are required. Only the internal loopback health probe skips certificate verification; browser certificate checking must stay enabled.

```powershell
./scripts/deploy.ps1 -Rebuild
./scripts/deploy.ps1 -EnvFile .env.container-private -Rebuild
```

```bash
./scripts/deploy.sh --rebuild
./scripts/deploy.sh --env-file .env.container-private --rebuild
```

Scripts check daemon/Compose availability, use the same explicit env file throughout, propagate failures and wait up to 180 seconds for health checks. Verify `/health/deployment`, actual browser login, tenant selection and authorized reads before release. No users or machines are created implicitly; follow the existing authentication bootstrap documentation.

## Local HTTP demo

Use `./scripts/deploy.ps1 -Dev -Rebuild` or `./scripts/deploy.sh --dev --rebuild`. Only loopback port 8080 is published. Origins are exactly `http://localhost:8080` and `http://127.0.0.1:8080`. This is a local demo, without hot reload; it is not external production authentication. Secrets are still required; TLS certificates are not used. Use the same mode/env file for shutdown.

## Database lifecycle

The one-shot migrate service uses sentinel_owner to run Alembic and provision sentinel_app. Any failure blocks backend startup. Backend receives only the runtime password. Runtime gets DML/sequence access, but cannot create tables/roles/databases, bypass RLS or modify alembic_version. Application tenant checks remain necessary; this does not implement RLS. Grants run after each successful migration. Do not run concurrent migration jobs.

The new /health/deployment probe requires the model plus a configured database at the expected schema revision. Existing /health/ready remains model-only for compatibility; /health/live still checks the process. One backend worker avoids multiplying process-local login limits; shared rate limiting for replicas remains future work.

Schema head remains 0007_mlops. Back up before upgrades and retain the prior image with a matching schema backup. Shutdown never uses down -v. Existing records and model artifacts are not reset. The historical FD001 model stays mounted read-only; container model promotion and durable release-pointer storage remain out of scope.

## Validation

See [executed checks](reports/DEPLOYMENT_FIXES_20261028.md). Docker builds, fresh-volume migration, TLS/browser login and gateway behavior must still pass on a Docker-capable host. Configuration changes alone are not production certification.

Compose override version requirement: [Docker merge reference](https://docs.docker.com/reference/compose-file/merge/).
