# Setup, startup and shutdown

Use Docker Desktop with Linux containers and Compose, Python 3.12+ and uv
(the images use uv 0.11.19). Frontend development/tests use Node 22.23.2 and npm.
The isolated PostgreSQL backup tests also require PostgreSQL 17 client tools;
see [tooling](tooling.md). Starting services is an explicit user action.

Checkpoint 1 adds a fifth service and new platform-only configuration. Read the
[platform upgrade/provisioning guide](platform-accounts.md) before starting the
upgraded stack. This does not regenerate existing credentials or re-import data.
Checkpoint 2 adds an explicit dataset migration and grants. Follow the
[dataset upgrade guide](datasets.md) before starting updated images; reuse the
existing platform configuration and administrator. Startup does not migrate.
Checkpoint 3 adds saved analyses and source relationships. Use the current
[analytics upgrade guide](analytics.md) for all three explicit revisions/grants;
keep existing credentials, datasets and the application volume.

## Existing configured workspace

Keep the existing private `.env`, `.runtime/postgres.env`, `.runtime/compose.env`
and named database volume. Update Python commands after pulling changes:

```powershell
uv sync --frozen
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080> for accounts, or `/assistant` for the assistant. The normal configuration exposes only web on localhost.
Startup never changes migration state or re-imports facts. Cleanup has preserved
the project name `pharmacy-assistant-architecture`, service names and
`postgres_data` named-volume identity. Do not regenerate credentials or reset
the database merely because package/input paths changed.

Stop when finished:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml down
```

This preserves the named volume. `stop`/`start` also reuse existing containers.
Do not add `--volumes` to normal shutdown if you intend to keep application data.
The separate old `compose.database.yaml` and Streamlit launcher are retired.
Use the maintained Compose configuration for database-only work too.

## New checkout with no existing credentials or volume

From the project root:

```powershell
uv sync --frozen
Copy-Item .env.example .env
```

Edit `.env` locally to provide the chosen provider key. Keep it private. Then
initialize new credentials and translate them into the container configuration:

```powershell
.\.venv\Scripts\pharmacy-db.exe init-env
.\.venv\Scripts\pharmacy-compose-setup.exe
npm ci --prefix services/platform
npm --prefix services/platform run admin -- configure --source .runtime/compose.env --output .runtime/platform.env
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait postgres
```

Both initialization commands refuse to overwrite existing files. If credentials
already exist, use the existing-workspace instructions instead. The host database
file contains localhost URLs for explicit debug access; Compose setup translates
them to the internal `postgres` hostname without changing credentials.

Migrate, grant, import and verify explicitly, in order:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm database-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm database-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm database-setup import
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm database-setup verify
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm -it platform-setup provision-admin --email admin@example.com --name "Administrateur"
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Owned migrations retain their revision IDs. The importer reads the two
authoritative JSONL inputs in `data/imports/`, keeps recorded presentation IDs and
source conflicts, and performs transactional validation. Repeating unchanged
imports is recognized; normal startup does not import. Verification compares all
9,936 medication presentations and 327 pharmacy records and checks role isolation.

## Explicit debug and phone access

For host database clients, evaluation or API debugging, add the debug overlay:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml -f deploy/compose.debug.yaml up -d --wait
```

It binds PostgreSQL to localhost:55432, core to localhost:18000 and language to
localhost:18001. Core's host API docs are at <http://127.0.0.1:18000/docs>.
Host tools select existing database URLs with:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
```

Each runtime service loads only its own settings. Provider keys and the language
ledger URL are absent from core's container; migration/admin credentials belong
only to explicit setup jobs. The browser receives neither provider keys nor
database credentials. Returning to the normal Compose configuration removes
debug bindings on recreated services.

Phone access uses the separate web-only overlay and the laptop's Wi-Fi address;
follow [the frontend phone guide](../../apps/web/README.md#test-on-a-phone-over-wi-fi).
It does not expose database or internal API ports to Wi-Fi.

## Verification and recovery

Use `pharmacy-check` and frontend tests for offline checks. The user-run
`pharmacy-compose-verify --run-isolated --frontend` creates/removes its own
temporary stack and databases, with mocked hosted inference. It does not reuse
the application volume. See [tooling](tooling.md) for backup/restore prerequisites,
quota status, schema/fixture export and diagnostic locations.

If readiness fails, inspect the affected service's logs and configuration.
Missing/unavailable PostgreSQL is an error, not a signal to switch storage modes.
Do not publish environment files, expanded Compose configuration or private logs.
