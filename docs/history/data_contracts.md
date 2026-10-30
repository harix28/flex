# Data Contracts and Quality Policies

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Canonical frame

See [JSON Schema](contracts/telemetry.schema.json) and [example](examples/telemetry.json). Required: source_event_id, stream_id, machine_id, event_time, data_mode, cycle, settings and readings. `received_at` and tenant ID are server assigned. Each reading identifies a sensor, raw numeric value and declared unit. Resolver determines the valid installation; clients cannot assert that an unverified mapping is trusted.

Live sensor IDs and replay sensor aliases use different namespaces. NASA measurements use dataset-native units until verified mapping exists. Do not label normalized values as degrees Celsius. NaN/Infinity are rejected before persistence.

## Quality outcomes

| Code | Action |
|---|---|
| valid | Eligible if history/model compatibility also pass |
| missing_required | Assessment unavailable |
| stale | Show last observation but not current healthy status |
| invalid_unit | Reject or apply explicitly configured conversion |
| unverified_mapping | Quarantine/reject; mapping verification task |
| duplicate | Return original receipt, no duplicate prediction |
| out_of_order | Store historical when valid; no regression of latest pointer |
| suspected_stuck | Quality warning and investigation; no automatic sensor diagnosis |
| unsupported_regime | Review/unavailable under model policy |

Freshness thresholds are asset/adapter policies. For demo live-like data a 120-second threshold may be a starting setting, not a universal machine rule. Replay freshness uses explicit replay clock and paused state.

## Feature consistency

Feature schema includes ordered names, units, transformations, window semantics, required sensors and model-compatible machine type. Input and model schemas must match exactly. Partial models require their own evaluated bundle; dropping missing features at runtime is forbidden.

## Reproducibility manifest

Record source URL, download time, SHA256 archive/file hashes, parser version, row/engine counts, split engine IDs, exclusions with reasons, condition handling and label policy. No true future RUL labels in online inference payload. Preserve raw observations alongside canonical conversion provenance.
