# Checkpoint 2 — PostgreSQL storage implementation

Status: **implemented, verified, and reviewed by the user**. The user reported the
PostgreSQL-backed demo worked seamlessly and authorized checkpoint 3.
Schema direction approved in D019. The database was started by the user. No demo
API/UI service or hosted inference was started by the agent.

## Prepared implementation

- SQLAlchemy table models in each service's `storage/models.py`, separate from
  public Pydantic models; 13 core tables and 3 language tables.
- Independent Alembic environments under `migrations/core` and
  `migrations/language`, with separate schema-local version tables. Initial
  migrations contain frozen readable DDL, not imports of mutable runtime models.
- Explicit transactional importer, with source hashes, duplicate protection,
  exact formulation grouping, source ordering, and full reconstruction before
  commit. Repeating identical imports validates and returns without duplicates;
  different existing data is rejected until an explicit update policy is designed.
- Persistent conversations around the existing ChatService, preserving local
  matching/pricing. SQL transactions surround inference rather than holding row
  locks while the provider runs. Revisions prevent concurrent context overwrites.
- Hashed bearer tokens, three-minute uncertain-pending detection during restore,
  atomic successful publication, 30-minute inactivity expiry, one-minute cleanup,
  and cascade deletion on reset/expiry. Reads and failures do not renew expiry.
- PostgreSQL quota reservation/cooldown/budget implementation. SQLite import reads
  a consistent snapshot without rewriting historical ledgers; repeated imports
  do not add counters or shorten deadlines. Old evaluation budgets stay in their
  original ledger. Future PostgreSQL-mode evaluation uses the same PostgreSQL
  quota scopes as runtime. Old saved reports are not automatically migrated.
- Explicit credentials/setup, service-specific runtime grants, database-only
  Compose configuration, and backup/restore verification tools.

Driver: Psycopg 3 with synchronous SQLAlchemy connections. Request-side blocking
operations are offloaded to worker threads. Database access has connection,
statement, and lock timeouts; connection sessions use UTC. Dependencies are
locked in `uv.lock`; no provider/model or prompt switch was made.

## User-controlled database startup

An ignored `.runtime/postgres.env` was generated with local random credentials.
`database_setup init-env` never overwrites an existing file. Do not publish the
file, print its contents, or run Compose `config` without `--quiet` when sharing
output: expanded configuration includes the database password.

The isolated Compose service uses PostgreSQL 17, a persistent named volume, and
localhost port 55432. It does not use the separate existing Windows PostgreSQL 17
server on the machine. The user starts/stops services:

```powershell
docker compose --env-file .runtime/postgres.env -f deploy/compose.database.yaml up -d --wait
# Normal shutdown preserves the database volume:
docker compose --env-file .runtime/postgres.env -f deploy/compose.database.yaml down
```

The initial official-image download failed with a network timeout. After the user
restarted Docker Desktop and retried, the image downloaded and PostgreSQL became
healthy. Migrations, imports, permission checks, and backup/restore verification
below have since completed successfully.

## Explicit migration and import steps

Once PostgreSQL is healthy, these commands apply migrations and populate only the
configured application database. No command starts a service or calls inference:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_setup migrate
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_setup grant
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_setup import
# Re-run to validate idempotence:
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_setup import
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_setup verify
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_setup import-quota
```

Quota import requires the existing ledger. Supply `--legacy-ledger PATH` only if
the original configured path differs from `.runtime/inference_quota.sqlite3`.
Do not delete a ledger or start with fresh counters to bypass existing cooldowns.
Keep inference and evaluation idle while migrating quota state.

The `grant` step creates or updates only `pharmacy_core` and `pharmacy_language`
roles in the configured server. Runtime roles can manipulate their own service's
data, but cannot create schema objects, edit migration history, or access the
other service's schema. Administrative migration credentials are separate.

## Real database tests and recovery

```powershell
$env:PHARMACY_PG_TEST_ENV = (Resolve-Path .runtime/postgres.env).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_postgres_storage.py -v
Remove-Item Env:PHARMACY_PG_TEST_ENV
```

These opt-in tests create and remove only a uniquely named
`pharmacy_checkpoint2_test_*` database. They apply real migrations and exercise
round-trip imports, repeat imports, constraints, permissions, restart/restore,
deduplication, reset, expiry, failed-message retention, concurrent context updates,
quota reservations/budgets, legacy cooldown import, and backup/restore. All model
outputs are mocked. Tests do not start/stop PostgreSQL or modify source artifacts.

Backups use PostgreSQL 17 client tools and a new output file. Verification restores
to a uniquely named `pharmacy_backup_verify_*` database, compares facts and quota
accounting, then removes that verification database. Original databases are never
overwritten. Temporary conversation table data is excluded from backups so this
does not create permanent chat history.

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_backup backup .runtime/backups/checkpoint2.dump
.\.venv\Scripts\python.exe -m pharmacy_assistant.database_backup verify .runtime/backups/checkpoint2.dump
```

For a deliberate future restore, create a separate empty database, restore the
custom-format dump with `pg_restore --no-owner --no-privileges --exit-on-error`,
configure the setup tool's URLs for that database, reapply runtime grants, and run
verification before changing runtime configuration. No destructive in-place restore
is part of this checkpoint.

## Runtime activation and API additions

Existing `.env` was not modified. File mode remains available for the retained
demo and offline fixtures. To explicitly select the validated PostgreSQL runtime
when the user next starts the demo:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Settings read that explicitly selected database file for storage fields, with OS
environment overrides taking priority; provider credentials still come from the
existing root configuration. PostgreSQL mode never falls back to JSONL on failure,
nor does startup create tables or import data. Catalogue records are reconstructed
from relational tables into the existing indices to preserve matching behavior.
`/health` identifies the active storage backend. The launcher refuses to reuse an
existing API running in a different storage mode; the user must stop it or choose
another API port.

PostgreSQL mode adds:

- `POST /conversation`: create an empty temporary conversation and return its
  session token. No inference. This is the entry point for reliable request IDs.
- `GET /conversation` with `Authorization: Bearer TOKEN`: restore temporary
  messages and the latest usable context/choices; return refreshed opaque tokens
  without renewing the conversation's expiry or calling inference.
- `DELETE /conversation` with the same authorization: invalidate the conversation
  and delete its active child state; return 204.
- Optional `/chat` `request_id` (16–80 ASCII letters, digits, underscores, hyphens)
  with a valid session/continuation token: deduplicate a turn. Pending requests
  return 409; the latest completed identical request can be replayed without
  inference. Failed/uncertain or superseded requests require explicit recovery,
  not automatic repeat provider calls. Initial text without request IDs remains
  compatible; clients should create a conversation before using request IDs.
- Safe 503 storage failures and 409 conversation/request conflicts. Expired or
  reset tokens remain 410. No token is put in a URL or saved raw in transcript
  payloads.

Transcript/reset browser integration belongs to the replacement frontend in
checkpoint 5. The retained Streamlit UI has not been redesigned in this checkpoint.

## Validation status

Final complete suite: **260 passed, no skips**, 50.402 seconds, in
`reports/architecture_checkpoint2_final_verified.log`. This includes all nine
opt-in PostgreSQL checks. Earlier offline/intermediate logs are historical;
the provider shutdown and SQLite handle issues found there were fixed.

The application database contains 7,302 formulation groups, 9,936 presentations,
29,808 nullable price rows, 327 pharmacies, 3,128 observations, 1,260 conflicts,
22 alias spellings, and one import receipt. All 1,126 missing public prices are
preserved. A repeat import added no rows. Runtime permission checks passed.

Both original quota scopes were conservatively imported without copying old
evaluation budgets or modifying their ledger. A backup of the actual application
database was restored and compared in a separate verification database, including
quota accounting and absence of temporary history. The backup is ignored under
`.runtime/backups/checkpoint2_20261020.dump`.

`reports/architecture_checkpoint2_validation.json` records counts, revisions,
source hashes, and backup verification. The application smoke report verifies
the actual imported database via the in-process API, with inference mocked and
zero hosted requests. It selected presentation 9080 at its stored 372.00 MAD
price, used no further inference for selection, and reset its synthetic state.

Dependency lock verification, source/wheel build, Python compilation, and offline
SQL generation passed. Existing source data and historical evaluation reports
were preserved. PostgreSQL tests are opt-in and skip when not configured; a
skipped run alone is not database validation.

This completes checkpoint 2's storage work. HTTP language-service extraction,
full Compose wiring, and the React interface remain checkpoints 3–5. Stop for
user review here.
