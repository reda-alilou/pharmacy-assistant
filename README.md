# Multilingual Patient–Pharmacy Assistant

A local challenge demo and learning project for Moroccan pharmacy requests.
A French React chat connects to a core FastAPI service; a separate language
service uses hosted Qwen extraction through Groq. A local image service uses
EasyOCR and fuzzy matching to identify medication boxes from uploaded photos.
Local code matches medication and pharmacy records, manages clarification and
temporary conversations, and calculates prices from recorded facts. Backend
interpretation and answers support French, Arabic, Darija and mixed language;
the patient interface is French only.

For a self-contained explanation of the current system, read
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md): architecture and request flow,
service communication, database tables and relationships, data collection and
transformation, repository structure, configuration and validation evidence.

## What the application does

- Accepts typed questions and medication-box photos in the French web interface.
- Extracts intent and entities with a hosted language model, while keeping raw
  message spans separate from conversation context.
- Matches medication identity, strength, form and presentation against the local
  catalogue. Ambiguous matches require an explicit user choice.
- Identifies medication boxes locally with EasyOCR, normalisation and fuzzy
  matching. The image path does not call the hosted model.
- Shows ranked OCR candidates and then the normal medication cards, prices and
  sources from the local database.
- Supports follow-ups, offered clarification choices, complete-package quantity
  totals and exact decimal arithmetic. Missing prices stay unknown.
- Keeps temporary conversations for 30 minutes of inactivity, restores them after
  refresh, exposes failed messages, supports explicit retry and server-side reset.
- Shares PostgreSQL quota reservations and cooldowns across the running services.

Try `Quel est le prix de ABIP ?`, choose a presentation, then ask
`Et pour deux boîtes ?`. The paperclip button sends a medication-box photo to the
local image service. The uploaded photo is previewed in the current conversation;
after a full page refresh, the server restores the message label but not the image
binary. Recorded prices are historical observations, not live offers.

The [demo guide and spoken script](docs/project/demo-guide.md) provides a
presentation sequence, verified examples and an architecture walkthrough.

## Architecture at a glance

| Component | Container | Responsibility | Host exposure |
| --- | --- | --- | --- |
| `web` | nginx + built React assets | French chat, photo preview, result cards | `127.0.0.1:8080` |
| `core` | FastAPI | Conversation state, matching, pricing, API | Internal only |
| `language` | FastAPI | Hosted provider adapters, extraction validation, quotas | Internal only |
| `image` | FastAPI + EasyOCR | Local OCR, normalisation and fuzzy matching | Internal only |
| `postgres` | PostgreSQL 17 | Catalogue, conversations, quota ledger | Internal only |

Text request flow:

1. `web` sends `POST /api/chat` to nginx.
2. nginx proxies `/api/*` to `core`.
3. `core` calls `language` over the private Compose network.
4. `language` calls the configured hosted provider and validates the structured
   interpretation.
5. `core` resolves local records, calculates recorded prices, stores the
   conversation and returns the response.
6. `web` validates the response at runtime before rendering it.

Photo request flow:

1. `web` previews the selected image locally and sends `multipart/form-data` to
   `POST /api/chat/image`.
2. nginx allows up to 15 MB on that exact route.
3. `core` validates the content type and size, then calls `image` at
   `http://image:8002/identify/image`.
4. `image` runs EasyOCR, normalises the detected text and ranks catalogue records
   with field-aware fuzzy matching.
5. `core` maps the returned source IDs to its own records, renders the answer and
   cards, and persists the conversation.

The image service is intentionally separate from the uv workspace because
EasyOCR/PyTorch would otherwise inflate every Python install. It has its own
`requirements.txt` and Dockerfile, which installs CPU-only PyTorch.

## Prerequisites

- Docker Desktop with Linux containers and Compose.
- Python 3.12 or later.
- `uv` 0.11 or later.
- Node 22.23.2 and npm for frontend development/tests only. The container build
  does not require Node on the host.
- Internet access for the first image build, the first EasyOCR model download and
  hosted inference. Valid offered choices and photo matching do not call the
  hosted provider.
- Enough disk space for Docker images, PostgreSQL data and EasyOCR models. The
  CPU PyTorch layer is several hundred MB.

Check the tools:

```powershell
docker version
docker compose version
uv --version
python --version
node --version
npm --version
```

The isolated PostgreSQL backup tests additionally require PostgreSQL 17 client
tools; see [tooling](docs/operations/tooling.md).

## Quick start: existing configured workspace

Use this when `.env`, `.runtime/postgres.env`, `.runtime/compose.env` and the
named database volume already exist.

```powershell
cd C:\Users\msi\Desktop\pharmacy-assistant

uv sync --frozen

docker compose --env-file .runtime\compose.env -f deploy\compose.yaml --profile tools build
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>.

Check service health:

```powershell
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml ps
```

All five services should become healthy: `web`, `core`, `language`, `image` and
`postgres`. The normal configuration exposes only `web` on localhost.

After source changes, rebuild the affected images before recreating services. To
rebuild every application/setup image:

```powershell
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml --profile tools build
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml up -d --wait
```

Startup never migrates the database or re-imports catalogue data. Existing
credentials, migration revisions, Compose project/service names and named volumes
are retained.

## First run from a fresh clone

From the repository root:

```powershell
uv sync --frozen
Copy-Item .env.example .env
```

Edit `.env` locally and provide the selected provider key. Keep it private. The
default provider is Groq:

```dotenv
INFERENCE_PROVIDER=groq
GROQ_API_KEY=your-private-key
```

Then create the ignored runtime configuration files:

```powershell
.\.venv\Scripts\pharmacy-db.exe init-env
.\.venv\Scripts\pharmacy-compose-setup.exe
```

`pharmacy-db init-env` creates `.runtime/postgres.env` with random database
credentials. `pharmacy-compose-setup` reads `.env` plus the database file and
creates `.runtime/compose.env` with container hostnames. Both commands refuse to
overwrite existing files and never print secrets.

Build all images, then start PostgreSQL alone for the explicit setup jobs:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait postgres
```

Run migrations and data setup explicitly, in this order:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup migrate
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup grant
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup import
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup verify
```

Finally start the full stack:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>.

The importer reads the two authoritative JSONL inputs in `data/imports/`, keeps
recorded presentation IDs and source conflicts, and validates transactionally.
Verification compares all 9,936 medication presentations and 327 pharmacy records
and checks role isolation. Repeating an unchanged import is recognised; normal
startup does not import.

## Environment files and configuration

| File | Created by | Purpose | Commit? |
| --- | --- | --- | --- |
| `.env.example` | Repository | Documented template for local settings | Yes |
| `.env` | Developer | Provider key and local service settings | No |
| `.runtime/postgres.env` | `pharmacy-db init-env` | Random PostgreSQL credentials and host URLs | No |
| `.runtime/compose.env` | `pharmacy-compose-setup` | Container hostnames, ports and selected provider settings | No |

Never publish `.env`, `.runtime/postgres.env`, `.runtime/compose.env`, expanded
Compose output or logs containing private values. The browser receives neither
provider keys nor database credentials.

Frequently used settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `INFERENCE_PROVIDER` | `groq` | Selected hosted provider |
| `GROQ_API_KEY` | empty | Private Groq key; required for typed questions with Groq |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` | Extraction model |
| `DATABASE_ENV_FILE` | `.runtime/postgres.env` | Host-side database URL file |
| `STORAGE_BACKEND` | `postgres` | Only supported runtime storage |
| `LANGUAGE_SERVICE_URL` | `http://127.0.0.1:8001` | Host/debug language URL |
| `LANGUAGE_SERVICE_TIMEOUT_SECONDS` | `160` | Total core-to-language deadline |
| `IMAGE_SERVICE_URL` | `http://127.0.0.1:8002` | Host/debug image URL |
| `IMAGE_SERVICE_TIMEOUT_SECONDS` | `150` | Total core-to-image deadline |
| `IMAGE_TOP_K` | `5` | Number of OCR candidates requested |
| `IMAGE_MIN_SCORE` | `50` | Minimum fuzzy score for an OCR candidate |
| `MEDID_OCR_LANGUAGES` | `fr` | EasyOCR language list |
| `MEDID_OCR_MIN_CONFIDENCE` | `0.20` | Minimum OCR token confidence |
| `WEB_PORT` | `8080` | Host port used by the normal web binding |

Compose overrides internal URLs with container hostnames such as
`http://language:8001` and `http://image:8002`. The host values in `.env` are for
explicit debug tools.

## Photo identification and OCR models

The `image` service stores downloaded EasyOCR models in the named volume
`easyocr_models`, mounted at `/models`. The container root filesystem is read-only;
the service uses `HOME=/tmp` and writes its EasyOCR user-network files under
`/models/user_network`.

The first photo request may download the detection and recognition models. This
needs internet access once and can take longer than a normal request. Later starts
reuse the volume. The model files are not committed to Git.

The service is internal to Compose. Do not try to open port 8002 from the host in
the normal configuration. Test it through the paperclip button in the web UI.

Image error codes shown by the API/client:

| Code | Meaning |
| --- | --- |
| `image_invalid` | Missing, empty or unsupported image |
| `image_too_large` | Image exceeds 15 MB |
| `image_service_unavailable` | Core cannot reach the image service |
| `image_service_timeout` | OCR exceeded the configured deadline |
| `image_identification_failed` | OCR/matching returned an unusable result |
| `image_unavailable` | Image support is not configured in core |

A photo may return several candidates. The first card is the highest-ranked match;
the others are lower-scoring OCR candidates. The UI never invents a price or a
catalogue record for an uncertain match.

## Stop, restart and reset

Stop the stack while preserving the database and OCR models:

```powershell
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml down
```

`stop`/`start` also reuse existing containers:

```powershell
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml stop
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml start
```

Do not add `--volumes` to a normal shutdown. It removes PostgreSQL data and the
EasyOCR model volume. Use it only when a deliberate full reset is intended:

```powershell
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml down --volumes
```

A full reset also requires new credentials and a new explicit migrate/import cycle.
The separate old `compose.database.yaml` and Streamlit launcher are retired; use
the maintained Compose configuration for database-only work too.

## Checks and validation

After `uv sync --frozen`, run the maintained offline Python checks:

```powershell
.\.venv\Scripts\pharmacy-check.exe
.\.venv\Scripts\pharmacy-archive.exe
```

These do not make hosted inference calls. Real PostgreSQL tests are skipped
outside the explicit isolated verification lifecycle. For frontend checks:

```powershell
cd apps/web
npm ci
npm run build
npm run lint
npm test
```

From the root, the user can explicitly run the disposable full-stack check:

```powershell
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend
```

It exercises the real frontend/services and 18 PostgreSQL scenarios with mocked
inference, then removes its own stack and volume. It preserves application data.
See [administration commands](docs/operations/tooling.md) and
[evaluation commands and budgets](docs/development/evaluation-tools.md).

Current offline validation: **269 Python tests** pass, **23 browser tests** pass
and one deployment-only browser test is skipped in the normal suite. The isolated
Compose verification covers the real web/core/PostgreSQL path and its 18
PostgreSQL scenarios.

## Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `required variable ... is missing` | `.runtime/compose.env` absent | Run `pharmacy-compose-setup` |
| `Run database_setup init-env first` | `.runtime/postgres.env` absent | Run `pharmacy-db init-env` |
| `image` unhealthy or restarting | Image build/model filesystem issue | Inspect `logs image`, rebuild `image` |
| Photo returns an immediate error | Old image without the writable EasyOCR home fix | Rebuild `image`, then `up -d --wait image` |
| First photo is slow or times out | EasyOCR models are downloading | Keep internet access; wait or pre-download models |
| `image_identification_failed` | OCR found no usable match | Use a clearer, well-lit photo with visible text |
| Typed question fails but photo works | Hosted provider quota/key/network issue | Check `logs language` and `.runtime/compose.env` |
| `core` not ready | PostgreSQL unavailable or not migrated | Check `logs core postgres`; run explicit migrations |
| Port 8080 already in use | Another process owns the port | Stop it or change `WEB_PORT` deliberately |
| Image preview disappears after refresh | Server stores text, not image bytes | Expected; the current-session preview is local only |

Useful diagnostics:

```powershell
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml ps
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml logs --tail=120 image core language web postgres
docker compose --env-file .runtime\compose.env -f deploy\compose.yaml config --quiet
```

If readiness fails, inspect the affected service's logs and configuration.
Missing or unavailable PostgreSQL is an error, not a signal to switch storage
modes. Do not publish environment files, expanded Compose configuration or private
logs.

## Repository structure

| Location | Responsibility |
| --- | --- |
| `apps/web/` | React/TypeScript chat, photo preview, result cards and browser tests |
| `services/core/` | Conversation, matching, pricing, HTTP API and owned migrations |
| `services/language/` | Provider adapters, extraction validation, quotas and owned migrations |
| `services/image/` | Standalone EasyOCR and fuzzy-matching service for medication photos |
| `packages/contracts/` | Shared schemas, protocols and errors |
| `packages/infrastructure/` | Environment, database, workspace and evidence-path helpers |
| `tools/operations/` | Explicit setup/import/backup, verification and offline checks |
| `tools/evaluation/` | Datasets, scoring, budgeted runners and evidence validation |
| `deploy/` | Compose configurations and nginx gateway |
| `data/imports/`, `data/evaluation/` | Authoritative import inputs and active annotations |
| `tests/` | Architecture/integration checks and shared test fixtures |
| `docs/` | Current architecture, development, operations, project and validation guides |
| `archive/` | Immutable historical data, reports and documents with an exact hash manifest |
| `artifacts/` | Ignored generated logs, builds, reports and screenshots |

The root is a virtual uv coordinator. Six Python members own their dependencies
and are independently installable from one lockfile. `services/image` is kept
outside that workspace because EasyOCR/PyTorch would otherwise inflate every
Python install; it has its own requirements and container image. Streamlit, the old
`pharmacy_assistant` package, collection/enrichment workflows and obsolete root
tests have been retired after their useful coverage was migrated.

Local environments, credentials and generated output remain ignored. Verified
obsolete scratch directories and legacy caches have been removed. Previously
ignored raw downloads/staging data are preserved privately in `archive/local/`;
they are not application inputs or part of the tracked historical archive.

## Data, evidence and limits

The active medication input contains **9,936 presentations** and the pharmacy
input **327 records**. PostgreSQL retains presentation identities, source
observations and conflicts rather than combining differing facts. **1,126**
medication presentations have no recorded public price. See the
[data guide](docs/project/data-and-evidence.md).

Historical evaluation results describe earlier frozen implementations:

| Evidence | Result | Limit |
| --- | --- | --- |
| [Frozen held-out metrics](archive/historical/reports/held_out_qwen_frozen_metrics.json) | 34/40 backend cases; intent F1 92.86%; entity slot F1 95.91%; 48/48 schema-valid completions | Earlier frozen version |
| [Later correction metrics](archive/historical/reports/matching_package_metrics_complete.json) | 14/14 backend cases; 20/20 schema-valid completions; raw slot F1 85.71% | Seen failures and development variations; not a new independent benchmark |

The small synthetic dataset was assistant-authored/reviewed; independent
native-speaker review is not claimed. Cleanup checks preserve behavior and
evidence; they do not remeasure current model accuracy. Archived evidence stays
unchanged and cannot silently authorize a current live freeze.

This demo does not verify stock, opening hours or duty schedules, calculate
geographic proximity, diagnose conditions or recommend treatment. Pharmacy
coverage is partial and limited to Rabat. Voice, accounts, durable patient history
and public deployment are outside the implemented scope. Hosted free inference
can be interrupted by quotas and provider availability. No local model training
or universal extraction accuracy is claimed.

## Project status and navigation

Architecture checkpoints 1–5 and cleanup R1–R7 are complete. R7 passed independent
installs/builds, 269 offline Python tests, 23 browser tests, all ten isolated stack
checks and all 18 PostgreSQL tests. The user accepted the laptop demo and waived
the final physical-phone review; automated mobile checks passed. See
[the final R7 evidence and limits](docs/validation/cleanup-r7.md). Follow
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the current handoff and
[DECISION_LOG.md](DECISION_LOG.md) for finalized choices. The
[cleanup plan](docs/development/cleanup-plan.md) defines the checkpoint gates.

Read the [current architecture](docs/architecture/overview.md),
[requirements audit](docs/project/requirements-audit.md), and
[archive guide](archive/README.md). The related-work study and final presentation
preparation remain submission work; they are separate from repository cleanup.
