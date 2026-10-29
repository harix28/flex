# Prioritized Backlog

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

| Epic | Priority | Deliverable | Dependency | Deferred complexity |
|---|---|---|---|---|
| Identity and registry | P0 | Login, roles, machine/sensor mapping | Bootstrap | Multi-site provisioning automation |
| Data ingestion | P0 | Parser, validation, replay, freshness | Registry | High-frequency plant streaming |
| ML baseline | P0 | Reproducible RUL/classification report | Parsed dataset | Deep sequence ensembles |
| Portal | P0 | Fleet, trends, evidence, unknown queue | Predictions | 3D digital twin |
| Maintenance | P0 | Draft/approve/assign/findings/verify | Incidents | Optimized workforce allocation |
| MLOps | P1 | Tracking, immutable versions, gates, rollback | ML baseline | Automated multi-site canaries |
| Planning | P1 | Transparent rule-based feasible plan | Skills/parts/slots data | Mathematical optimization |
| Assistant and MCP | P2 | Scoped evidence and draft generation | Stable API/manuals | Autonomous action expressly excluded |
| Component diagnosis | P2 research | Separate labeled fault study | Suitable ground truth | No implied support from FD001 metadata |

Proposed differentiators: evidence card, separate data-quality status, incident timeline, actionable work order and challenge-mode demo. Add features only after P0 works end to end. Product owners can reprioritize; record changes in PRD/ADRs and acceptance IDs.
