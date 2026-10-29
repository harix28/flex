# Risk Register

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

| ID | Risk | Impact | Mitigation / owner | Residual limitation |
|---|---|---|---|---|
| R01 | Engine data presented as factory-general | Invalid claims | ML lead: scope and compatibility gate | Plant validation still needed |
| R02 | Component diagnosis overclaimed | Wrong inspection direction | ML/product: evidence labels | Exact cause may remain unknown |
| R03 | Leakage through windows/normalization | Inflated metrics | ML lead: engine partitions and causal tests | Small sample uncertainty |
| R04 | Sensor/mapping fault | Wrong machine warning | Registry owner: verified installations | Physical mistakes require review |
| R05 | Alert fatigue | Ignored important incidents | Operations: episodes/persistence/ownership | Policy needs pilot tuning |
| R06 | Missed or sudden failure | Unplanned downtime | Product: coverage/lead-time reporting | Not all failures predictable |
| R07 | Tenant/auth breach | Data exposure | Security owner: scoped auth/FKs/tests | Requires production review |
| R08 | Retraining on bad labels | Model degradation | ML lead: reviewed feedback/censoring | Intervention outcomes incomplete |
| R09 | Adapter/portal outage | Stale decisions | Operations: unknown status/recovery | Data may be unavailable |
| R10 | Scope expansion | Incomplete core demo | Project lead: P0 gates | Advanced features deferred |
| R11 | Unsupported claims of savings | Misleading business case | Product: assumptions vs observed values | ROI requires real records |
| R12 | Prompt injection or unsafe procedure | Unauthorized action | Agent owner: bounded tools/manual grounding | Assistant can be wrong |

Risk review is required at scope change, external integration enablement and pilot release. Owner names are roles until the project assigns actual people.
