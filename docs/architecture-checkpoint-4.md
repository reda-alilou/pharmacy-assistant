# Checkpoint 4 — Docker Compose integration

Status: **implemented, verified and reviewed by the user**. The user started all
four healthy services, confirmed the placeholder, and later authorized checkpoint
5. This document records checkpoint 4; see [checkpoint 5](architecture-checkpoint-5.md)
for the React interface that now replaces the placeholder.

## Four running services

| Service | Responsibility | Default host access |
| --- | --- | --- |
| `web` | Nginx on 8080; static assets and `/api/*` forwarding to core | `127.0.0.1:8080` |
| `core` | Core FastAPI, catalogue, temporary conversations, matching, pricing | Internal only |
| `language` | Language FastAPI, provider calls/validation, quotas | Internal only |
| `postgres` | PostgreSQL 17 with the existing persistent named volume | Internal only |

At checkpoint 4 the web image contained a small French placeholder; checkpoint 5
replaces it with React assets built from the frontend lockfile. Streamlit
remains available through the existing local launcher and is not a fifth
container. It is retired only after the final demo validation.

`deploy/compose.yaml` keeps the checkpoint 2 project name
`pharmacy-assistant-architecture` and volume `postgres_data`, which resolves to
`pharmacy-assistant-architecture_postgres_data`. Switching configuration reuses
the existing database. It does not reset credentials, re-import data, or migrate
on startup. The unrelated Windows PostgreSQL service remains untouched.

The old `compose.database.yaml` remains the database-only host development option.
Use one configuration at a time for this project. The complete stack removes its
default database host port; an explicit `compose.debug.yaml` overlay restores
localhost PostgreSQL 55432 and adds core 18000 / language 18001 for host tools.

## Independent images and credentials

`deploy/Dockerfile.python` has separate core, language, and short-lived database
tool targets. Each installs only its dependency group from the frozen root
`uv.lock`. Core includes no language implementation or Groq SDK. Language includes
no core implementation. Neither runtime image includes imports, evaluation data,
source snapshots, migration credentials, Streamlit, or project `.env` files.
The setup target alone includes migrations and the two public import inputs.

The Python base is `python:3.12-slim-bookworm`; the dependency installer is uv
0.11.19. The web image uses `nginx:1.28-alpine`. Builds run independently, use no
secret build arguments, and apply an allowlist `.dockerignore`. Local credentials,
Git, virtual environments, reports, snapshots, and caches do not enter the build
context. Runtime applications run as unprivileged users with read-only filesystems,
temporary `/tmp`, dropped capabilities, and no added privileges.

`compose_setup.py` creates ignored `.runtime/compose.env` from the existing
database credentials and selected inference configuration. It rewrites only URL
host/port to `postgres:5432`, preserves provider/model/quota scope/spacing, and
copies only the selected provider credential. It never overwrites an existing
file or prints its contents. Core receives only its own URL; language receives
only its own URL and provider settings. Web receives no application credentials.

## Prepare and build

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.compose_setup
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools config --quiet
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
```

The first command has already generated the local file for this workspace. On
later configuration changes, edit that ignored file deliberately; do not overwrite
database passwords associated with an existing volume. Avoid printing expanded
Compose configuration: `config --quiet` validates without exposing credentials.
Do not commit `.runtime`, `.env`, or generated runtime files.

## Explicit isolated verification

After images have built, the user controls the test stack lifecycle with:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.compose_verify --run-isolated
```

This creates a uniquely named `pharmacy-checkpoint4-test-*` project and fresh
volume, with generated passwords and a nonfunctional provider key. The language
container has only an internal test network, so hosted inference is unreachable.
The utility explicitly runs migrations, grants, imports, and round-trip validation
on that fresh test database, then starts the four containers.

It seeds one synthetic clarification through the existing conversation engine
with an offline fixture sent through `docker compose exec`; this fixture is not
in the deployed image or production request path. It then checks public API
forwarding, image and credential isolation, language outage behavior, retained
failed messages, inference-free selection, gateway failure handling, Docker DNS
recovery after replacement, database failure/recovery, 429/Retry-After forwarding,
and preservation of facts, temporary state, and quota counters after whole-stack
replacement. It sends no hosted model requests. Finally it removes only its own
temporary containers/networks/volume and generated credential files.

Public evidence is written to
`reports/architecture_checkpoint4_container_validation.json`. Diagnostic logs
stay in ignored `.runtime`. The user's application volume and running demo are
not modified. The fixture must never be added as a runtime fallback.

## Start the existing migrated application

Stop the prior local demo with Ctrl+C in its terminal. Keep Docker Desktop
running, then start the full stack yourself:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>. The placeholder is expected until checkpoint 5.
<http://127.0.0.1:8080/api/health> reports the core catalogue and language status;
this check does not call the model. OpenAPI is available through
`/api/openapi.json`, with working Swagger documentation at `/api/docs`.

Observe or stop the services yourself:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml ps
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml logs --tail 100 core language web
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml down
```

Normal `down` preserves the named volume. `down --volumes` removes stored data and
is not the application shutdown command. The isolated test utility uses volume
deletion only for the fresh test project it creates and checks by prefix.

## Fresh installation only

The current application database is already migrated/imported. A genuinely new
volume needs explicit setup after builds:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait postgres
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup migrate
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup grant
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup import
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup verify
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Existing historical quota ledgers require the separately reviewed explicit import
procedure; no startup step silently resets or replaces them. Backups remain the
verified checkpoint 2 host procedure, with PostgreSQL debug access enabled:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml -f deploy/compose.debug.yaml up -d --wait
```

The original ignored `.runtime/postgres.env` still points host backup/test tools
at localhost:55432. Keep backup files private and retain the established exclusion
of temporary conversation contents.

## Readiness and failure behavior

- PostgreSQL readiness gates both backend startups. Core loads the already
  imported relational catalogue; missing migrations/data fail startup visibly.
- Core `/ready` checks its owned database tables without inference, writes, or
  expiry renewal. Language is deliberately not a core readiness dependency.
- Language `/ready` checks configured credentials and quota-state access without
  calling the provider or consuming quota. It does not promise remaining allowance
  or prove provider availability.
- Web `/healthz` reports the static/reverse-proxy process. Core availability is
  checked separately through `/api/ready`.
- Nginx re-resolves core through Docker DNS after replacement. It disables proxy
  retries, preserves application error bodies and cooldown headers, and gives a
  short French JSON error on gateway failure. Timeout uncertainty is explicit;
  no automatic request replay or provider fallback is added.
- Containers do not restart automatically or start migrations/imports on boot.
  The user controls service lifecycle. Failure of language leaves core/database
  operations and valid offered choices usable; database failure prevents a
  successful conversation result.

Current automated evidence and any remaining environmental blocker are recorded
in `reports/architecture_checkpoint4_status.json`. That report predates the user's
subsequent successful startup/review and is retained as historical evidence.


## Verified results

- All four images built; core/language ownership and imports and the setup CLI
  passed separate offline image smoke checks. Frozen dependency exports, lock
  verification, Python source/wheel builds, and whitespace checks passed.
- Full pre-container regression suite: 280 passed / 54.715 seconds, including ten
  real PostgreSQL checks. After the user restarted Docker, the host database was
  stopped: the final offline run passed 270 / 45.917 seconds with ten opt-in
  PostgreSQL tests skipped. An intervening test attempt could not connect to that
  stopped database; this is retained as diagnostic evidence.
- The first isolated container run passed fresh migrations/import/round-trip but
  exposed a wrong column name in the new readiness query. This was corrected to
  `source_record_id`, affected images rebuilt, and verification repeated.
- The final user-run isolated container verification passed all eight checks:
  bootstrap/round-trip, web/API routing and OpenAPI, image/credential/network
  isolation, language outage with retained failed messages and valid selection,
  core gateway errors/DNS recovery, database replacement persistence, cooldown
  error/header forwarding, and whole-stack replacement persistence. Temporary
  resources were removed; no hosted inference or application-volume changes.
- Image downloads initially timed out through router DNS. The user approved a
  temporary Wi-Fi DNS change for the build. Images built successfully, and the
  original automatic DNS settings were restored and independently checked.
- Source input hashes and tracked historical data/evaluation evidence are
  unchanged. No new final architecture decision, Git commit, or push was made.

Evidence: `reports/architecture_checkpoint4_status.json`,
`reports/architecture_checkpoint4_container_validation.json`,
`reports/architecture_checkpoint4_tests_precontainer.log`,
`reports/architecture_checkpoint4_offline_final.log`,
`reports/architecture_checkpoint4_build_verified.log`, and
`reports/architecture_checkpoint4_readiness_fix_build.log`.
