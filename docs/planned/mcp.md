# Planned MCP: Model Context Protocol Assistant Integration

This specification details the planned Model Context Protocol (MCP) server, assistant tools, and security policies for Meridian Sentinel.

## Status

**Status: PLANNED / SPECIFICATION ONLY**

No MCP server or assistant interfaces are currently implemented. All user interactions occur through the React web portal ([apps/web/](../../apps/web/)) or authenticated REST endpoints ([sentinel/api.py](../../sentinel/api.py)).

---

## Architectural Principles

```mermaid
flowchart TD
    LLM[AI Assistant / LLM] <-->|MCP Protocol (JSON-RPC)| MCPServer[Sentinel MCP Server]
    MCPServer -->|Scoped Read/Draft Token| REST[Sentinel REST API]
    REST --> DB[(PostgreSQL)]
    
    subgraph Allowed Actions
        A1[Read Telemetry & Trends]
        A2[Inspect Prediction Evidence]
        A3[Draft Maintenance Work Order]
    end
    
    subgraph Strictly Prohibited Actions
        P1[Approve Work Orders]
        P2[Dispatch Technicians]
        P3[Promote/Deploy Models]
        P4[Modify Raw Telemetry]
    end
    
    MCPServer -.-> Allowed Actions
```

### 1. Read & Draft Scope
- MCP tools are strictly restricted to **read operations** (querying machines, telemetry trends, prediction history) and **draft creation** (proposing a maintenance work order with evidence).
- MCP assistants are **strictly forbidden** from:
  - Approving work orders or transitioning work orders to `approved` or `in_progress`.
  - Shutting down machines or issuing actuator control commands.
  - Deploying, activating, or rolling back ML models.
  - Modifying or deleting stored telemetry observations.

### 2. Tenant Context & Session Isolation
- Every MCP request must be bound to a verified organization membership and role.
- MCP server must not bypass tenant isolation or query across organization boundaries.
- No integration API secrets, database connection strings, or system private keys are ever exposed in tool schemas or returned in LLM context.

### 3. Planned MCP Tools
- `list_machines`: Enumerate machines with current health status and maintenance priority band.
- `get_sensor_trends`: Retrieve historical sensor observations and summary statistics for a given machine and cycle window.
- `get_prediction_evidence`: Retrieve discrete RUL prediction, input digest, cutoff cycle, and model metadata for an asset.
- `draft_work_order`: Create an unapproved `draft` work order containing pre-filled AMM templates and snapshot evidence for human review.
