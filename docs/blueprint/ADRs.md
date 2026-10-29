# Architecture Decision Records

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## ADR-001: modular monolith first — proposed

Context: limited team and tightly related workflows. Decision: API modules and a background worker share domain contracts; PostgreSQL outbox provides durability. Consequence: simpler deployment; independently scaling ingestion may require later extraction. Revisit when measured workload or team boundaries justify it.

## ADR-002: separate RUL and horizon risk — proposed

Context: RUL is not a calibrated probability. Decision: separate regression/classification outputs and evaluation. Consequence: additional calibration work, clearer semantics.

## ADR-003: explicit unavailable state — accepted design invariant

Context: missing data must not appear healthy. Decision: nullable outputs plus reason and freshness. Consequence: UI requires an unknown queue and cannot sort absent probabilities as zero.

## ADR-004: human-reviewed maintenance and releases — accepted design invariant

Context: operational decisions have consequences beyond prediction. Decision: draft-only assistant, role-gated approvals and model promotion. Consequence: no autonomous actuator/control integration.

## ADR-005: immutable model bundles — proposed

Context: weights alone cannot reproduce behavior. Decision: version transforms, feature schema, calibration and runtime alongside estimator. Consequence: larger artifacts, safe compatibility checks and rollback.

## ADR-006: replay as first adapter — proposed

Context: no live plant access supplied. Decision: explicit historical replay and synthetic operational metadata. Consequence: useful demo, no live integration claim.

## ADR-007: MCP is optional — proposed

Context: assistant integration should not block the portal. Decision: bounded adapter over authorized APIs. Consequence: extra convenience without a new data/control authority.

## ADR-008: tenant-scoped relational integrity — proposed

Context: app-only tenant filters can be bypassed by implementation mistakes. Decision: composite tenant FKs plus scoped service queries; optional tested row-level security later. Consequence: more verbose schema, stronger boundaries. RLS is not claimed implemented by the baseline SQL.
