# R2 — Independently packaged backends

Status: **complete and reviewed**. All nine user-run isolated Compose checks
passed. The user subsequently authorized R3; see `cleanup-r3.md` for current work.
The following describes the R2 handoff; its JSON evidence remains frozen.

## What changed

The real backend implementations now live in four installable workspace members:

| Package | Source | Owns |
| --- | --- | --- |
| `pharmacy-core` | `services/core/src/pharmacy_core` | API, conversations, medication/pharmacy logic, PostgreSQL storage, HTTP language client |
| `pharmacy-language` | `services/language/src/pharmacy_language` | API, provider adapters, extraction prompt/validation, quotas and PostgreSQL quota storage |
| `pharmacy-contracts` | `packages/contracts/src/pharmacy_contracts` | Shared interpretation/HTTP schemas, protocols and errors |
| `pharmacy-infrastructure` | `packages/infrastructure/src/pharmacy_infrastructure` | Environment loading, connection creation, root discovery, optional migration helper |

Each has its own `pyproject.toml`, `src` package and focused tests. The root uv
workspace coordinates the existing lockfile. Runtime images install only the
selected service and its declared shared dependencies as non-editable packages.
They contain no legacy package, repository checkout, peer implementation or
Streamlit. Core also contains no provider SDK. Language receives no core code.

Core is organized by API/routes, conversations, medications, pharmacies,
PostgreSQL storage and HTTP clients. The API lifecycle and exception handling
remain in `api/app.py`; separate route groups preserve existing names, request
schemas and operation IDs. Providers share the unchanged extraction prompt and
retry-header parsing without importing another provider's implementation.

Settings now belong to their service. Shared environment loading maps only the
requesting settings class's fields; core receives no provider key/language URL
credential and language receives no core database credential. Repository paths
use `PHARMACY_PROJECT_ROOT`, recognized workspace discovery or the explicit
working directory for installed applications, rather than fixed parent depth.
Containers explicitly set the root to `/app`.

Each service owns an Alembic configuration and migration history. The initial
revision files are byte-preserved; schema/version-table identities and SQL
semantics remain unchanged. The root Alembic configuration temporarily forwards
old operations to those owned histories. No migration was executed against the
application database.

## What intentionally remains until later checkpoints

The old `src/pharmacy_assistant` import paths still exist for retained tooling
and tests. Moved runtime modules are thin aliases to the new implementations,
not duplicate implementations. The legacy combined settings and collection/UI
tools remain until their R5/R6 migration/removal gates. Do not mistake those
temporary files for the final layout.

File-mode startup and SQLite quota selection are still present for compatibility
until **R4**. PostgreSQL remains the selected Compose runtime. The React app is
still at `frontend/` until **R3**. The operations Dockerfile is already separated,
but its administrative CLI is still the legacy tool until **R5**.

Evaluation provenance/freeze checks now include canonical workspace source,
member manifests and service migrations. Hashing only old aliases would miss
real changes; new guards explicitly detect canonical changes. Historical
predictions, annotations, reports and freezes were not rewritten or rerun.

## Commands

Update the existing local environment from the lockfile, without starting apps:

```powershell
uv sync --frozen
```

Canonical API entry points are `pharmacy_core.api.app:app` and
`pharmacy_language.api.app:app`. Examples for explicit host development:

```powershell
uv run --package pharmacy-core uvicorn pharmacy_core.api.app:app --host 127.0.0.1 --port 8000
uv run --package pharmacy-language uvicorn pharmacy_language.api.app:app --host 127.0.0.1 --port 8001
```

Choose service storage/environment deliberately; the default file mode is not
removed until R4. PostgreSQL host development uses the established debug overlay
and private `.runtime/postgres.env`. The user controls all service lifecycle.

Service migration configuration is now `services/core/alembic.ini` and
`services/language/alembic.ini`. Each service exposes a `migrations` dependency
extra for explicit Alembic use; runtime installations need not include Alembic.
The existing explicit database-setup job still migrates both owned histories.

Compose keeps its existing name, services, persistent volume, runtime credentials,
ports and optional debug/phone overlays. It now builds `services/core/Dockerfile`,
`services/language/Dockerfile` and `tools/operations/Dockerfile` independently.
The frontend image and API forwarding behavior are unchanged.

After images build, the user runs the temporary verification stack explicitly:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.compose_verify --run-isolated --frontend --output docs/validation/cleanup-r2-container.json
```

The added `--output` option allows checkpoint-specific evidence. Without it,
verification writes to a unique report in ignored `artifacts/compose/`; frontend
captures also go there. The final check caught a capture written to the old
checkpoint 5 screenshot path. That screenshot was restored byte-for-byte from
the saved commit, and the capture path was corrected. Historical `data/` and
`reports/` have no changes relative to the saved baseline.
Existing `--run-isolated`/`--frontend` arguments and isolation/cleanup rules remain.
Fixtures injected into images now use canonical packages, without any new
production route or inference fallback.

## Checks and evidence

- All backend/setup images built from the frozen workspace lockfile.
- Offline network-disabled image helpers verified that each API imports without
  the legacy/peer package and that core contains no provider SDK or Streamlit.
- Both OpenAPI schemas exactly match R1's canonical hashes, including the core
  schema consumed by the frontend. No frontend types or factual UI changed.
- Owned migrations generate SQL independently in the setup image with no database
  or inference access. The initial SQL also remains checked against model metadata.
- Independent settings, contracts, root-discovery and canonical hash/import guards
  pass. An existing 50ms deadline test was timing-sensitive when quota reservation
  ran in a worker thread. The test now waits for the first mocked provider attempt
  before expiring its deadline; production timeout/retry behavior is unchanged.
- The full root regression suite passed: 276 passed, ten opt-in PostgreSQL tests
  skipped because the host database was stopped (286 discovered). Eight additional
  owned-package tests passed. PostgreSQL behavior was exercised in the isolated
  Compose verification, rather than against the application database.
- All nine real-stack checks passed, including frontend restore/reset/selection,
  service outages, cooldowns and persistence across container/stack replacement.
  The test utility removed its own resources, and no containers remained running
  at handoff. No application volume was modified.
- Source/wheel builds for all five workspace packages and offline lock verification
  passed. Existing dependency versions, prompt text/version and initial migration
  bytes were preserved; four local workspace packages were added.

Detailed logs/build products stay in `artifacts/cleanup/r2/` rather than historical
`reports/`. Public evidence is `cleanup-r2-images.json`, the final
`cleanup-r2-baseline.json`, and the user-run `cleanup-r2-container.json` beside this
guide. No hosted inference or scraping is included in verification.

Stop for user review before **R3: organize the frontend**. Do not perform later
PostgreSQL-only or deletion work merely because the new packages exist.
