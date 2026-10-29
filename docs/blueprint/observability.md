# Observability and Monitoring

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Signals

| Layer | Measures | Example alert condition |
|---|---|---|
| Adapter | Last event, rejected count, reconnects | No data beyond configured freshness |
| API | Request rate, status, latency | Sustained 5xx above release budget |
| Worker | Queue age, retries, dead letters | Prediction queue exceeds latency budget |
| Data | Missing/stale/stuck/unit errors | Required input quality drops |
| Model | Drift by regime, unavailable rate, delayed error metrics | Investigate material regime shift |
| Workflow | Unacknowledged age, parts blockers, verification backlog | Required action overdue |
| Security | Denials, role changes, credential errors | Repeated unauthorized access |

Use structured logs with request ID, tenant-scoped resource IDs, artifact version and sanitized reason codes. Do not include secrets or whole readings by default. Aggregate metrics must avoid unbounded label cardinality; machine IDs belong in logs/traces, not every metrics label.

Dashboards show data freshness and inference freshness independently. A service can be available while telemetry is stale. Model accuracy monitoring awaits real labels; provisional technician findings are not automatically ground truth. See MLOPS_structure.md.

Alerts require an owner, severity, action and runbook. Avoid sending every anomalous point as a notification. Notification delivery itself is monitored and audited.
