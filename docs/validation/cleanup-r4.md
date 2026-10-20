# R4 — PostgreSQL-only service runtime

Status: **complete, reviewed by the user**. Offline/image checks and all nine
user-run isolated-stack checks passed. The user authorized R5, whose current
tools and coverage are documented in [the R5 guide](cleanup-r5.md). The sections
below describe the R4 checkpoint as implemented before that tooling migration.

## Runtime behavior

Both services now require their own database URL. `CoreSettings` requires
`CORE_DATABASE_URL`; `LanguageSettings` requires `LANGUAGE_DATABASE_URL`. The
accepted driver is `postgresql+psycopg`, with an explicit host, user and database.
Each settings class still excludes the other service's credential. Validation
errors hide input values. `STORAGE_BACKEND` accepts only `postgres`; `files`,
blank/missing URLs, SQLite URLs and incomplete URLs fail during configuration.

Core always loads the relational catalogue and starts persistent conversations.
It verifies catalogue/conversation access before serving requests. Language
always constructs a PostgreSQL quota store and verifies access before yielding
its application lifespan. Unavailable/unmigrated storage fails startup with a
sanitized message. There is no automatic migration, import, file fallback or
quota reset. A missing provider key remains a separate readiness failure; a
database is required even when inference is unconfigured.

Live health/readiness responses report `postgres`. The existing wire schemas
remain byte-equivalent after canonicalization; the health schemas retain their
backward-readable enum for existing clients/evidence, but running services cannot
select its former file-mode value. No frontend types or UI changed.

## Explicit offline dependencies

The core application factory accepts a `CoreResources` object containing its
catalogue, directory, interpreter, chat responder and optional conversation store.
The language factory accepts an explicit interpreter. Default exported apps supply
neither; no environment value, HTTP field or automatic failure path injects fixtures.

`tests/runtime_fixtures.py` constructs offline dependencies deliberately. Most
mocked language scenarios use a per-test memory quota fixture. Existing temporary
ledger scenarios explicitly inject their own store; they never use the private
default ledger. The two-API harness explicitly chooses persistent mode for the
real PostgreSQL scenarios. Existing grounding, HTTP errors, retries, cooldowns,
matching and recovery assertions are preserved.

JSONL readers and the memory conversation engine remain available to explicit
imports/evaluation/fixtures. They are no longer a service startup branch.

## Transitional tools until R5

The writable SQLite ledger moved out of `pharmacy_language` into the retained
legacy tooling namespace, `src/pharmacy_assistant/language/legacy_quota.py`.
The legacy evaluation factory supplies this ledger explicitly. Runtime images
contain neither that package nor its factory; services import their canonical
PostgreSQL factory directly. This preserves existing budget, concurrency and
resume checks without retaining a SQLite runtime selection.

The read-only legacy-ledger import into PostgreSQL remains an explicit
administrative operation. Existing private ledgers and credentials were not
readjusted, migrated or removed. Organizing those tools and migrating their
coverage belongs to R5; retiring their compatibility modules belongs to R6.

## Host and Compose use

The existing Compose environment already supplies PostgreSQL and owned URLs.
Service/project names, named volume, ports, overlays and private environment
files are unchanged. Startup commands are unchanged; the affected images have
been rebuilt. No application stack was started by the agent.

For the existing host setup, select the already configured private file explicitly
before invoking the APIs or retained launcher:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
```

The shared loader reads each service's own fields from that file. Explicit
process environment values take priority; a stale `STORAGE_BACKEND=files` must
be removed or set to `postgres`. Do not copy over an existing `.env` or regenerate
database credentials. Fresh setups must perform the explicit database setup
described in the earlier database/Compose guides before starting services.
`.env.example` documents the required PostgreSQL setup; no private file changed.

## Evidence

- Full root regression suite: 276 passed, ten opt-in host PostgreSQL checks skipped
  (286 discovered). No host database was started to run them.
- Both owned service suites: six tests each passed, covering settings isolation,
  missing/invalid URLs, unavailable storage, sanitized failures, resource closure,
  and explicit offline injection.
- Frozen lock verification and source/wheel builds for all five workspace
  packages passed. Dependency versions, prompts, migrations, frontend source and
  historical data/reports are unchanged.
- Core, language and explicit setup images rebuilt with the existing Desktop
  builder. Network-disabled, self-removing helpers proved missing/unavailable
  PostgreSQL and file-mode startup are rejected in the installed runtime images,
  no SQLite fallback file appears, peer/legacy packages are absent and original
  OpenAPI hashes are preserved. These helpers started no listening server.
- The user-controlled complete stack passed all nine checks: explicit migrations,
  import/round-trip, frontend routing and recovery, service/credential isolation,
  language/core/database outages, quota/cooldown propagation, inference-free
  selection, and persistence across container/whole-stack replacement. Its
  temporary resources were removed. No containers remained running at handoff;
  hosted inference and modifications to the application volume were excluded.
  The successful command was:

  ```powershell
  .\.venv\Scripts\python.exe -m pharmacy_assistant.compose_verify --run-isolated --frontend --output docs/validation/cleanup-r4-container.json
  ```

Public evidence: `cleanup-r4-baseline.json`, `cleanup-r4-images.json` and the
user-run `cleanup-r4-container.json`. Disposable logs/build products are in
ignored `artifacts/cleanup/r4/`. No hosted inference, scraping, Git commit/push
or network-setting change is part of this checkpoint.

Stop for user review before **R5: operations/evaluation tooling and coverage**.
