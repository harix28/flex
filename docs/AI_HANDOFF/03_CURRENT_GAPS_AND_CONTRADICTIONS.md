# Current gaps, contradictions and evidence boundaries

This register supersedes broad historical status claims for the inspected working-tree snapshot. Findings are static inspection unless a specific executed check is stated. It does not authorize an AI to fix unrelated work automatically.

| ID | Observation | Evidence location | Practical consequence / next verification |
|---|---|---|---|
| G01 | `sentinel/train.py` is zero bytes and locally modified | File size; current pytest collection | `metrics` and `weights` imports fail. Resolve ownership/history of the change before restoring. Do not overwrite another person's work. |
| G02 | Current test collection is not green | `pytest --collect-only -q`: 286 collected, 3 collection errors, exit 2 | No claim of a current full passing suite. Affected modules: all-subsets training, classification and RUL experiments. |
| G03 | MCP has no verified principal/membership binding | `sentinel/mcp_server.py`, direct organization ID to database transactions | Tenant IDs supplied as arguments are not authorization. Add a reviewed identity/scope boundary before exposing data. |
| G04 | MCP calls service APIs that do not match current modules | Registry is a `Registry` class; ingestion exports `history`/`quality`; work orders export draft functions | Advertised tools cannot be assumed executable. Tests currently cover handshake/list/unknown tool, not actual data access/drafting. |
| G05 | MCP evidence field names differ from prediction output | Uses predicted_rul/priority/cutoff_cycle/model_bundle_sha256 versus persistent-service fields | Field translation needs correction and integration tests. Hardcoded assistant actor is not a provisioned authorized principal. |
| G06 | Notification code simulates successful delivery | `notifications/dispatcher.py`: no network sender; writes HTTP 200 into local record | Do not describe alerts as sent, delivered, durable or receiver-acknowledged. |
| G07 | Notification state is process-local | Module dictionaries for subscribers, secrets, cooldown and history | Lost on restart; inconsistent across processes; no durable queue linkage. Cooldown can suppress events even before a subscriber delivery succeeds. |
| G08 | New notification mutations omit CSRF verification | `notifications/api.py` context helper authenticates/authorizes only | Align with established write boundaries and test rejection cases. URL field is a plain string despite an unused HttpUrl import. |
| G09 | Job HTTP submit uses `actor['id']` | `jobs/api.py` versus `auth/context.py` returning `user_id` | Submission path is inconsistent; do not infer CLI validation covers it. Random source IDs also prevent caller-controlled retry deduplication. |
| G10 | Job HTTP writes omit explicit CSRF check and validated lower limit | `jobs/api.py` | Add reviewed input limits, write boundary and idempotency semantics. The API predictor may be multi-subset while CLI fleet uses the configured primary. |
| G11 | PDF API invokes nonexistent registry helper | `audit/api.py` uses module-level get_machine; registry implementation is class-based | Route registration is not a successful downloadable dossier. |
| G12 | PDF schema defaults can falsify evidence | `audit/dossier.py` uses legacy prediction keys and defaults RUL to 0.0 | Map real fields, preserve unknowns and test unavailable states before use. Catch-all fallbacks can hide errors. |
| G13 | PDF is not cryptographically signed | Matplotlib drawing, printed hashes and blank signature lines | “Cryptographic”/“tamper-evident” docstrings are unsupported. No PDF digital-signature/certificate verification implemented. |
| G14 | PDF sensor/history representation needs validation | First 300 observations, static sensor labels, AMM/FAA-style wording | Confirm cutoff alignment, units and procedure provenance; do not equate a template with certified instructions. |
| G15 | New import dependency not clearly declared | API imports audit module; audit imports matplotlib; direct requirements omit it | Verify a clean dependency install and startup. Local installed packages are not reproducibility evidence. |
| G16 | Current API discovers known candidate models | `inference.py: load_multi_predictor`; API construction | Old “only FD001 serves” / “candidates never loaded” statements can be stale. Record actual configured/loaded identities. |
| G17 | Worker and API may have different subset coverage | Queue dispatcher uses primary Predictor; API uses MultiPredictor | Document/test intended behavior before aligning them; do not auto-promote candidates to make outputs match. |
| G18 | Classifier card is now mounted | `MachineDetailPage.tsx` imports/renders LifetimeStageCard | Earlier handoff notes about missing page integration are superseded. Horizon probabilities/physical diagnosis remain absent. |
| G19 | Feature descriptions conflict | `features.py`: last/mean/std/slope = 96; some prose says min/max | Current code/schema govern. Offline engineered97 is a distinct feature family. |
| G20 | Root summaries lag several changes | README still says seven migrations, planned workers, missing EDA | Current head is 0009; queue/fleet exist; offline EDA/selection exists but shared training import is currently broken. |
| G21 | “Active” UI rows can be static candidate descriptors | `ModelMonitoringPage.tsx` | Read backend model-info and activation evidence before claiming an artifact is active. |
| G22 | Authentication prose and proxy code differ | Old auth doc says forwarded headers disabled; current serve/public entrypoints enable them | Reconcile proxy topology and trust; neither old prose nor local HTTPS assumptions suffice. |
| G23 | Current schema is not a live schema inspection | `db.REVISION`, migration files | No application migration query was run during documentation. Code head does not prove deployment head. |
| G24 | Job worker deployment is not demonstrated | Compose has no worker service; earlier reports explicitly did not install one | Start/manage it only through an authorized rollout. Add health/monitoring/supervision intentionally. |
| G25 | RLS/distributed auth controls remain incomplete | Auth service scoping, process-local limiter, migration review | Existing role boundaries do not establish OIDC/SAML, RLS or Redis limiting. |
| G26 | Live integrations and durable planning remain open | No live MQTT/OPC-UA/CMMS adapters; new planning modules use seeded in-memory catalogs/rosters | Require real external contracts, persistence, provenance and human gates. |
| G27 | Maintenance memory is proposed | Conversation and master guide section 29 | No outcome/verification/case-retrieval schema or measured plant efficacy exists yet. |
| G28 | Planning uses hardcoded demo stock, prices and staff | `planning/inventory.py`, `planning/shifts.py` | Not warehouse/HR connectivity, real pricing or certified qualification evidence. State is lost on restart. |
| G29 | Readiness calls a nonexistent service helper | `planning/service.py`: work_orders_service.get_work_order | Repair integration and test against real tenant-scoped work orders. |
| G30 | Readiness can contradict its blockers | Off-duty assigned technician adds blocker without setting is_ready false; qualification matching unions candidates across tasks | Do not treat READY_FOR_EXECUTION as clearance. Require complete task/parts/assignee coverage tests and preserve approval gates. |
| G31 | Planning PATCH routes omit normal CSRF enforcement | `planning/api.py` | Apply established mutation boundary; model actual roster memberships, clock-based shifts and inventory reservations. |

## Benchmark contradictions that are not necessarily bugs

MAE 16.79, 12.45 and 16.14 for FD001 belong to different historical comparisons/populations. Do not pick the smallest number as the product accuracy. Combined classifier row accuracy 90.2457% and engine-balanced accuracy 92.72% use different aggregation. All-cycle, last-cycle and fixed-window evaluation differ. A rejected cap-125 candidate remains rejected unless new reviewed evidence changes that decision.

The same applies to test counts: historical suites with 159 passed/125 skipped, earlier targeted 27/35 passes and today's 286 collected/3 collection errors are different facts. Collection is not execution; skips are not passes. This pack retains those distinctions.

## Prioritized response to these findings

First establish a coherent, importable working tree and ownership of the empty trainer change. Then validate the core API in a clean dependency environment. Repair prototype auth/service contracts before connecting external users or notification networks. Validate PDF evidence and labeling before compliance presentation. Only then extend deployment, scheduler, ingestion or real integrations. This is a suggested dependency order, not an instruction to modify the whole project without a concrete user request.
