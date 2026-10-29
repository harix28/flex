# Integration Contracts and Adapters

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Adapter policy

Integrations translate external protocols into validated internal contracts. They cannot bypass tenant checks, state transitions or approvals. Every connector has owner, mode, scope, credential reference, last successful event, error count and disabled state. Start with replay; add physical adapters only with plant access and a verified mapping.

| Integration | Stage | Direction | Main control |
|---|---|---|---|
| C-MAPSS replay | P0 | File → frames | Immutable source/hash and replay stream ID |
| OIDC | P0 | Identity → session | Issuer/audience/state/nonce validation |
| Artifact storage | P0 | API/worker ↔ private bucket | Short-lived scoped access and checksum |
| MLflow | P1 | Training → registry | Immutable model ID/hash; release review |
| MQTT/OPC UA gateway | P2 | Plant → outbound adapter | Plant-approved read-only acquisition, credentials |
| CMMS/EAM | P2 | Reviewed drafts/status ↔ external system | External ID mapping and explicit approval |
| Email/webhook | P1 | Outbox → destination | Allowlisted destination and delivery dedupe |
| Manuals retrieval | P2 | Approved docs → search index | Model applicability and version references |
| MCP | P2 | Assistant → application | Scoped read/draft tools |

## Replay

Use `stream_id` per replay run and deterministic external event IDs. Separate simulated cycle timestamp from ingestion clock. Pausing replay makes data freshness dependent on replay clock policy, not accidental wall-time expiry; show replay paused. Restart can replay the same run idempotently or create a new run explicitly. Never mix historical/test labels into inference payload.

## Delivery reliability

Outbox delivery uses exponential backoff with jitter, bounded attempts and a dead-letter queue. Stable external event IDs make retries safe. Persist attempt response codes and sanitized errors. Webhook receivers authenticate signatures with timestamps/replay checks; outbound destinations cannot be arbitrary user-supplied URLs. No hidden fallback to demo mode on connection failure.

## CMMS synchronization

The portal owns its draft and evidence. External CMMS may own executed work order state once exported; choose ownership before integration. Store external ID and revision. Reject/review conflicts instead of overwriting technician findings. Sending or approving an external work order requires a separate authorized action.

## Adapter acceptance

Contract fixture, duplicate event, reconnect/backfill, wrong unit, out-of-order record, credential revocation, rate limit and destination outage tests. Show connection failure separately from machine failure.
