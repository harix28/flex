# Durable background jobs

The asynchronous worker supports operator-enqueued FD001 drift evaluations and
bounded fleet scoring. It uses PostgreSQL directly; no Celery broker is needed.
Ingestion, notification handlers, HTTP submission, and automatic periodic scheduling remain
planned. Existing synchronous endpoints retain their behavior.

## Setup and operation

Back up the database, stop API/worker processes, and run the owner-credential
migration using the repository's normal migration procedure:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m sentinel.jobs enqueue-drift --tenant <tenant-uuid> --source-event-id drift-2026-10-30T12:00Z
.venv/Scripts/python.exe -m sentinel.jobs enqueue-fleet --tenant <tenant-uuid> --actor <user-uuid> --source-event-id fleet-2026-10-30T12:00Z
.venv/Scripts/python.exe -m sentinel.jobs work --once
.venv/Scripts/python.exe -m sentinel.jobs work
.venv/Scripts/python.exe -m sentinel.jobs status --tenant <tenant-uuid> --job <job-uuid>
```

Commands load DATABASE_URL through normal configuration. The producer is an
operator tool requiring database access; it is not a public API or a substitute
for membership checks. Internal producers call `enqueue` inside their existing
authorized transaction. Tenant IDs come from trusted authorization context.
The tenant foreign key rejects nonexistent tenants. Do not grant database access
to end users. Existing deployment procedures must grant the worker runtime role
access to new tables/view as appropriate. Schema readiness now requires 0009_fleet_jobs.

Drift uses the existing pinned FD001 model and verified training reference. Fleet
scoring loads only the configured primary model through the hash-verifying Predictor;
it does not discover candidate models or promote them. Missing/incompatible artifacts cause retries.
Insufficient telemetry is a successful monitoring outcome with explicit unknown
status, not evidence of health. Run under a process supervisor for restart on
database outages. Ctrl+C exits; an interrupted job becomes recoverable after its
lease expires. No background process is installed by this change.

## Delivery and recovery

Enqueue uniqueness is `(tenant_id, event_type, source_event_id)`. Repeat a source
ID to obtain the original job; use a new ID for a genuinely new monitoring run.
Allowed events are `drift.evaluate` with an empty validated JSON payload and
`fleet.score` with a validated frozen fleet snapshot. Conflicting reuse of a source
event ID is rejected by the generic enqueue function.

## Fleet scoring contract

The CLI requires an explicit user ID with an active account and tenant membership
granting `predictions.create`. This is an operator action made on behalf of that
requester, not user impersonation through a public endpoint. Both producer and
worker recheck permissions while holding tenant and membership locks. The status
command is an operator database tool scoped by tenant ID; it is not end-user auth.

Each run snapshots all active machines in one tenant, up to 100. Larger fleets are
rejected without partial enqueue; there is no silent truncation. Empty fleets
complete with zero results. The payload freezes the requester, primary bundle hash,
policy version, stream IDs, cutoff cycles and trailing-window input digests.
Repeating the same source event ID for the same requester returns that original
snapshot even after ingestion advances. A different requester cannot reuse it.

The worker rejects changed model/policy identity, disabled users/memberships,
inactive machines, foreign-tenant machine IDs, changed streams and backfilled
windows. New observations after the frozen cutoff do not affect the run. Rejection
uses the normal retry/dead-letter policy; after resolving the cause, submit a new
source ID to capture a new snapshot. Worker and producer must use the same primary
model configuration. No model directory or credential is accepted in a job payload.

All predictions, their audit events and job completion commit atomically. An unexpected
failure on any asset rolls the entire bounded batch back. The handler reuses existing
prediction uniqueness and provenance; insufficient history and unsupported machines
or subsets are completed `unavailable` predictions with unknown priority. Successful
job results store counts and per-machine prediction IDs/status/reason. Existing
prediction API/UI surfaces can display these persisted records. Queued job progress
is currently available through the operator status command, not the UI; an existing
prediction card is not an indicator that a newly queued run has finished.

Fleet execution holds tenant locks for the batch, so it can temporarily contend with
same-tenant writes. This is a bounded first implementation, not a high-volume SLA.
It does not create/approve work orders, dispatch technicians or schedule itself.

Workers claim with `FOR UPDATE SKIP LOCKED`, a unique lease token and a five-minute
lease. Each claim consumes an attempt, including crashes. A handler holds the job
row lock through its database transaction, so another worker skips it even if the
lease expires during execution. Lease-token checks reject stale claimants. Handler
effects and success acknowledgement commit together. A savepoint rolls back failed
effects before recording retry state. Handlers must use the supplied session and
must not commit it or perform external side effects. Delivery is at least once;
these guarantees do not extend to outbound network calls or filesystem cache writes.

Retries use 2/4/8/16 seconds of delay before the default fifth failed attempt enters
`dead_letter`. Exhausted crashed claims also become dead letters. Errors store only
`handler_failed` or `attempts_exhausted`, never arbitrary exception messages.
Inspect `outbox_events` by tenant, status and ID, or the `outbox_dead_letter` view.
Investigate model/reference availability and database health before submitting a
new source ID. Preserve the dead-letter row as evidence; there is no automatic
dead-letter replay or deletion. Monitoring results remain in `ml_monitoring_runs`.

## Rollback

Stop producers/workers first. Back up both outbox rows and domain data; drain pending
jobs where possible. Downgrading 0009 to 0008 refuses while any fleet job exists.
Archive the fleet rows, then explicitly remove them only as part of a reviewed rollback;
completed predictions/audits are retained. Downgrade drops the job result column.
`alembic downgrade 0007_mlops` subsequently removes the queue and view,
including all pending jobs and delivery history. It does not undo completed drift
runs. Deploy the previous application revision together with the downgrade because
its readiness check expects the old schema. Restore the full matching backup if
queue history must be recovered. Never restore only queue state over newer domain
state: that can replay already completed work. Test on disposable databases first.
