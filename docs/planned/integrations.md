# Planned Integrations: CMMS, IoT, Telemetry & Notifications

This specification outlines the planned external adapters and integration boundaries for Meridian Sentinel.

## Status

**Status: PLANNED / SPECIFICATION ONLY**

The current system supports local file-based NASA C-MAPSS dataset downloads via [sentinel/download.py](../../sentinel/download.py) and persistent replay ingestion via [sentinel/ingestion/](../../sentinel/ingestion/). External enterprise systems and physical hardware interfaces are not yet integrated.

---

## Planned Adapters

### 1. Computerized Maintenance Management System (CMMS)
- **Target Systems**: SAP PM, IBM Maximo, or generic enterprise CMMS APIs.
- **Scope**: Bidirectional synchronization of maintenance work orders.
- **Direction**:
  - Outbound: Approved work orders in Meridian Sentinel create draft work requests in CMMS.
  - Inbound: External CMMS completion records and technician notes sync back into Meridian Sentinel audit history.
- **Security**: Scoped OAuth 2.0 / mTLS credentials per organization. Idempotent external reference tracking (`external_order_id`).
- **Policy**: Meridian Sentinel predictions NEVER automatically generate external purchase orders or plant work requests without explicit human sign-off.

### 2. IoT Gateway & Edge Telemetry
- **Scope**: Direct ingestion from industrial edge gateways (MQTT, OPC-UA, Sparkplug B).
- **Authentication**: Device identity certificates (X.509) and scoped gateway API tokens.
- **Normalization**: Translation of physical sensor engineering units to standardized C-MAPSS operational channel schemas.
- **Safety Boundary**: Read-only telemetry transport. No actuator command execution or machine control capability.

### 3. Live NASA Telemetry Feeds
- **Current State**: Static file ingestion from official NASA data sources (`FD001` through `FD004`).
- **Planned Extension**: Automated polling and streaming ingestion from live aerospace telemetry streams or cloud storage buckets (S3 / GCS / Azure Blob).

### 4. Alert & Notification Delivery
- **Scope**: Outbound alert routing to email, SMS, or enterprise collaboration platforms (Slack, Microsoft Teams, PagerDuty).
- **Delivery Controls**: Configurable alert priority thresholds (e.g. only `urgent` and `high` priority bands notify on-call staff).
- **Rate Limiting**: Deduplication windows and alert fatigue mitigation per engine/channel.
