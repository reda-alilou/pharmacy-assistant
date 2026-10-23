# Pharmaceutical analysis platform — datasets and assistant

A local pharmaceutical data platform under construction. Accounts, profiles,
guided CSV imports, private immutable versions, exploration, analytics and private
saved definitions now use a real TypeScript/Express service. Dashboards, sharing
and the administration workflow are future checkpoints. The existing Moroccan pharmacy assistant
remains separately accessible at `/assistant`.

Checkpoint 2's 14 rebuilt-image checks and 18 assistant PostgreSQL tests passed;
the user authorized Checkpoint 3. Final analytics host/browser checks and all
16 isolated full-stack checks pass, with all 18 assistant PostgreSQL tests passing
and isolated cleanup confirmed. Checkpoint 3 awaits user review; Checkpoint 4 has
not started. Normal-volume upgrade remains a separate user-run step.
See [actual Checkpoint 3 evidence](docs/validation/platform-checkpoint-3.md).

The assistant is a local challenge demo and learning project for pharmacy requests.
A French React chat connects to a core FastAPI service; a separate language
service uses hosted Qwen extraction through Groq. Local code matches medication
and pharmacy records, manages clarification and temporary conversations, and
calculates prices from recorded facts. Backend interpretation and answers support
French, Arabic, Darija and mixed language; the patient interface is French only.

For a self-contained explanation of the current system, read
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md): architecture and request flow,
service communication, database tables and relationships, data collection and
transformation, repository structure, configuration and validation evidence.

## Run the configured demo

Follow the [Checkpoint 3 upgrade](docs/operations/analytics.md), including the
one-time account setup if not already applied. Reuse
existing private credentials and the database volume. After that setup, with
Docker Desktop running, from the repository root:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080> for accounts and **Mes données**, or
**Mes analyses** for analytics, or <http://127.0.0.1:8080/assistant> for the assistant. After source updates, build the affected images
first, or build all application/setup images:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build
```

Stop the stack while preserving its database:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml down
```

Startup never migrates or re-imports data. Existing credentials, migration
revisions, Compose project/service names and named volume are retained.
Fresh checkout instructions and explicit setup actions are in the
[setup guide](docs/operations/setup.md). Phone testing is in
[the frontend guide](apps/web/README.md#test-on-a-phone-over-wi-fi).

New typed questions require available hosted inference and internet access.
Valid offered clarification choices can work without another model call.
There is no automatic provider switch, paid fallback or saved-answer fallback.

## Implemented behavior

Registration (analyst only), login/logout, own-profile/name/password editing,
PostgreSQL account sessions, CSRF checks and login throttling are implemented.
Administrator provisioning is explicit. Dataset upload/configuration, full CSV
validation/report, atomic publication, immutable versions, metadata editing,
archive/restore and guarded deletion are implemented. Exploration includes
full-dataset search/typed filters/sort/pagination, original cells and column/
completeness profiles. Checkpoint 3 adds aggregations, pharmaceutical templates,
KPI/bar/line/histogram/pie/scatter charts, four advanced features (missingness,
IQR outliers, editable chart recommendations, explicit dataset/version comparison)
and private version-pinned saved configurations. Dashboard construction, sharing
and administration remain future work. See [account security](docs/architecture/platform-api.md),
[dataset API](docs/architecture/datasets-api.md) and
[analytics/calculation contract](docs/architecture/analytics-api.md), plus
[sample provenance](apps/web/public/samples/README.md).

The retained assistant provides:

- Validated multilingual intent/entity extraction, with raw spans kept separate
  from inherited conversation context.
- Medication identity, strength, form and presentation matching; ambiguous
  results require clarification. Reviewed aliases and spelling suggestions never
  silently select an uncertain product.
- Follow-ups, explicit offered choices and complete-package quantity totals.
  Arithmetic uses recorded prices and decimal rules; missing prices stay unknown.
- Source-aware medication cards and a partial Rabat pharmacy directory with
  recorded names, addresses and phone numbers.
- Temporary conversations with a 30-minute inactivity expiry, refresh restoration,
  failed-message visibility, explicit retry and server-side reset. Refresh never
  repeats a question or renews expiry.
- Shared PostgreSQL quota reservations and cooldowns, explicit evaluation budgets,
  and safe errors when inference or storage is unavailable.

Try `Quel est le prix de ABIP ?`, choose a presentation, then ask
`Et pour deux boîtes ?`. Recorded prices are historical observations, not live offers.
The [demo guide and spoken script](docs/project/demo-guide.md) provides startup
commands, a presentation sequence, verified examples and an architecture walkthrough.

## Repository structure

| Location | Responsibility |
| --- | --- |
| `apps/web/` | Router/accounts, CSV/exploration, analysis builder/charts/saved definitions, separate assistant/tests |
| `services/platform/` | Express accounts, CSV/datasets, analytics/saved settings, ownership, SQL migrations/admin CLI |
| `services/core/` | Conversation, matching, pricing, HTTP API and owned migrations |
| `services/language/` | Provider adapters, extraction validation, quotas and owned migrations |
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
and are independently installable from one lockfile. Streamlit, the old
`pharmacy_assistant` package, collection/enrichment workflows and obsolete root
tests have been retired after their useful coverage was migrated.

Local environments, credentials and generated output remain ignored. Verified
obsolete scratch directories and legacy caches have been removed. Previously
ignored raw downloads/staging data are preserved privately in `archive/local/`;
they are not application inputs or part of the tracked historical archive.

## Checks

After `uv sync --frozen`, run maintained offline Python checks:

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

Platform checks additionally use `npm --prefix services/platform test` and the
dedicated database/browser commands in [analytics operations](docs/operations/analytics.md).
The user starts/stops the dedicated test database and isolated stacks.

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
coverage is partial and limited to Rabat. Voice, durable patient history and public deployment remain outside the
implemented scope. Platform accounts are separate from temporary patient chats. Hosted free inference
can be interrupted by quotas and provider availability. No local model training
or universal extraction accuracy is claimed.

## Project status and navigation

Architecture checkpoints 1–5 and cleanup R1–R7 are complete. R7 passed independent
installs/builds, 247 offline Python tests, 22 browser tests, all ten isolated stack
checks and all 18 PostgreSQL tests. The user accepted the laptop demo and waived
the final physical-phone review; automated mobile checks passed. See
[the final R7 evidence and limits](docs/validation/cleanup-r7.md). Follow
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the current handoff and
[DECISION_LOG.md](DECISION_LOG.md) for approved Full Stack CdC decisions, checkpoint status and remaining work,
and the [historical decision log](docs/development/decisions-2026-10-19-20.md)
for completed architecture-phase choices. Proposals are not implemented features. The
[cleanup plan](docs/development/cleanup-plan.md) defines the checkpoint gates.

Read the [current architecture](docs/architecture/overview.md),
[requirements audit](docs/project/requirements-audit.md), and
[archive guide](archive/README.md). The related-work study and final presentation
preparation remain submission work; they are separate from repository cleanup.
