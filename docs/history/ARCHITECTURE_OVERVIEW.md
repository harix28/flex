# Architecture and flows

## Implemented ML/backend path

```mermaid
flowchart TD
 A[Official NASA archive] --> B[Parser and validation]
 B --> C[Engine-level split]
 C --> D[Shared causal features]
 D --> E[Baseline and candidate training]
 E --> F[Validation selection]
 F --> G[Official test evaluation]
 G --> H[Model and report bundle]
 H --> I[Hash-checked inference API]
 J[Replay history] --> K{Valid and sufficient?}
 K -- Yes --> I
 K -- No --> L[Unavailable or validation error]
 I --> M[RUL in cycles]
```

## Target application — pending beyond experimental inference

```mermaid
flowchart TD
 U[Manager and technician] --> W[Web portal]
 W --> A[API and authorization]
 O[OIDC identity] --> A
 G[Replay or gateway] --> T[Telemetry validation]
 A --> DB[(PostgreSQL)]
 T --> DB
 DB --> Q[Outbox worker]
 Q --> P[Prediction service]
 R[Approved model registry] --> P
 P --> DB
 Q --> N[Notification adapter]
 MCP[MCP read and draft tools] --> A
```

## Target MLOps release — pending

```mermaid
flowchart TD
 D[Versioned dataset] --> T[Train candidate]
 T --> E[Evaluate and calibrate]
 E --> G{Release gates pass?}
 G -- No --> X[Investigate]
 G -- Yes --> H[Human review]
 H --> R[Approved registry]
 R --> S[Serving]
 S --> M[Monitoring]
 M --> I[Review drift or errors]
 I --> D
 R --> B[Approved rollback version]
 B --> S
```

No automatic physical machine control, maintenance approval or model promotion. No calibrated failure probability or component diagnosis in the present RUL model. Bad/missing input never becomes a green/zero-risk prediction.
