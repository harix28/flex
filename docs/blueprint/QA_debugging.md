# Q&A and Debugging Playbook

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Common questions

**Machine kaun si hai?** Registered ID, serial, location and verified QR mapping identify it. AI does not discover physical identity from anonymous numbers.

**Sensor kharab hai ya machine?** An unusual reading alone cannot settle that. Review sensor quality, operating context and approved inspection findings.

**Prediction blank kyun?** It may be intentionally unavailable due to stale/missing data, insufficient history, incompatible type or unapproved model. Show reason, not a fake number.

**NASA model pump par chalega?** Not a validated claim. Different machine types need relevant data and evaluation.

**RUL 30 means 30 days?** No, operating cycles. Calendar conversion needs a justified usage model.

**Component panel compressor kyun bolta hai?** In FD001 that can be known dataset metadata. It must not masquerade as learned diagnosis.

**MCP se prediction hoti hai?** No. MCP is an optional assistant access layer; the deterministic API/inference path works without it.

**MLOps automatic model change karega?** It can create an evaluated candidate pipeline; production promotion remains reviewed.

## Debugging table

| Symptom | Inspect first | Safe corrective action |
|---|---|---|
| No readings | Adapter last event, credentials, source mapping | Restore connector; retain unknown status |
| Readings but no prediction | Quality code, window length, model compatibility, queue | Fix actual blocker; replay idempotently |
| Risk jumps | Input changes, regime, feature schema, model release | Explain change; investigate; avoid smoothing away hazards |
| Excess alerts | Episode grouping, persistence, threshold calibration | Tune on validation/pilot data, not test set |
| Missing alerts | Lead time, sensor coverage, horizon, outage | Review blind spots; do not promise all failures detectable |
| Duplicate tasks | Idempotency record, outbox delivery ID, unique index | Fix dedupe; merge through audited operation |
| Login loops | Issuer/redirect/cookie/origin/time skew | Correct deployment config; don't disable validation |
| MCP unauthorized | Audience/scope/token expiry | Reauthorize with least scope |
| Wrong model loaded | Artifact hash, resolved version, config/schema | Roll back complete bundle |
| Repair still high risk | Installation history, actual findings, post-repair policy | Review evidence; don't force green |

## Investigation sequence

Trace request_id → frame_id → job/outbox ID → prediction_id → incident_id → work_order_id. Capture sanitized event times and versions. Reproduce with a minimal fixture in a non-production environment. Identify cause, add a regression test, fix and review. Never paste bearer tokens, raw private manuals or unredacted telemetry into public issues.

## Escalation packet

Expected vs actual behavior, affected scope, first/last occurrence, deployment/model/schema versions, trace IDs, sanitized fixture, known workaround and responsible owner. Separate service incident from actual machine incident to avoid misleading operations.
