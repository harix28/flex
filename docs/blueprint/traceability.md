# Requirement Traceability

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

| Requirement | Implementation spec | Test coverage | Release gate |
|---|---|---|---|
| FR-01 registry | database.md, Design.md | T06, AC-01 | Verified mapping |
| FR-02 ingestion | data_contracts.md, data_pipeline.md | T02–T06, T13 | Durable and idempotent |
| FR-03 fleet | Design.md, api.md | T04, AC-03 | Unknown distinct from healthy |
| FR-04 trends | Design.md, evaluation.md | AC-04 | Units/provenance visible |
| FR-05 ML | Models.md, evaluation.md | T10–T12, AC-05 | Real measured report |
| FR-06 workflow | state_machines.md, api.md | T07–T09 | Human approval and verification |
| FR-07 security | authentication_security.md | T01, T08 | Negative authorization tests |
| FR-08 replay | Integration.md, demo_script.md | T17 | Replay clearly labeled |
| FR-09 MLOps | MLOPS_structure.md | T14–T15 | Approved compatible artifact |
| FR-10 evidence | Design.md, Agent.md | AC-10 | Preserved decision lineage |
| FR-11 planning | backlog.md, PRD.md | AC-11 | Feasible constraints |
| FR-12 MCP | MCP_connections.md | T16, AC-12 | No elevated tool authority |
