# Platform accounts API — Checkpoint 1

Browser base path: `/platform-api`. Nginx removes this prefix and forwards to
Express on internal port 3000. `/api` still belongs to the assistant core; its
contracts and conversation bearers are unchanged. Express never queries `core`
or `language`. API responses use `Cache-Control: no-store`; errors contain only
`{"error":{"code":"…","message":"…"}}`. No SQL, password, cookie identifier or
stack is returned. There is no automatic replay of writes.

| Method / service path | Request / result | Access |
| --- | --- | --- |
| GET `/health` | Process health | Public |
| GET `/ready` | Database tables and runtime boundary check; 503 if unavailable | Public |
| GET `/auth/session` | `{user, csrfToken, expiresAt}`; creates an anonymous session if needed | Public; creation throttled |
| POST `/auth/register` | `{email, displayName, password}` → session, 201 | Anonymous CSRF session; analyst only |
| POST `/auth/login` | `{email, password}` → rotated session | CSRF session; throttled |
| POST `/auth/logout` | `{}` → 204; invalidates current session and clears cookie | CSRF session |
| GET `/users/:id` | `{user}` | Current user only, including administrators |
| PATCH `/users/:id` | `{displayName}` → `{user}` | Current user and CSRF |
| POST `/auth/password` | `{currentPassword, password}` → 204 | Current user and CSRF; revokes all account sessions |
| GET `/admin/access` | `{role:"admin", administrationAvailable:false, plannedCheckpoint:5}` | Active administrator; capability check only |

`user` is `{id, email, displayName, role, createdAt}`. Email is trimmed and
lowercased, valid and at most 254 characters. The displayed name is trimmed,
1–80 characters, without control characters. New passwords are 12–128 characters;
passwords are never trimmed. Names and passwords can be edited; login email is
unchanged in this checkpoint. Unknown fields (including `role`/`active` in public
registration/profile requests) are rejected. JSON requests are limited to 16 KiB.
Responses and incoming bodies use Zod runtime validation; database rows are
mapped to public objects explicitly.

## Sessions, CSRF and passwords

Passwords use Node scrypt with a random 128-bit salt, N=131072, r=8, p=1 and a
64-byte derived key. Hash records are versioned; comparisons use constant-time
equality. Unknown/disabled accounts have the same login error as an incorrect
password and perform password derivation. At most two password operations run
concurrently in one process (503 / Retry-After: 1 on saturation).

The 256-bit random session identifier is an HttpOnly, SameSite=Lax cookie named
`platform_session`, with path `/platform-api`, no Domain, and a maximum age of
12 hours. Only its SHA-256 digest is stored in PostgreSQL. Request inactivity
expires it after 30 minutes; the absolute 12-hour limit never slides. Authenticated
requests (including session refresh) renew only the inactivity deadline. Expired
records cannot authenticate before cleanup. Cleanup runs every 60 seconds.

`GET /auth/session` returns a CSRF value derived using HMAC-SHA256 keyed by the
opaque cookie secret. The value cannot be used to recover the cookie; it stays
in React memory. Every write, including registration, login and logout, requires
`Content-Type: application/json`, the configured exact `Origin`, and matching
`X-CSRF-Token`. Cross-site Fetch Metadata is rejected. The bootstrap response is
same-origin and uncached; no CORS access is enabled. Login/registration rotates
the identifier and deletes the prior session. There is no authentication token
in localStorage/sessionStorage. Assistant bearers remain separate in tab storage.

The default local configuration explicitly permits a non-Secure cookie only on
a loopback origin. Public or LAN account access needs HTTPS and
`PLATFORM_COOKIE_SECURE=true`; deployment/TLS setup is outside this checkpoint.
The optional HTTP phone binding supports the assistant at `/assistant`; it does
not enable account writes from the phone's different origin. No network settings
are changed. `trust proxy` is disabled for host development and limited to the
single private Nginx hop in Compose; Nginx replaces forwarded client headers.

Login limits are 30 attempts per IP and 10 per normalized email in a 15-minute
window, including successful attempts. Registration allows 10 per IP; anonymous
session creation 120 per IP; password changes 10 per account. Atomic PostgreSQL
upserts enforce limits across processes. Limit keys are SHA-256 digests, not raw
emails/IPs. Expired counters are removed every minute. 429 includes Retry-After.

## Authorization and persistence

`platform.users` stores unique account identities, hashes, analyst/admin roles,
active status and timestamps. `sessions` references users (nullable for CSRF-only
visitor sessions); `auth_throttles` stores expiring counters. `activity` stores
account registration/provisioning, profile/password and permission-change events,
with resource/actor references and bounded account-change details. No passwords,
tokens or patient conversations are logged. Account activity is retained without
automatic pruning in Checkpoint 1; general activity retention is still a later
administration decision. `schema_migrations` records version/checksum/application
time separately from the unchanged Python Alembic histories.

Every authenticated request joins back to current active account state. The SQL
trigger revokes sessions when role, active status or password changes. Both the
administrative CLI and trigger serialize last-active-administrator changes with
an advisory lock; the last active administrator cannot be disabled/demoted/deleted.
Profile APIs enforce ownership even for admins; the admin probe enforces role
at the backend. The browser guards are additional UI behavior. Checkpoint 2 adds
dataset ownership endpoints, documented in [dataset API](datasets-api.md).

Runtime `pharmacy_platform` receives schema USAGE; DML on users, sessions and
throttles; SELECT/INSERT on activity and sequence usage. It receives no DDL,
migration-table changes, activity deletion, role membership or peer-schema access.
The grant command refuses an unexpectedly privileged existing role and never
resets an existing role password. The service refuses an administrative runtime
identity. Password/status/role changes also work through explicit CLI operations;
the user-management screen remains Checkpoint 5 work. Disabling preserves the
account, activity and owned datasets. Future recipients' explicit access and
sharing controls follow D032; sharing is not implemented yet.

## Technical references

Implementation follows the official [Express middleware guidance](https://expressjs.com/en/guide/writing-middleware/),
[Node 22 crypto API](https://nodejs.org/docs/latest-v22.x/api/crypto.html),
[node-postgres transactions](https://node-postgres.com/features/transactions) and
[React Router declarative routing](https://reactrouter.com/7.18.4/start/declarative/routing).
Dependency versions are recorded in each npm lockfile.
