# Flowchart and State Diagram Atlas

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

Each diagram is also present in its owning document. Open in a Mermaid-capable Markdown viewer. Diagrams describe proposed behavior.

## PRD.md — diagram 1
[Context](PRD.md)

```mermaid
flowchart TD
 A[Register asset] --> B[Verify sensor mapping]
 B --> C[Receive readings]
 C --> D{Usable input?}
 D -- No --> E[Unknown status and data task]
 D -- Yes --> F[Estimate risk and RUL]
 F --> G[Review evidence and priority]
 G --> H[Approve inspection draft]
 H --> I[Record findings]
 I --> J[Verify recovery]
```

## Design.md — diagram 1
[Context](Design.md)

```mermaid
flowchart TD
 A[Open assigned task] --> B[Scan asset QR]
 B --> C{Identity matches?}
 C -- No --> D[Stop and resolve mapping]
 C -- Yes --> E[Open marked sensor photo]
 E --> F[Approved inspection checklist]
 F --> G[Record findings]
 G --> H{Repair needed?}
 H -- Yes --> I[Review repair action]
 H -- No --> J[Record outcome or further review]
 I --> K[Verify recovery]
```

## architecture.md — diagram 1
[Context](architecture.md)

```mermaid
flowchart TD
 U[Manager and technician] --> UI[Web portal]
 UI --> API[API and authorization]
 IDP[OIDC provider] --> API
 R[Replay or gateway adapter] --> ING[Ingestion module]
 ING --> DB[(PostgreSQL)]
 API --> DB
 DB --> W[Jobs and outbox worker]
 W --> ML[Validated inference pipeline]
 ML --> DB
 W --> N[Notification adapter]
 API --> OBJ[Private object storage]
 TRAIN[Offline training] --> REG[Model registry]
 REG --> ML
 MCP[Optional MCP adapter] --> API
```

## database.md — diagram 1
[Context](database.md)

```mermaid
erDiagram
 TENANT ||--o{ MACHINE : owns
 TENANT ||--o{ SENSOR : owns
 MACHINE ||--o{ INSTALLATION : has
 SENSOR ||--o{ INSTALLATION : mounted_as
 MACHINE ||--o{ TELEMETRY_FRAME : emits
 TELEMETRY_FRAME ||--o{ READING : contains
 INSTALLATION ||--o{ READING : identifies
 TELEMETRY_FRAME ||--o{ PREDICTION : evaluated_by
 MODEL_VERSION ||--o{ PREDICTION : produces
```

## database.md — diagram 2
[Context](database.md)

```mermaid
erDiagram
 MACHINE ||--o{ INCIDENT : triggers
 PREDICTION o|--o{ INCIDENT : supports
 INCIDENT ||--o{ WORK_ORDER : investigated_by
 WORK_ORDER ||--o{ INSPECTION : records
 USER ||--o{ INSPECTION : performs
 USER ||--o{ AUDIT_EVENT : initiates
 MODEL_VERSION ||--o{ MODEL_DEPLOYMENT : released_as
```

## api.md — diagram 1
[Context](api.md)

```mermaid
sequenceDiagram
 participant C as Client
 participant A as API
 participant D as Database
 participant W as Worker
 C->>A: Frame and idempotency key
 A->>A: Authenticate and validate
 A->>D: Commit frame and outbox
 A-->>C: 202 accepted
 W->>D: Claim committed event
 W->>W: Quality and inference
 W->>D: Prediction and incident transaction
```

## Agent.md — diagram 1
[Context](Agent.md)

```mermaid
flowchart TD
 A[User question] --> B[Resolve tenant and role]
 B --> C[Retrieve scoped evidence]
 C --> D{Enough verified evidence?}
 D -- No --> E[State uncertainty and ask focused question]
 D -- Yes --> F[Compose answer with evidence IDs]
 F --> G{Draft requested?}
 G -- No --> H[Return explanation]
 G -- Yes --> I[Preview structured draft]
 I --> J[User confirms draft creation]
 J --> K[API validates and saves draft]
```

## project_implementation.md — diagram 1
[Context](project_implementation.md)

```mermaid
flowchart TD
 A[Bootstrap and contracts] --> B[Registry and identity]
 B --> C[Data validation and replay]
 C --> D[Model and evaluation]
 C --> E[Portal and unknown states]
 D --> F[Prediction integration]
 E --> F
 F --> G[Incidents and work orders]
 G --> H[Recovery and audit]
 H --> I[Release and pilot]
```

## feature_development.md — diagram 1
[Context](feature_development.md)

```mermaid
flowchart TD
 A[Acceptance example] --> B[Contract and permissions]
 B --> C[Migration if needed]
 C --> D[Backend behavior]
 D --> E[UI states and accessibility]
 E --> F[Meaningful tests]
 F --> G[Review and controlled release]
 G --> H[Observe and document]
```

## authentication_security.md — diagram 1
[Context](authentication_security.md)

```mermaid
flowchart TD
 A[Request] --> B[Authenticate identity]
 B --> C[Resolve tenant and membership]
 C --> D[Check role and resource scope]
 D --> E{Allowed action and state?}
 E -- No --> F[Reject and log appropriate event]
 E -- Yes --> G[Validate input and concurrency]
 G --> H[Commit action and audit]
```

## MCP_connections.md — diagram 1
[Context](MCP_connections.md)

```mermaid
sequenceDiagram
 participant U as User
 participant C as Assistant client
 participant M as MCP adapter
 participant A as Application API
 U->>C: Explain machine warning
 C->>M: Scoped evidence tool
 M->>A: Authenticated resource request
 A-->>M: Evidence and limitations
 M-->>C: Structured result
 C-->>U: Grounded explanation
```

## Models.md — diagram 1
[Context](Models.md)

```mermaid
flowchart TD
 A[Training engines] --> B[Disjoint split manifest]
 B --> C[Train-only preprocessing]
 C --> D[Baseline and candidates]
 D --> E[Validation and threshold selection]
 E --> F[Independent calibration]
 F --> G[Frozen evaluation]
 G --> H[Versioned bundle and model card]
```

## MLOPS_structure.md — diagram 1
[Context](MLOPS_structure.md)

```mermaid
flowchart TD
 A[Versioned dataset] --> B[Schema and leakage checks]
 B --> C[Reproducible training run]
 C --> D[Validation and calibration]
 D --> E{Release gates pass?}
 E -- No --> F[Reject with recorded reason]
 E -- Yes --> G[Register immutable candidate]
 G --> H[Human review]
 H --> I[Controlled deployment]
 I --> J[Monitor data service and outcomes]
 J --> K{Investigation result?}
 K -- Deployment fault --> L[Rollback compatible bundle]
 K -- New training need --> A
 K -- Normal variation --> J
```

## data_pipeline.md — diagram 1
[Context](data_pipeline.md)

```mermaid
flowchart TD
 A[Receive frame] --> B[Authenticate source]
 B --> C[Schema and installation lookup]
 C --> D{Quality acceptable?}
 D -- No --> E[Reject or store unavailable state]
 D -- Yes --> F[Commit frame and event]
 F --> G[Build trailing window]
 G --> H{Compatible and sufficient?}
 H -- No --> I[Unavailable prediction]
 H -- Yes --> J[Score approved bundle]
 J --> K[Store prediction and incident event]
```

## state_machines.md — diagram 1
[Context](state_machines.md)

```mermaid
stateDiagram-v2
 [*] --> draft
 draft --> approved: manager approves
 draft --> cancelled: authorized cancellation
 approved --> assigned: manager assigns
 assigned --> in_progress: assigned technician accepts
 in_progress --> awaiting_parts: parts blocker
 awaiting_parts --> in_progress: parts ready
 in_progress --> verification_pending: findings and repair record
 verification_pending --> closed: designated verification passes
 verification_pending --> in_progress: verification fails
 approved --> cancelled: manager records reason
 assigned --> cancelled: manager records reason
```
