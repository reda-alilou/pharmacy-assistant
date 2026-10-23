# Dataset lifecycle and exploration — Checkpoint 2

Express owns all dataset operations in `platform`. Browser routes are `/donnees`,
`/donnees/importer`, `/donnees/imports/:id` and `/donnees/:id`. The dataset URL
accepts `version=<uuid>` and `tab=overview|data|columns|quality|versions`, so direct
URLs and refresh retain the selected version/view. Dataset, import and version
APIs require an active account and account-session protections. Mutations remain
owner-only; Checkpoint 4 read routes also accept an explicit dataset grant. A
result-only grant does not authorize these dataset routes.
Administrators have no implicit access to another owner's dataset contents.
Sharing and administrative inspection remain later work. Checkpoint 3 adds
[analytical tools and private saved definitions](analytics-api.md).

## API

Gateway base path `/platform-api` is removed before Express. Account routes and
the assistant's independent `/api` contracts remain unchanged. All results are
uncached. Writes and query POSTs require exact Origin and X-CSRF-Token; no POST
is automatically repeated. Unknown fields/columns/operators are rejected.

| Method / Express path | Contract / behavior |
| --- | --- |
| GET `/datasets/limits` | Current supported limits |
| POST `/imports` | Raw CSV bytes, `Content-Type: application/octet-stream`, URI-encoded basename in `X-Filename`; returns receipt ID/revision/expiry, 201 |
| GET `/imports/:id` | Private preview/configuration/validation/status; imported receipts return the published dataset/version link |
| POST `/imports/:id/preview` | `{revision, options}`; reparse and infer types, clear prior validation, advance revision |
| POST `/imports/:id/validate` | `{revision, options, columns?}`; validate the complete file and advance revision; errors are a valid report response, never a partial import |
| GET `/imports/:id/report` | Download bounded validation CSV (row, source line, column, code, reason); no cell values in the report |
| DELETE `/imports/:id` | `{}`; cancel staging only, 204 |
| POST `/imports/:id/publish` | `{revision, metadata, datasetId?}`; validated immutable version/new private dataset, 201; repeating an already-published receipt returns its original version |
| GET `/datasets?archived=false&page=1` | Owner-only listing, 25 per page with `hasMore` |
| GET `/datasets/:id` | Metadata, optimistic revision and latest 25 version descriptors |
| PATCH `/datasets/:id` | Full metadata plus `{revision, archived}`; stale revisions fail with 409 |
| GET `/datasets/:id/versions?page=1` | Version history, 25 per page |
| GET `/datasets/:id/versions/:version` | Immutable version descriptor, column definitions and full-version profiles |
| POST `/datasets/:id/versions/:version/rows` | Bounded query described below; full filtered count and paginated rows/original cells |
| GET `/datasets/:id/dependencies` | Versions, dependency/share list, current revision and `canDelete` |
| DELETE `/datasets/:id` | `{revision, confirmTitle}`; only after dependency review and exact title confirmation; dependencies block deletion |

`metadata` is `{title, description, category, source, observationDate}`. Title is
1–160 trimmed characters, description at most 4000, category 100, source 500;
observationDate is a valid ISO date or null. Metadata is user-declared provenance,
not a claim of source verification. Appending a version preserves existing
dataset metadata and all prior versions. No owner-change API exists.

`options` contains delimiter (`auto`, comma, semicolon or tab), encoding (`utf-8`
or explicit `windows-1252`), `decimalSeparator` (point/comma), `trim` and exact
case-sensitive `missingMarkers`. Defaults are automatic delimiter detection,
UTF-8, decimal point, no trimming and only the empty string as missing. BOMs are
handled. UTF-16/binary NUL input is rejected with corrective guidance. Detection
uses separators outside quoted fields in the header; users can correct it.
Quoted separators/newlines and doubled quotes are supported. Blank records are
not silently dropped. Header-only/empty files, duplicate/blank/control-character
headers and inconsistent row widths fail validation.

Column definitions retain `id`, `originalName`, displayed `name`, `type`,
`dateFormat` (`iso|dmy|mdy`) and `booleanFormat` (`true-false|oui-non|1-0`). IDs are
derived from the exact original header and survive column reordering. Display
names trim header-edge whitespace; duplicate names are rejected ignoring case
and edge whitespace. Source headers are preserved. Types are proposed from 200
rows; any leading-zero integer-like value anywhere in a column keeps its default
type text. Every cell is checked before publication. The selected interpretation
is saved with the version; no malformed value becomes null silently.

Integers/decimals are exact canonical decimal **strings** in JSON, with at most
38 significant digits and 12 fractional digits. No JS floating-point conversion,
thousands separators, currency suffixes, NaN, infinity or exponent syntax.
Users can keep identifiers as text. Dates require explicit ISO, DD/MM/YYYY or
MM/DD/YYYY and a valid calendar date in years 1000–9999; ambiguous slash dates
remain text until the user selects a convention. Date/time requires ISO seconds
and an explicit timezone, with up to six fractional digits. It normalizes to UTC
with six digits while preserving microseconds and original input. Boolean tokens
use the selected convention; numeric 0/1 is not inferred as boolean automatically.

## Bounds and state

All limits apply together: 10 MiB input; 25,000 data records; 100 columns;
1,000,000 cells; 16,384 UTF-16 units per cell; parser record buffer limit 262,144.
CSV payloads are raw bytes; dataset configuration/query JSON is limited to 128 KiB
(accounts retain 16 KiB). Preview contains at most 20 rows, row queries at most
100. At most five unexpired uploads per account, each retained for one hour.
Upload is throttled to 10/account/15 minutes; preview/validation to 60/account/15
minutes. A process admits one parse/validation/publication at a time, returning
429 / Retry-After: 1 when occupied. No automatic queue, retry or inference runs.
These bounded local-demo limits were measured; they are not production SLAs.

Validation counts all issues but retains/reports at most the first 1000. The UI
and API expose the total and truncation flag and tell users to correct and rerun.
The downloadable CSV escapes spreadsheet formula prefixes in user column labels.
Original user files are not rewritten or corrected. Parsing errors never publish
any dataset/version/row. Failures inside publication roll back the new version,
rows, profiles, receipt update and activity together. A source hash, filename,
original cell text and complete parsing configuration survive publication;
temporary source bytes are then removed. Keeping the original external CSV is
still useful for byte-for-byte reproduction of its recorded SHA-256.

Uploads have revision checks so old validation/configuration cannot authorize a
changed draft. A one-minute cleanup removes expired upload bodies/configurations/
reports and marks their receipts expired. Cancellation removes staging immediately.
Import receipts and activity are retained without automatic pruning for now;
general retention remains an administration decision. Reloading the import URL
checks its actual status after an uncertain response. Publication is idempotent
per receipt and never creates a duplicate version when a response was lost.

## Persistence and lifecycle

`0002_datasets.sql` adds datasets, immutable dataset_versions, related
dataset_columns, one dataset_rows record per imported row, import_receipts,
temporary import_uploads and dataset_dependencies. Typed values and original
strings are separate JSONB objects keyed by stable column ID; metadata, ownership,
versioning and relationships are relational with constraints/indexes. Account
migration `0001_accounts.sql` and Python revisions remain untouched. Activity now
has an explicit resource kind and supports dataset/import identities, retaining
events after deletion rather than a foreign key into only users.

Runtime gets DML on datasets/receipts/staging, SELECT/INSERT on immutable version/
column/row tables, and SELECT on dependency registrations. No version/row update
or direct deletion privileges; dataset deletion cascades only through its parent.
There is no public SQL execution or peer-schema access. Publication locks the
dataset to serialize version numbering and checks active account state inside
the write transaction. Disabling an account cannot authorize a subsequent write
through a previously validated upload. Metadata revisions prevent lost updates.

Archiving hides datasets from the normal listing and prevents new versions, but
preserves old versions and access by their owner. Deletion requires a dependency/
share review and exact confirmation; dependency rows and database FKs prevent
accidental removal. Checkpoint 3 now creates real saved-analysis dependency
registrations and source FKs. Checkpoint 4 also registers real dashboard and
dataset-share dependencies. Dependent personal configurations remain after a
source grant is revoked, and still block deletion until removed or migrated.
[Dashboard/sharing permissions](dashboards-sharing-api.md) explain grants and copies;
saving a dataset/analysis never creates a grant automatically.

Backups retain datasets, versions, columns, normalized/original rows, receipts
and dependencies, but exclude `import_uploads`, account sessions/throttles and
the existing temporary patient-conversation rows. Incomplete restored receipts
cannot resume without upload content (410); abandoned imports are not revived.

## Query and profiling conventions

Query JSON is `{page, pageSize, search, filters, sort}`. Page starts at 1; default
pageSize is 25 (maximum 100). Search is a case-insensitive literal substring
across all interpreted cell values in the full version. It does not use wildcard
or regular-expression syntax. Filters combine with AND; `in` values combine with
OR. Supported operations are text contains/equals/starts_with/in; numeric equals,
gt/gte/lt/lte/between/in; date/date-time equals/before/after/between/in; boolean
equals/in; missing/present for every type. Text equals/in is case-sensitive;
contains/starts_with is case-insensitive. Filter inputs use canonical decimal
point, ISO dates/timezones and true/false independently of source conventions.
There are at most 20 filters, 50 values per selected-value filter, 500 characters
per value and 200 search characters, also subject to the JSON body bound.

Sort chooses one known column and asc/desc, applies the actual numeric/boolean
type (ISO date/time values sort chronologically), puts nulls last and uses source
row order as the stable tie-breaker. Parameterized SQL and whitelisted operations
apply search/filter/sort/count before LIMIT/OFFSET. Count and page are read from
the same repeatable-read snapshot. No arbitrary identifiers/SQL reach PostgreSQL.
Bounded pools and existing SQL/lock timeouts remain active; gateway/client dataset
deadlines are 60 seconds. Errors replace the current result; old rows are not
presented as if they matched a failed query.

Column profiles are immutable full-version summaries: total, present, missing,
nonmissing distinct count, min/max, and exact PostgreSQL numeric average where
applicable. Missing cells are excluded from statistics; present count is shown
as the denominator. Empty text/zero/false remain distinct from missing. The
Quality view is this initial completeness profile, not the later advanced
missingness/group/outlier/comparison features. Cross-medicine averages do not
measure therapeutic value. Grouping, quartiles, charting and the four advanced
features are now available through [Checkpoint 3 analytics](analytics-api.md).
New import means use numeric(80,24) inputs; old immutable profiles remain stored
as originally calculated. Current analytics recalculate from unchanged typed cells.

Technical references: official [CSV parser options](https://csv.js.org/parse/options/),
[PostgreSQL JSON operators](https://www.postgresql.org/docs/17/functions-json.html)
and [aggregates](https://www.postgresql.org/docs/17/functions-aggregate.html).
