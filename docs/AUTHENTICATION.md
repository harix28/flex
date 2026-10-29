# Phase 3 authentication and tenant isolation

Implemented backend-only local password authentication; **not production-ready**.
The earlier OIDC blueprint remains a future option. This phase explicitly follows
the requested local email/password design. Existing OIDC issuer/subject columns and
identities are preserved. Local users receive issuer `urn:meridian:local` and a UUID
subject; no external account is silently converted. No public registration, invitations,
email verification, password-recovery emails or frontend has been added.

## Setup and explicit provisioning

Use Python 3.12 and pinned requirements. Reuse the native PostgreSQL setup:

```powershell
.\.venv\Scripts\python.exe scripts/postgres-local.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -m sentinel.db upgrade --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.db check --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.auth bootstrap --env-file .runtime/postgres.env
```

Bootstrap prompts for email, unique organization slug, organization name, display name,
and a password entered twice through `getpass` with echo disabled. It refuses non-TTY
password input, accepts no password argument, and supplies no default credentials.
Choose a unique 2–63 character lowercase slug (letters, numbers, hyphens). Email is
validated, trimmed, ASCII-normalized and lowercased as a case-insensitive product policy;
provider-specific dot/plus aliases are not collapsed. Unicode local parts are unsupported.
Display/organization names are bounded. Password length is 12–128 characters, with no
silent trimming or truncation. Argon2id uses argon2-cffi, 64 MiB, 3 iterations and
parallelism 4, random salts, and automatic safe rehash on successful login.

Bootstrap is transactional: duplicate slug/email fails without creating partial
organizations/users. It never adopts or overwrites an existing identity, resets a
password, or runs on server startup. Existing Phase 2 SAMPLE identities have no local
password and cannot log in. The development database has not been given a default admin.

Other privileged local operator commands:

```powershell
.\.venv\Scripts\python.exe -m sentinel.auth create-user --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.auth reset-password --env-file .runtime/postgres.env
.\.venv\Scripts\python.exe -m sentinel.auth disable-user --env-file .runtime/postgres.env
```

`create-user` returns an existing-user ID for an organization admin to add; it creates
no membership. The CLI is a database-operator interface, not a platform privilege
available to organization admins over HTTP. Disable and password reset revoke sessions;
disable refuses to strand an organization's last usable active administrator.

## Configuration and startup

Settings retain CLI > process environment > private `.env` precedence. Blank process
values do not fall back. Never print or commit private environment files.

| Variable | Default / validation |
|---|---|
| DATABASE_URL | Required when auth enabled; existing PostgreSQL psycopg format |
| SENTINEL_AUTH_ENABLED | false; explicit true required for application login |
| SENTINEL_AUTH_LOCALHOST | false; true allows HTTP/non-Secure cookies only for loopback hosts and origins |
| SENTINEL_AUTH_ORIGINS | Exact comma-separated origins; required when enabled; HTTPS unless explicit localhost mode |
| SENTINEL_SESSION_SECONDS | 28800; absolute lifetime 60–86400 seconds |
| SENTINEL_LOGIN_LIMIT | 10; 1–100 attempts per IP and per normalized email per window |
| SENTINEL_LOGIN_WINDOW | 300; 1–3600 seconds |
| SENTINEL_LOGIN_GLOBAL_LIMIT | 100; 1–1000 attempts per process per window |

Local PowerShell example; choose the same port as your existing server configuration:

```powershell
$env:DATABASE_URL = (Get-Content -LiteralPath .runtime/postgres.env | Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13)
$env:SENTINEL_AUTH_ENABLED = 'true'
$env:SENTINEL_AUTH_LOCALHOST = 'true'
$env:SENTINEL_AUTH_ORIGINS = 'http://127.0.0.1:8001'
.\scripts\start-local.ps1 -Port 8001
```

Stop the API with Ctrl+C. Stop only the isolated cluster with
`python scripts/postgres-local.py stop --bin "C:\Program Files\PostgreSQL\18\bin"`.
Data remains. Remove process overrides when finished or close that terminal. Authentication
routes return controlled 503 when disabled/unavailable. Invalid required settings fail at
app construction; database connectivity is represented by `/health/database`, separately
from process liveness and loaded-model readiness.

The canonical server stays loopback-only and explicitly disables proxy-header trust.
X-Forwarded-For/Proto cannot change the acting client or bypass transport enforcement.
Outside explicit localhost mode, auth requests require HTTPS and cookies are Secure.
A production TLS/proxy topology must be reviewed/configured separately; do not simply
turn on forwarded headers or deploy with the localhost override. No production proxy
or deployment readiness is claimed.

## Cookies, CSRF and example flow

Login uses a 256-bit random opaque session token in a host-only, HttpOnly, SameSite=Lax,
Path=/ cookie. Secure mode uses `__Host-meridian_session`; localhost mode uses
`meridian_session`. Only SHA-256 digests of session and CSRF tokens are stored in
PostgreSQL. Tokens are never accepted in URLs or logged. Session cookies are issued
only after commit. A replacement login revokes the previous browser session and uses
a fresh token. Sessions have an absolute expiry, no sliding extension.

All login requests require JSON, an exact allowed `Origin`, and `X-CSRF-Protection: 1`.
This is the deliberate login-CSRF defense: HTML forms cannot supply the custom header;
foreign origins cannot pass the explicitly restricted CORS preflight. Missing/null/
unlisted Origin and cross-site Fetch Metadata are rejected. There is no wildcard CORS.
Credentialed CORS allows only configured origins, the four implemented methods, and
Content-Type / X-CSRF-Token / X-CSRF-Protection request headers.

Login response includes a separate random CSRF token. Keep it in browser memory and
send it in `X-CSRF-Token` plus allowed Origin on logout, password and membership mutations.
Server compares its digest against the session-bound digest with constant-time comparison.
After reload, `GET /api/v1/auth/csrf` requires the session cookie, allowed Origin and
`X-CSRF-Protection: 1`; it rotates the CSRF token and returns the new value. Other tabs
must refresh their token. Tokens never go in query strings or localStorage.

Browser/API-client pseudocode (password is entered securely by the client, not hardcoded):

```javascript
const base = '/api/v1';
const login = await fetch(base + '/auth/login', {
  method: 'POST', credentials: 'include',
  headers: {'Content-Type': 'application/json', 'X-CSRF-Protection': '1'},
  body: JSON.stringify({email, password})
}); // Browser supplies Origin; never log response headers or credentials.
const {csrf_token, organizations} = await login.json();
const me = await fetch(base + '/auth/me', {credentials: 'include'});
await fetch(base + '/auth/logout', {
  method: 'POST', credentials: 'include', headers: {'X-CSRF-Token': csrf_token}
});
```

Non-browser clients must explicitly supply an allowed Origin, retain cookies in memory,
and follow the same CSRF flow. The API does not expose raw session tokens in JSON.
Generic login failures do not disclose whether an email exists, is disabled, or lacks
membership; unknown identities use a dummy Argon2 verification. Ordinary malformed
schema returns sanitized 422 without echoing passwords or request bodies.

## Implemented endpoints and tenant boundary

| Endpoint | Access |
|---|---|
| POST /api/v1/auth/login | Allowed Origin/custom header, rate-limited credentials |
| GET /api/v1/auth/me | Current active user + valid unexpired, unrevoked session |
| GET /api/v1/auth/csrf | Valid session + allowed Origin/custom header |
| POST /api/v1/auth/logout | Session + CSRF; revokes server-side and clears cookie |
| POST /api/v1/auth/password | Session + CSRF + current password; revokes all sessions |
| GET /api/v1/organizations/{tenant_id} | Current active membership, any implemented role |
| GET /api/v1/organizations/{tenant_id}/members | Current organization admin; up to 100 results with next_offset |
| POST /api/v1/organizations/{tenant_id}/members | Admin + CSRF; existing user_id, roles, active |
| PATCH /api/v1/organizations/{tenant_id}/members/{member_id} | Admin + CSRF; roles and active only |
| DELETE /api/v1/organizations/{tenant_id}/members/{member_id} | Admin + CSRF; disables membership, preserves history |

Every tenant ID in the route is checked against the user derived from the verified
session. Membership/roles are read from PostgreSQL on each operation, not copied into
the session. A non-member gets 404; a member without permission gets 403; missing,
expired, revoked or disabled-user sessions get 401. Membership record lookups and
updates include tenant ID, and strict input schemas reject mass assignment.

The organization row is locked for membership mutations, privileges are rechecked after
the lock, and last-admin validation plus mutation and audit commit together. Concurrent
self-demotions cannot remove both admins. An inactive user or one without a local
password cannot serve as the remaining usable administrator. Disabling a user through
the operator command takes tenant locks in stable order and enforces the same invariant.
Direct privileged SQL is outside application authorization and can still alter data.

Password-hash changes (including rehash) and user disabling have a database trigger to
revoke existing sessions even when performed by operator SQL. Membership removal or
role changes immediately affect subsequent organization requests; a global session may
continue accessing the user's other memberships. In-flight read requests are not canceled.
Phase 4 registry routes reuse this same session/membership/CSRF boundary; see MACHINE_SENSOR_REGISTRY.md. Phase 2 composite foreign keys and tenant-scoped registry
repository remain in place for the next backend slice.

## Rate limiting, audit and limitations

A bounded, synchronized in-memory limiter enforces per-IP, per-email-digest and global
attempt budgets before password hashing. Successful and failed attempts count. HTTP 429
includes Retry-After. Counters reset on process restart and are not shared across workers;
use a reviewed distributed limiter/edge policy before scaling. Targeted lockout and
shared-IP contention are tradeoffs of this simple phase. No raw email or IP is persisted
for rate limiting. Authenticated password-change attempts do not have a separate rate
limiter yet; they require a valid session, CSRF and current password.

Minimal database audit events record action, actor/target UUIDs, organization when
applicable, timestamp and existing request ID. Login success/failure/rate-limit, logout,
password change, provisioning and membership changes are recorded. They contain no
password, session/CSRF token, raw request body, email or IP. Failed credential/rate-limit
audits commit before returning their error; successful mutations and audit are atomic.
Malformed/CSRF-rejected attempts are represented by safe HTTP status/request-ID logs,
not additional database audit records. Database failure fails closed with sanitized 503.

RLS, production least-privilege grants/append-only audit role, distributed limits, MFA,
email verification/recovery, OIDC, idle timeout, session/audit retention jobs, production
backup restore and external security review remain pending. Local operator DB credentials
are privileged. XSS protection and frontend token handling require review when a UI exists.

The local experimental `X-API-Key` remains limited to `/api/v1/experimental/*`. It does
not authenticate application routes, grant memberships, or imply an organization identity.
Model/replay contracts, trusted manifests and unavailable outputs are unchanged.

## Migrations and verification

`0002_auth` follows immutable `0001_registry`, adds nullable unique normalized email,
password hash, active state, optional unique organization slug, session/audit tables,
indexes and revocation trigger. Old external-only identities remain intact. Legacy
`manager` becomes `plant_manager`. Legacy `ml_engineer` cannot map safely into the four
requested roles: upgrade aborts transactionally until an operator explicitly resolves
those memberships. No role is silently promoted or discarded.

Downgrading Phase 3 destroys local email/password/active state, slugs, sessions and audit
records, and maps plant_manager back to manager. It retains Phase 2 registry records.
Use downgrade only on disposable tests, or a reviewed backup/restore plan. No automatic
reset/downgrade exists. See [database operations](../database/README.md).

Real PostgreSQL tests use fresh randomly named disposable databases. Run with explicit
SENTINEL_TEST_ADMIN_URL as documented there; missing URL visibly skips these tests.
For real socket verification with two organizations and the existing model:

```powershell
$env:SENTINEL_TEST_ADMIN_URL = (Get-Content -LiteralPath .runtime/postgres.env | Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13)
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify-auth-local.py
Remove-Item Env:SENTINEL_TEST_ADMIN_URL
```

The script migrates only a newly generated test database, creates random disposable
credentials, starts a temporary loopback HTTP server, records sanitized status/prediction
evidence and cleans up its server/database. It never prints passwords/cookies/CSRF tokens.
See [Phase 3 validation](../reports/PHASE3_VALIDATION.md).

Design references: [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[OWASP CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).


Phase 4 extracted the common checks into sentinel/auth/context.py and added registry
permissions without changing login, cookies or session semantics. Organization-scoped
machine/sensor/installation routes never accept experimental API keys as authentication.


## Phase 5 implemented extension (2026-10-26)

Current migration is `0004_replay`. `sentinel/ingestion/` implements persistent NASA
replay observations, immutable partition/file-version streams, atomic batches and
bounded history/quality APIs with the existing sessions, CSRF and tenant permissions.
The authoritative new contract is `docs/REPLAY_INGESTION.md`; Phase 6 integration
details are in `docs/PHASE5_HANDOFF.md`. Older phase-specific text above is historical.
Machine source bindings now accept `split: train|test` and optional `file_sha256`
(required for new train registrations). Different trajectory/version requires a new
machine. No prediction persistence or physical-device ingestion was implemented.
