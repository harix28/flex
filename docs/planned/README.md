# Planned Architecture Modules & Future Roadmap

This directory contains design specifications and architectural guidelines for system capabilities that are currently **planned** or in design specification, rather than implemented in the current codebase.

## Status Overview

| Capability | Current Status | Specification Document | Canonical Implementation (if any) |
|---|---|---|---|
| **Asynchronous Worker & Jobs** | Planned | [services.md](services.md) | None currently (stateless / synchronous FastAPI) |
| **CMMS & IoT Integrations** | Planned | [integrations.md](integrations.md) | Local NASA replay parser in [sentinel/data.py](../../sentinel/data.py) |
| **External Notifications** | Planned | [integrations.md](integrations.md) | None |
| **Model Context Protocol (MCP)** | Planned | [mcp.md](mcp.md) | None |
| **Automated MLOps Retraining & MLflow** | Planned | [mlops_extensions.md](mlops_extensions.md) | Manual MLOps CLI in [sentinel/mlops/cli.py](../../sentinel/mlops/cli.py) |
| **ML Probability Calibration & Horizon Classification** | Planned / Experimental | [ml_experiments.md](ml_experiments.md) | RUL regression in [sentinel/train.py](../../sentinel/train.py) |
| **Target Production API Contract** | Target Spec | [packages/contracts/production-target.openapi.json](../../packages/contracts/production-target.openapi.json) | Active API: [packages/contracts/experimental.openapi.json](../../packages/contracts/experimental.openapi.json) |

---

## Architectural Principles for Planned Modules

1. **Human-in-the-Loop Gate**: Model predictions and automated services must never autonomously approve work orders, commit equipment shutdowns, or promote production models without explicit authorized human review.
2. **Tenant Isolation**: All planned services (workers, integrations, MCP tools) must strictly enforce tenant boundaries and derive tenant context from authenticated sessions.
3. **Idempotency & Auditing**: Any future worker or integration queues must use idempotency keys and append-only audit tracking to prevent duplicate operations.
4. **Honest Capabilities**: Features are documented as planned until working implementation code and rigorous automated tests exist in the repository.
