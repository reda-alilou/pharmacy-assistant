# Setup, startup and shutdown

This guide covers a fresh checkout, an existing configured workspace, the local
OCR image service, explicit database setup, debug/phone access and recovery. All
commands assume Windows PowerShell and the repository root unless stated
otherwise. Starting services is always an explicit user action.

## Contents

- [Prerequisites](#prerequisites)
- [Environment files](#environment-files)
- [Existing configured workspace](#existing-configured-workspace)
- [Fresh checkout](#fresh-checkout)
- [Image service and OCR models](#image-service-and-ocr-models)
- [Explicit debug and phone access](#explicit-debug-and-phone-access)
- [Updating an existing installation](#updating-an-existing-installation)
- [Stop, restart and reset](#stop-restart-and-reset)
- [Verification and recovery](#verification-and-recovery)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Install and verify:

- Docker Desktop with Linux containers and Docker Compose.
- Python 3.12 or later.
- `uv` 0.11 or later.
- Node 22.23.2 and npm for frontend development and browser tests. The Docker
  image build does not need Node on the host.
- Internet access for image builds, hosted inference and the first EasyOCR model
  download.

```powershell
docker version
docker compose version
uv --version
python --version
node --version
npm --version
```

The isolated PostgreSQL backup tests additionally require PostgreSQL 17 client
tools. See [tooling](tooling.md).

## Environment files

| File | Created by | Contains | Commit? |
| --- | --- | --- | --- |
| `.env.example` | Repository | Documented local settings template | Yes |
| `.env` | Developer | Provider key and host-side settings | No |
| `.runtime/postgres.env` | `pharmacy-db init-env` | Random database credentials and localhost URLs | No |
| `.runtime/compose.env` | `pharmacy-compose-setup` | Container hostnames, ports and selected provider settings | No |

The browser and containers never receive the complete set of credentials. Core
receives only its own database URL and the language/image service origins. The
language service owns provider keys and its quota database URL. PostgreSQL admin
and migration credentials are used only by explicit setup jobs.

Never publish `.env`, `.runtime/postgres.env`, `.runtime/compose.env`, expanded
Compose output or private logs. Do not regenerate credentials merely because a
package path or input file changed.

### Main settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `INFERENCE_PROVIDER` | `groq` | Hosted provider used by the language service |
| `GROQ_API_KEY` | empty | Private Groq key |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` | Extraction model |
| `GROQ_OUTPUT_MODE` | `json_object` | Provider output mode |
| `DATABASE_ENV_FILE` | `.runtime/postgres.env` | Host-side database URL file |
| `STORAGE_BACKEND` | `postgres` | Only supported runtime storage |
| `LANGUAGE_SERVICE_URL` | `http://127.0.0.1:8001` | Host/debug language origin |
| `LANGUAGE_SERVICE_TIMEOUT_SECONDS` | `160` | Total core-to-language deadline |
| `IMAGE_SERVICE_URL` | `http://127.0.0.1:8002` | Host/debug image origin |
| `IMAGE_SERVICE_TIMEOUT_SECONDS` | `150` | Total core-to-image deadline |
| `IMAGE_TOP_K` | `5` | Number of OCR candidates requested |
| `IMAGE_MIN_SCORE` | `50` | Minimum fuzzy score for an OCR candidate |
| `MEDID_OCR_LANGUAGES` | `fr` | EasyOCR language list |
| `MEDID_OCR_MIN_CONFIDENCE` | `0.20` | Minimum OCR token confidence |
| `WEB_PORT` | `8080` | Host port for the normal web binding |

Compose replaces internal hostnames with `language:8001`, `image:8002` and
`postgres:5432`. The host values are for explicit debug tools, not the normal
container path.

## Existing configured workspace

Use this path when `.env`, `.runtime/postgres.env`, `.runtime/compose.env` and the
named database volume already exist.

Update Python commands and rebuild the images:

```powershell
uv sync --frozen
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>. The normal configuration exposes only web on
localhost.

Check health:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml ps
```

Expected services: `web`, `core`, `language`, `image`, `postgres`. All should
become healthy. Startup never changes migration state or re-imports facts.

The project name is `pharmacy-assistant-architecture`. The persistent database
volume is `postgres_data`; the OCR model volume is `easyocr_models`. Do not reset
either merely because package or input paths changed.

## Fresh checkout

### 1. Install Python dependencies

```powershell
uv sync --frozen
```

This creates `.venv/` from the committed `uv.lock`.

### 2. Create the local provider settings

```powershell
Copy-Item .env.example .env
```

Edit `.env` locally. The default configuration is:

```dotenv
INFERENCE_PROVIDER=groq
GROQ_API_KEY=your-private-key
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_OUTPUT_MODE=json_object
```

Keep `.env` private. Typed questions need the hosted provider; photo matching and
valid offered choices do not.

### 3. Create database and Compose credentials

```powershell
.\.venv\Scripts\pharmacy-db.exe init-env
.\.venv\Scripts\pharmacy-compose-setup.exe
```

- `init-env` creates `.runtime/postgres.env` with random admin, core and language
  passwords and localhost URLs.
- `pharmacy-compose-setup` translates those URLs to the internal `postgres`
  hostname and writes `.runtime/compose.env`, including only the selected
  provider's key and options.

Both commands use exclusive file creation and refuse to overwrite existing files.
They do not print secrets. If either says the configuration already exists, use
the existing-workspace instructions instead.

### 4. Build images

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
```

This builds `web`, `core`, `language`, `image` and the explicit `database-setup`
job. The `image` build installs CPU-only PyTorch and EasyOCR and can take several
minutes.

### 5. Start PostgreSQL alone

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait postgres
```

### 6. Migrate, grant, import and verify

Run these explicitly, in order:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup migrate
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup grant
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup import
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools run --rm database-setup verify
```

Owned migrations retain their revision IDs. The importer reads
`data/imports/ammps_medications_enriched.jsonl` and
`data/imports/pharmacies_rabat.jsonl`, preserves presentation identities and
source conflicts, and validates transactionally. Repeating an unchanged import is
recognised. Verification compares all 9,936 medication presentations and 327
pharmacy records and checks role isolation.

### 7. Start the full stack

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>.

## Image service and OCR models

The `image` service is a separate FastAPI application under `services/image/`.
It is not a member of the root uv workspace because EasyOCR/PyTorch would inflate
every Python environment. It has its own `requirements.txt` and Dockerfile.

At runtime:

- The container root filesystem is read-only.
- `/tmp` is writable tmpfs.
- `HOME=/tmp`.
- EasyOCR models live in the named volume `easyocr_models` mounted at `/models`.
- EasyOCR user-network files live in `/models/user_network`.

The first photo request may download the detection and recognition models. This
requires internet access once and can take longer than a normal request. Later
starts reuse the volume. Model files are not committed to Git.

The service is internal to Compose and is not published on localhost in the normal
configuration. Test it through the paperclip button in the web UI. For diagnostics
inside the private network, inspect the service logs.

### Optional model pre-download

If the first request times out on a slow connection, pre-download models into the
volume after building the image:

```powershell
docker run --rm --tmpfs /tmp:rw,noexec,nosuid,size=256m -e HOME=/tmp `
  -v pharmacy-assistant-architecture_easyocr_models:/models `
  --entrypoint python pharmacy-assistant-image:local -c `
  "import easyocr, pathlib; pathlib.Path('/models/user_network').mkdir(parents=True, exist_ok=True); easyocr.Reader(['fr'], gpu=False, model_storage_directory='/models', user_network_directory='/models/user_network'); print('models ready')"
```

Then recreate the image service:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait image
```

### Photo limits and errors

- Accepted types: `image/*` or `application/octet-stream`.
- Maximum size: 15 MB.
- nginx allows 15 MB only on `POST /api/chat/image`; the global limit stays small.
- Core forwards the image to `http://image:8002/identify/image`.

| Error code | Meaning |
| --- | --- |
| `image_invalid` | Missing, empty or unsupported image |
| `image_too_large` | Image exceeds 15 MB |
| `image_service_unavailable` | Core cannot reach the image service |
| `image_service_timeout` | OCR exceeded the configured deadline |
| `image_identification_failed` | OCR/matching returned an unusable result |
| `image_unavailable` | Image support is not configured in core |

The browser previews the selected image immediately in the current conversation.
The server stores the message text and conversation state, not the image binary.
After a full refresh, the label is restored but the preview is not.

## Explicit debug and phone access

For host database clients, evaluation or API debugging, add the debug overlay:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml -f deploy/compose.debug.yaml up -d --wait
```

It binds PostgreSQL to `127.0.0.1:55432`, core to `127.0.0.1:18000` and language
to `127.0.0.1:18001`. Core's host API docs are at
<http://127.0.0.1:18000/docs>. The image service remains internal; use core or the
web UI to exercise it.

Host tools select existing database URLs with:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
```

Each runtime service loads only its own settings. Provider keys and the language
ledger URL are absent from core's container; migration/admin credentials belong
only to explicit setup jobs. Returning to the normal Compose configuration removes
debug bindings on recreated services.

Phone access uses the separate web-only overlay and the laptop's Wi-Fi address:

```powershell
$env:PHONE_HOST_IP = "192.168.1.7" # Replace with the current Wi-Fi IPv4 address
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml -f deploy/compose.phone.yaml up -d --no-deps --wait web
```

Open `http://192.168.1.7:8080/` on the phone. Only web is exposed to Wi-Fi; core,
language, image and database stay internal. This is for local testing on a trusted
network, not public deployment. If blocked, check Windows Firewall and router
guest/client isolation; do not disable the firewall.

Return web to its default localhost binding afterward:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --no-deps --wait web
Remove-Item Env:PHONE_HOST_IP
```

The phone overlay uses Compose's `!override` port replacement, which requires
Compose 2.24.4 or later. Browser request IDs use cryptographic
`getRandomValues`, available on HTTP LAN origins. Conversation bearer tokens are
generated by core.

## Updating an existing installation

After pulling source changes:

```powershell
uv sync --frozen
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Rebuild only the affected images when iterating locally:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml build web
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml build core
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml build language
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml build image
```

Run migrations only when the change includes new owned migration revisions. Normal
startup does not migrate or re-import. Do not regenerate credentials or reset the
database because an image changed.

## Stop, restart and reset

Stop while preserving the database and OCR models:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml down
```

Reuse existing containers:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml stop
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml start
```

Destructive reset of application data and OCR models:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml down --volumes
```

After a destructive reset, start PostgreSQL and repeat the explicit
migrate/grant/import/verify sequence before starting the full stack. If you also
intend to rotate credentials, deliberately remove the ignored runtime files and
rerun `pharmacy-db init-env` and `pharmacy-compose-setup`. Do not delete the
runtime files casually: the PostgreSQL volume's password must remain consistent
with them.

The separate old `compose.database.yaml` and Streamlit launcher are retired. Use
the maintained Compose configuration for database-only work too.

## Verification and recovery

Use `pharmacy-check` and frontend tests for offline checks:

```powershell
.\.venv\Scripts\pharmacy-check.exe
.\.venv\Scripts\pharmacy-archive.exe
```

```powershell
cd apps/web
npm ci
npm run build
npm run lint
npm test
```

The user-run disposable full-stack check is:

```powershell
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend
```

It creates and removes its own temporary stack and databases, uses mocked hosted
inference, and does not reuse the application volume. See [tooling](tooling.md)
for backup/restore prerequisites, quota status, schema/fixture export and
diagnostic locations.

If readiness fails, inspect the affected service's logs and configuration.
Missing or unavailable PostgreSQL is an error, not a signal to switch storage
modes. Do not publish environment files, expanded Compose configuration or private
logs.

## Troubleshooting

### `required variable ... is missing`

`.runtime/compose.env` is absent or incomplete. Run:

```powershell
.\.venv\Scripts\pharmacy-compose-setup.exe
```

If it refuses because the file exists, inspect the existing file deliberately;
do not delete it unless rotating credentials.

### `Run database_setup init-env first`

`.runtime/postgres.env` is absent. Run:

```powershell
.\.venv\Scripts\pharmacy-db.exe init-env
```

### The image service is unhealthy or photos fail immediately

Inspect logs:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml logs --tail=160 image core
```

If the log mentions a read-only `/home/app` or EasyOCR user network, the running
image is stale. Rebuild and recreate the image service:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml build image
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait image
```

The maintained image sets `HOME=/tmp` and writes EasyOCR user-network files under
`/models/user_network`.

### The first photo request is slow or times out

EasyOCR is downloading models. Keep internet access available and retry after the
download completes, or use the optional pre-download command above. Check volume
contents:

```powershell
docker run --rm -v pharmacy-assistant-architecture_easyocr_models:/models `
  --entrypoint sh pharmacy-assistant-image:local -c "ls -lh /models"
```

Expected files include `craft_mlt_25k.pth` and `latin_g2.pth`.

### The photo is displayed before the answer but disappears after refresh

Expected. The browser previews the selected file locally. Core stores the message
text and conversation state, not the image bytes. The current-session preview
remains visible after the server response.

### Typed questions fail while photo matching works

Typed questions use the hosted provider; photo matching does not. Check:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml logs --tail=120 language
```

Verify the selected provider key and model in `.runtime/compose.env`. Do not print
the key. There is no automatic provider switch or saved-answer fallback.

### Core is not ready

Check PostgreSQL and core logs:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml logs --tail=120 postgres core
```

Confirm migrations were run explicitly and the database volume matches the current
runtime credentials. Do not switch to SQLite or a file backend; it is not
supported.

### Port 8080 is already in use

Stop the process using it or deliberately change `WEB_PORT` in the environment used
by Compose. Do not expose core, language, image or PostgreSQL publicly to work
around a local port conflict.

### Compose configuration validation

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml config --quiet
```

This validates interpolation and the merged Compose model without starting
services. Do not publish the expanded output.
