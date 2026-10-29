# packages/contracts

Two separate contracts: experimental.openapi.json is generated from current code; production-target.openapi.json is the unimplemented target from supplied documentation.


## Phase 5 implemented extension (2026-10-26)

Current migration is `0004_replay`. `sentinel/ingestion/` implements persistent NASA
replay observations, immutable partition/file-version streams, atomic batches and
bounded history/quality APIs with the existing sessions, CSRF and tenant permissions.
The authoritative new contract is `docs/REPLAY_INGESTION.md`; Phase 6 integration
details are in `docs/PHASE5_HANDOFF.md`. Older phase-specific text above is historical.
Machine source bindings now accept `split: train|test` and optional `file_sha256`
(required for new train registrations). Different trajectory/version requires a new
machine. No prediction persistence or physical-device ingestion was implemented.
