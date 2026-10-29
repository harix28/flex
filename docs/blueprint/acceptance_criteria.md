# Acceptance Criteria

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

| ID | Given / when | Then | Evidence required |
|---|---|---|---|
| AC-01 | Technician opens verified machine | Correct ID/location/sensor installation shown; mismatch blocked | Registry E2E + mapping tests |
| AC-02 | Duplicate, stale or wrong-unit input | Dedupe / explicit quality handling, never false green | Ingestion integration report |
| AC-03 | Mixed available and unavailable predictions | Valid risks ranked; unknown assets separately visible | UI and API assertions |
| AC-04 | Trend/evidence opened | Units, time/cycle, gaps, horizon and model version visible | Accessible UI review |
| AC-05 | Candidate evaluated | Engine-isolated real metrics and baseline comparison reported | Reproducible evaluation artifact |
| AC-06 | Draft progresses through repair | Correct roles/version checks; closure requires verification | State-machine E2E |
| AC-07 | Cross-tenant or unauthorized request | Denied without data leakage; appropriate audit | Security integration suite |
| AC-08 | Replay and sample workflow used | Explicit provenance; no live/repair claims | Demo checklist |
| AC-09 | New model released/rolled back | Gates and review enforced; full bundle identity retained | Release/rollback drill |
| AC-10 | Incident evidence changes | Timeline retains original and new evidence versions | Audit consistency test |
| AC-11 | Planner has limited slots/parts | Feasible suggestion or explicit unresolved constraints | Planner fixtures |
| AC-12 | Assistant requests scoped tools | Read/draft only, cited evidence, no approval bypass | MCP/agent negative tests |

P0 sign-off requires AC-01 through AC-08. P1/P2 acceptance is required only when the corresponding capability is enabled. No acceptance test has been run against an application by generating this documentation pack.
