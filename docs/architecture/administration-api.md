# Administration and suspension — Checkpoint 5

Express owns these APIs under `/platform-api/admin`. Every route requires an
active authenticated administrator; state-changing requests also require the
existing exact Origin, HttpOnly session and session-bound CSRF header. The
service rechecks the actor's current role/status inside its transaction and
holds a shared account lock until completion. No patient-conversation, provider
credential or Python private-table access is added.

## API

| Method/path | Request | Result |
| --- | --- | --- |
| GET `/overview` | None | Counts of total/active users/admins, datasets/suspensions, versions, imported rows across versions, analyses/dashboards; latest 10 imports and 10 failures |
| GET `/users` | `page`, `search`, `role=all/admin/analyst`, `active=all/true/false` | 25 accounts/page, `hasMore`; exact account fields, permission revision, no hashes or sessions |
| PATCH `/users/:id/permissions` | `{revision,role,active,confirm:true}` | `{changed,sessionInvalidated}`; optimistic conflict 409; last active administrator 409 |
| GET `/datasets` | `page`, `search` (title/source/owner email), optional owner UUID, `state=all/available/suspended/archived` | 25 metadata summaries/page, ownership, source, dimensions and state |
| GET `/datasets/:id` | Optional version `page` | Metadata, 25 version summaries/page, latest 10 associated import receipts; no cells, profiles or raw upload bodies |
| POST `/datasets/:id/suspension` | `{revision,suspended,reason,confirm:true}` | 204; revision/state conflicts 409; reason required for suspension and restoration |
| POST `/datasets/:id/versions/:version/inspect` | `{reason,confirm:true,query}` | Bounded rows with original values, column definitions/profiles; successful audit insertion is required before returning content |
| GET `/activity` | `page`, optional actor UUID, exact action, kind, resource UUID, outcome, `from`/`to` calendar dates | 25 newest events/page, `hasMore`, limited structured details |

Lists default to page 1, cap the page number at 100,000 and fetch one extra record
to determine `hasMore`. Search is a literal case-insensitive substring of at most
160 characters, never interpolated SQL. Inspection reuses the typed dataset query
contract (page 1–25,000, page size 1–100, bounded search/filter/sort). Missing or
foreign version IDs return 404. There is no GET shortcut for inspection and no
durable inspection grant. Every page/search/sort submission requires explicit
confirmation and records actor, dataset, version, reason, page/size and returned
row count; cell values and the search text are excluded from the audit.

Administrative reasons are trimmed text of 3–1,000 characters without control
characters. The UI explains that they must contain no secrets/patient text.
All bodies are strict; extra fields and invalid dates/ranges (including PostgreSQL's
unsupported year zero) return 422. Admin
routes have a shared 300/account/15-minute throttle and inspection additionally
has 60/account/15 minutes. Existing SQL/pool/lock/request limits remain in force.
Network and database errors use the existing safe error envelope and no-store.

## Account lifecycle

Role/status changes invalidate every session of the affected account through the
existing database trigger, including self-changes. Re-enabling requires a fresh
login; old sessions do not revive. The API serializes permission changes with the
same transaction advisory lock as the explicit CLI and checks the last-active-
admin invariant before writing. The database trigger independently enforces it.
`permissions_revision` increments only on actual role/status changes, including
CLI changes, so stale forms receive 409 instead of overwriting another decision.
No-op API changes neither revoke sessions nor manufacture activity.

The UI offers disabling instead of deletion. Disabled owners keep their data and
saved resources. Active recipients keep explicit existing grants unless revoked
or their dataset suspended. Promotion/demotion requires confirmation and invalidates
the old session; the new role is available only after login. Admin rights do not
silently grant ordinary dataset ownership, editing, deletion or sharing rights.

## Dataset suspension lifecycle

Migration `0005_administration.sql` adds suspension state, last reason/time/actor,
permission revisions and activity indexes/actions. Earlier SQL/Alembic revisions
remain unchanged. Suspension/restoration takes the dataset row lock and checks
its current revision, then increments that revision and appends an audit event.

Suspension blocks ordinary version contents/profiles, row browsing, direct/saved
analytics, comparison sides, templates, widget previews/execution, saves/copies
using that source, new versions, metadata/archive/delete operations, new dataset/
result grants and onward approval. It applies to owners and recipients, including
admins using ordinary analyst APIs. Unauthorized callers still get 404 rather
than discovering suspension state. Authorized source access fails with 423
`dataset_suspended`; dependent UI shows source unavailability and clears failed
calculation results.

Dataset listing and permitted metadata remain visible with a suspension warning.
Configurations, immutable rows/versions, dependencies, grants and approvals are
preserved. Owners may revoke existing grants/approvals and remove or repair saved
configurations without using a suspended source. Administrators can still perform
explicit, logged inspection. Restoring use rechecks existing permissions; it
recreates neither revoked grants nor revoked onward approvals. Requests begun
after a committed decision observe it; already-running snapshot reads can finish
against their prior consistent snapshot. Writes/source locks serialize with the
moderation change. No ongoing inference or source import is started.

## Activity and persistence

The event filter includes actor, action, resource type/ID, success/failure and a
UTC inclusive calendar range (`to` is implemented as the next day's exclusive
boundary). Activities are append-only for the runtime. Retain them without an
automatic purge for this local project; any later retention/deletion policy
requires an explicit decision. There is no delete-account or delete-audit API.
Details expose only known primitive fields and role/status summaries.

CSV validation failures now record outcome `failure`; the migration corrects
that flag on existing `import.validation_failed` events while preserving their
IDs, actors, timestamps and details. Version publication also records explicit
`dataset.version_created` alongside the existing import-success event. Overview
failure counts describe recorded business failures, not every network/HTTP error.

The maintained backup already retains complete users/datasets/activity and their
relationships, so new columns survive without a new dump format. Sessions,
throttles, staging uploads and temporary patient history remain excluded. Restore
requires explicit runtime grants; suspension and permission state must be tested
after restore without changing the source database.

The locking design follows [PostgreSQL 17 explicit locking](https://www.postgresql.org/docs/17/explicit-locking.html).
See [current evidence](../validation/platform-checkpoint-5.md) and
[operations](../operations/administration.md). Checkpoint 6 delivery is separate.
