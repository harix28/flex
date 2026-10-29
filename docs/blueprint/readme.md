# Meridian Sentinel — Project Documentation

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

**Start here.** This pack specifies a predictive maintenance portal and its ML/MLOps lifecycle. It is a build blueprint, not a runnable application or evidence of a trained model. Previously created narrated/interactive explainers are separate concept deliverables; their simulations are not implemented backend behavior.

Simple Hinglish: machine ko register karo, readings verify karo, risk estimate karo, technician ko evidence do, repair verify karo, aur model quality monitor karo.

## Reading paths

| Reader | Read in order |
|---|---|
| Product / project lead | [PRD](PRD.md), [scope and backlog](backlog.md), [implementation](project_implementation.md), [acceptance](acceptance_criteria.md) |
| Frontend engineer | [Design](Design.md), [API](api.md), [state machines](state_machines.md), [accessibility](accessibility.md) |
| Backend engineer | [Architecture](architecture.md), [database](database.md), [data contracts](data_contracts.md), [security](authentication_security.md), [integrations](Integration.md) |
| ML engineer | [Models](Models.md), [data pipeline](data_pipeline.md), [evaluation](evaluation.md), [MLOps](MLOPS_structure.md) |
| Agent / assistant developer | [Agent design](Agent.md), [MCP](MCP_connections.md), [repository instructions](AGENTS.md) |
| QA / operations | [Testing](testing.md), [debugging](QA_debugging.md), [deployment](deployment.md), [runbooks](runbooks.md) |

## Document map

Additional files: [setup](setup.md), [feature development](feature_development.md), [flowcharts](flowcharts.md), [observability](observability.md), [risk register](risks.md), [decision records](ADRs.md), [model card](model_card.md), [dataset card](dataset_card.md), [demo](demo_script.md), [glossary](glossary.md), [sources](sources.md), [traceability](traceability.md), [release checklist](release_checklist.md).

Machine-readable references: [OpenAPI](contracts/openapi.json), [telemetry JSON Schema](contracts/telemetry.schema.json), [example telemetry](examples/telemetry.json), [prediction example](examples/prediction.json), [database DDL](database/schema.sql), [configuration example](.env.example).

## How to use this pack

1. Extract the ZIP. Open [Flowcharts.html](Flowcharts.html) in a browser for 15 offline rendered diagrams, or open this file in a Mermaid-capable Markdown viewer. Individual editable diagram sources remain in the Markdown documents; exported SVGs are in `diagrams/`.
2. Review the design decisions in ADRs.md. Defaults are proposed choices, not external requirements.
3. Run `python scripts/validate_docs.py` from this directory. This validates local links, contract references and example structure; it does not test an application.
4. Implement the vertical slices in project_implementation.md. Create the application directories shown there; they are not included in this pack.
5. Record actual test results and measurements separately. Do not replace unmeasured values with illustrative numbers.

## MVP boundaries

One organization in the demo, with tenant-scoped storage designed from the start. C-MAPSS FD001 replay; machine/sensor registry; RUL and separately calibrated horizon classification; unknown status on unusable input; fleet/trends/evidence; reviewed draft work orders; basic model version tracking. Physical plant connectors, component classification, schedule optimization and MCP are extensions.

## Non-negotiable invariants

- Missing or invalid required data never becomes a healthy prediction.
- Operating cycles are not days. Event time and received time are different fields.
- Failure risk, data quality and business priority remain separate.
- Feature importance is not a proven cause. Known fault mode is not predicted diagnosis.
- No autonomous machine shutdown, repair approval or model promotion.
- Dataset replay, sample operational metadata and live data are visibly distinguished.
- Every model output includes artifact identity, input window and horizon.
