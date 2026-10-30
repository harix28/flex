# Start here: Meridian Sentinel AI handoff

This pack explains the project and supplies the implementation evidence needed to go beyond an overview. It reflects a local working-tree snapshot dated 30 October 2026, including in-progress changes. It is not a production-readiness assertion.

## What to give another AI

For one-file upload, use `MERIDIAN_SENTINEL_AI_CONTEXT.md` in the repository root. It combines the main explanation, current gap register, AI instructions and generated technical reference. For exact implementation detail, upload `docs/MERIDIAN_SENTINEL_AI_HANDOFF.zip`, which also contains a sanitized source/documentation snapshot and manifest.

No finite context window can ingest an arbitrarily large project at once. If the AI cannot accept the complete file/archive, provide these in order:

1. `00_READ_FIRST.md` and `03_CURRENT_GAPS_AND_CONTRADICTIONS.md`.
2. `01_PROJECT_MASTER.md` and `04_AI_WORKING_INSTRUCTIONS.md`.
3. `02_TECHNICAL_REFERENCE.md` and `runtime.openapi.json` for interface/schema questions.
4. The relevant files from `source_snapshot/` for the requested change.
5. `05_VALIDATION_AND_PROVENANCE.md` and the applicable historical reports for evidence.

The manifest gives source paths and SHA-256 hashes, exported-file hashes, Git state, omissions and whether input files changed during export. Historical source documents remain historical even when included in this newly generated archive. Their assertions do not override the current gap register.

## Suggested prompt to paste with the pack

> Understand Meridian Sentinel using the attached handoff. Start with the current-gap register, then the master guide. Distinguish verified code, dated test evidence, incomplete prototypes, simulated behavior and planned features. Before changing a module, inspect its bundled source, contracts, migrations and relevant tests. Preserve tenant isolation, truthful unknown states, causal ML inputs, immutable evidence and human-only approval gates. Do not claim deployment, real notifications, certified maintenance procedures or successful tests without evidence. Respect uncommitted work. First explain the parts relevant to my request and identify any assumptions that the snapshot cannot resolve. My task is: [insert task].

## Scope and deliberate exclusions

The pack covers selected first-party source, tests, configuration templates/manifests, migrations, API contracts, operational docs, blueprint/planned/history docs, text evaluation reports and safe saved model metadata. An inventory records selected-but-not-embedded file paths and reasons. Module/function/route/test catalogs and complete migration sources supplement the narrative. `ARTIFACT_INVENTORY.json` records local data/model artifact names and sizes without including raw data or weights.

Actual secrets, environment files, TLS keys, cookies, private logs, local databases, installed dependencies, model binaries, raw datasets, prediction-row exports, compiled frontend bundles and older ZIP/media exports are deliberately not copied. These are not needed to explain the architecture and must not be uploaded indiscriminately. Their categories and reconstruction/prerequisite roles are documented. Sanitized source is reference material; redaction may make some snippets non-executable.

This is comprehensive within the declared scope, not a promise that undocumented external infrastructure or every future change is known. The archive is not a runnable installation. Run-time credentials, data, model artifacts, identity-provider configuration and deployment state remain separate controlled inputs.

## Most important snapshot warnings

- `sentinel/train.py` is empty; current test collection fails in three dependent modules.
- MCP code exists but lacks a verified tenant identity boundary and has service/field mismatches.
- Notification dispatch is an in-memory simulation that does not make outbound HTTP calls.
- PDF export code exists, but current wiring/fields are inconsistent and no digital signature is implemented.
- New job HTTP submission uses the wrong authenticated-principal key and omits the normal CSRF check.
- New planning modules are seeded in-memory demos with readiness/service-contract gaps, not durable warehouse or staff scheduling integrations.
- The classifier card is now mounted; old notes claiming it is not mounted are stale.
- Earlier 27/35-test reports describe earlier targeted runs, not a green current full suite.
- The durable CLI worker/fleet implementation is distinct from the newer incomplete HTTP wrapper.
- Application deployment, running daemon, physical connectivity and certified operational use are not established by this documentation task.
