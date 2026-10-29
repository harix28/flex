# Deployment and Environments

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Environments

Local uses synthetic/replay data and local credentials. Staging uses isolated fixtures and mirrors production configuration. Production/pilot uses approved plant data, private infrastructure and monitored release gates. Separate databases, buckets, identity clients and credentials; never point staging at production by convenience.

## Deployment units

Web static bundle, API container, worker container, PostgreSQL, private object store and optional MLflow service. Place TLS ingress before the application. The API/worker share a versioned domain package and feature transforms. Model artifact release is separate from application release but compatibility is checked together.

## Release sequence

CI lint/type/test → dependency scan → build immutable image → migration rehearsal → staging smoke/role tests → approved release → health checks → controlled traffic → observe → record release. Expand/contract migrations for incompatible schema changes. Rollback must account for schema changes; restoring an old app against an incompatible DB is not a rollback plan.

## Secrets and storage

Inject secrets from approved storage, rotate integration credentials and restrict service roles. Persist DB and artifact volumes; container filesystem is not durable storage. Signed download URLs have short lifetimes and scoped authorization. Do not expose admin or tracking endpoints publicly.

## Recovery

Measure RPO/RTO in a restore drill, including registry artifacts and configuration. Validate tenant isolation and active model after restore. Re-deliver outbox events idempotently. Backups without a tested restore are not sufficient evidence of recoverability.

## Live pilot gate

Verified asset mapping, applicable model domain, data-quality policy, approved operating procedures, named incident owner and plant sign-off. Begin in observation mode. No autonomous control path is part of this project.
