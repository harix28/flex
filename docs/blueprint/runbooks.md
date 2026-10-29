# Operational Runbooks

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## RB-01: telemetry outage

Detect via freshness policy. Mark data unavailable and retain last observation with age. Check gateway power/connectivity/credential/mapping without issuing machine control commands. Restore source; backfill as historical and avoid alert floods. Verify newest event and prediction freshness before returning monitoring status.

## RB-02: inference worker failure

Check queue age, worker health and last successful artifact load. Keep ingestion within bounds; display pending/unavailable outputs. Restore worker or verified previous image. Reclaim expired job leases; confirm deduplication after retries. Record incident and trace IDs.

## RB-03: problematic model deployment

Freeze further promotions. Identify immutable version, schema and scope. Authorized operator restores prior approved complete bundle; perform compatibility smoke test. Preserve failed predictions and release audit. Investigate cause and create a new reviewed candidate rather than overwriting model files.

## RB-04: wrong sensor mapping

Quarantine affected source and mark assessments unreliable. Verify physical identity and installation with technician. Record corrected mapping validity period; historical records are annotated, not silently rewritten. Recompute historical evidence only through an audited job. Review incidents created from wrong mapping.

## RB-05: suspected account or connector compromise

Revoke affected sessions/credentials; restrict scope; preserve audit evidence; follow organization incident process. Rotate secrets and validate external destinations before reconnecting. Do not leak tokens into debugging channels.

## RB-06: database restore

Choose approved recovery point, restore isolated instance, verify checksums/migrations/tenant records, restore matching artifacts, run smoke tests, then controlled cutover. Record actual lost-data window and recovery duration. Replay outbox safely and notify owners of potentially missing operational records.
