# Planned Services: Background Workers and Async Jobs

This specification describes planned asynchronous background processing services for the Meridian Sentinel architecture.

## Status

**Status: PLANNED / SPECIFICATION ONLY**

The current implementation runs as a synchronous FastAPI backend in [sentinel/api.py](../../sentinel/api.py) and [sentinel/serve.py](../../sentinel/serve.py). Background processing queues have not yet been implemented.

---

## Planned Architecture

```mermaid
flowchart LR
    API[FastAPI Application] -->|Enqueue Event| Outbox[(PostgreSQL Outbox Table)]
    Outbox -->|Poll / Lease| Worker[Worker Service]
    Worker -->|Execute Job| JobEngine{Job Handlers}
    JobEngine -->|Batch Inference| Inference[sentinel/inference.py]
    JobEngine -->|Batch Telemetry Import| Ingestion[sentinel/ingestion/]
    JobEngine -->|Audit Event| AuditLog[(Audit Records)]
```

### 1. PostgreSQL Outbox Consumer
- **Pattern**: Transactional outbox table within PostgreSQL (`outbox_events`).
- **Processing**: Periodic polling with `FOR UPDATE SKIP LOCKED` row-level leasing to support multiple consumer instances without lock contention.
- **Resilience**: Explicit retry policies with exponential backoff and dead-letter queues (`outbox_dead_letter`) after a maximum number of failed attempts.
- **Idempotency**: Source event IDs and idempotency keys to ensure at-most-once state mutations.

### 2. Planned Job Handlers
- **Replay Ingestion**: Asynchronous batch ingestion of high-volume telemetry archives.
- **Batch Fleet Scoring**: Scheduled execution of RUL inference across all active fleet machines at shift boundaries.
- **Model Monitoring & Drift**: Periodic execution of feature drift checks and latency aggregation jobs.
- **Notification Delivery**: Authorized outbound dispatch of maintenance alerts to external channels with delivery deduplication.

### 3. Safety Constraints
- Workers must never bypass tenant isolation; worker context must always include explicit `tenant_id`.
- Workers must never automatically approve maintenance work orders or dispatch technicians autonomously.
