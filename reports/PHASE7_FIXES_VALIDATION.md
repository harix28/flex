# Phase 7 corrective validation — 2026-10-26

Scope: the four gaps reproduced or identified in CODEBASE_ASSESSMENT.md. Work stayed
in the existing backend; no frontend, new dependencies, model changes or migrations.
Current migration remains0006_work_orders. Original migration revisions were untouched.

## Behavior corrected

1. Execution actions start/block/resume/complete recheck current execute permission and
   assignment. An assigned user demoted to viewer receives403; inactive membership404,
   disabled user401. Managers/admins require an active eligible assignee, otherwise409
   assignee_ineligible; reassignment preserves history. Missing assignment remains400.
2. Approval transactionally rejects outdated evidence with409 outdated_evidence. A
   manager must cancel the old draft, select/request a current prediction, create and
   review a fresh draft. The immutable evidence snapshot is preserved. Superseding
   prediction IDs at the same cutoff also mark an older work order outdated. Already
   approved work is not silently cancelled by later observations.
3. Both list route variants support inclusive created_from/created_to (timezone-aware
   timestamps) and due_from/due_to (dates), combined with existing filters and pagination.
   Inverted/invalid ranges return422; undated orders are excluded by due-date filters.
4. Notes require strict positive integer version. Append, version increment and audit
   commit atomically. Response includes top-level work_order_version. Missing version422,
   stale version409 version_conflict; competing note/edit/completion cannot both commit
   with the same expected version. Authorized terminal-order notes do not reopen state.

## Verification

Baseline before edits:213 existing tests passed during the preceding assessment; two
separate disposable-PostgreSQL probes reproduced unwanted HTTP200 outcomes.
Targeted run after fixes:37 passed,0 failed/skipped,1 existing warning,133.96seconds.
That run covered the initial19 new regression cases plus18 existing work-order tests.
A further regression for replacement predictions at the same cutoff was then added;
final full-suite results are recorded below.

New tests cover all four execution actions after role demotion, membership removal and
user disabling; manager reassignment of disabled assignees; stale approval with unchanged
history/version; fresh-draft recovery; date bounds, timezone equivalence, pagination,
tenant scope; strict note version, rollback of note/version/audit, and concurrent notes
versus notes/completion. A prior stale-evidence test silently skipped its main assertions
because FD001 test engine1 has no cycle32; it now unconditionally exercises cycles30->31.
Existing tests were preserved and their note clients updated for the intentional contract
change. Test-only simulated replacement prediction metadata is confined to a disposable
DB; model files and original prediction rows were never modified.

Real HTTP verification used the existing script and a disposable PostgreSQL database.
It exercised the full workflow plus the corrective scenarios using actual FD001 engine2
rows30/31 for stale evidence. Execution revocation was applied as test setup in that
isolated database; subsequent denied actions used real HTTP sessions. Actual outcomes:

| Check | Result |
|---|---|
| Normal draft/approve/assign/start/block/resume/note/complete/history |HTTP200|
| Completed-order version after versioned note |8|
| Outdated prediction draft approval |409 outdated_evidence|
| Execution after assigned technician became viewer |403|
| Versioned note |200,version incremented|
| Reusing stale note version |409|
| Combined created/due filters |200,exactly1 matching record|
| Cross-tenant read/write |404|
| Transition out of terminal state |400|
| Existing configured bundle/model/report/data verification |Passed|

Actual corrective response summary:

```json
{
  "outdated_approval_error": "outdated_evidence",
  "demoted_execution_status": 403,
  "stale_note_status": 409,
  "note_version": 5,
  "filtered_count": 1
}
```

Full sanitized evidence: [phase7-http.json](phase7-http.json). No credentials, cookies
or tokens are included. Model verification still matches the current trusted config.
`compileall` passed and `pip check` reported no broken requirements.

## Commands executed

From the existing repository, with SENTINEL_TEST_ADMIN_URL loaded privately from
.runtime/postgres.env (never printed):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_work_order_regressions.py tests/test_work_orders_postgres.py tests/test_work_orders_unit.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify-work-orders-local.py
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m compileall -q sentinel scripts tests
.\.venv\Scripts\python.exe -m pip check
```

Also regenerated both OpenAPI snapshots from create_app().openapi(). PostgreSQL
integration checks create/drop generated test databases; no SQLite substitution.

## Files and handoff

Changed sentinel/work_orders/{api,service,schemas}.py and sentinel/http_support.py;
added tests/test_work_order_regressions.py; updated tests/test_work_orders_postgres.py
and scripts/verify-work-orders-local.py. Updated both OpenAPI snapshots, workflow/role
and handoff docs, README/quickstart/status files, assessment follow-up and this report.
No migration, dependency, existing model or raw dataset edits.

Client change: POST notes must send version and consume work_order_version. Refresh
on409 rather than silently overwriting a concurrent edit. Approval has no implicit
outdated-evidence override. Refer to docs/MAINTENANCE_WORKFLOW.md and docs/PHASE7_HANDOFF.md.

This is a focused correction, not certification of every original Phase7 requirement
or production readiness. Background workers, frontend and real-device integrations
remain outside scope. Generic history retention/pagination, broader database audit
hardening and production deployment were not introduced.

## Final full-suite result

**233 passed,0 failed,0 skipped,0 blocked**,407.35seconds. Collection split:
121 database-independent and112 PostgreSQL tests. Two warnings were reported:
Starlette/httpx TestClient deprecation and Pydantic unused alias metadata in the existing
Phase6 concurrency test. No dependencies were changed to suppress them.

OpenAPI snapshot equality passed as part of the full suite. The test fixtures and HTTP
script completed their cleanup without reported teardown errors. A final catalog check
found one idle test-named database of unverified ownership; it was left untouched rather
than deleting an unattributed database. Credential scan found no configured local API
key/database password in source, tests, docs or reports. The development PostgreSQL
server remains running; its schema/data were not changed by this correction.
