# Pharmacy Assistant — current state

Updated 2026-10-20. Read this and `DECISION_LOG.md` first. This file describes
implemented state and the handoff; it is not authorization to run its example
commands. Explore relevant files rather than scanning the entire repository.

## Checkpoint and authorization

Architecture checkpoints 1–5 of D018 passed user review. The user accepted the
React chat on laptop and phone. D020 approved a production-style repository
cleanup in checkpoints R1–R7, with review after each checkpoint.

**R1–R7 are complete, including the remaining D018 final validation.** R7 passed
clean-export installs/builds and the complete isolated stack. The user confirmed
the laptop demo works perfectly and explicitly waived the final physical-phone
review because it was optional for them. Campus network isolation is suspected,
not confirmed. Offline mobile browser checks passed; no new physical-phone pass
is claimed. Earlier laptop/phone acceptance remains historical evidence.

Read `docs/development/cleanup-plan.md` for the sequence and
`docs/validation/cleanup-r7.md` for final results and limitations. The saved starting
commit is `b1bca1693c6b351edd95f40aed4ced7e19e78520` on
`refactor/web-architecture`. Cleanup changes are uncommitted. Do not commit or
push automatically.

The user controls starting/stopping application services and isolated Compose
verification. Do not make hosted inference calls, scrape, change network/DNS
settings, regenerate credentials, alter private ledgers or touch application
volumes as routine cleanup. Image builds and brief self-removing, network-disabled
image checks are permitted. Stop any temporary containers when no longer needed.

## Implemented architecture

The patient interface is React/TypeScript/Vite with Tailwind and project-owned
shadcn/ui controls. It is French only, responsive and healthcare styled, with no
gradients or decorative side strips. Keep the accepted interface unchanged.
Nginx serves built assets and forwards same-origin `/api` requests to core.

Core and language are independently installable FastAPI services. Core owns
conversation, catalogue/directory matching, clarification, decimal pricing and
answers. Language owns provider adapters, model extraction/evidence validation
and shared quota/budget reservations. Core calls language over HTTP/JSON and has
no provider SDK or in-process fallback. Supported adapters remain Groq, Gemini
and OpenCode; selection is explicit, without automatic paid/provider fallback.
The selected hosted setup is Qwen through Groq, with explicit JSON-object output
and strict local validation. Preserve provider/model/prompt behavior during cleanup.

Both runtime services require their own PostgreSQL URL and verify storage before
serving. They own separate schemas, credentials and Alembic histories. Neither
service imports the other's implementation or accesses the other's tables.
Missing/unavailable PostgreSQL fails clearly; no file/SQLite runtime fallback
exists. Tests and offline tools may explicitly inject memory resources.

Conversations and transcripts persist temporarily with a 30-minute inactivity
expiry. Refresh/GET does not renew expiry or repeat a question. Failed messages
remain visible. POSTs are never automatically replayed; uncertain responses use
read-only recovery and explicit status verification. Reset invalidates state on
the server before clearing it locally. Valid offered choices avoid inference.

## Ownership and navigation

| Path | Canonical responsibility |
| --- | --- |
| `apps/web/src/app/` | Entry point, application shell and styles |
| `apps/web/src/features/chat/` | Chat components and temporary conversation state |
| `apps/web/src/features/results/` | Factual cards, sources and presentation |
| `apps/web/src/shared/` | Typed API/schema, shared UI and helpers |
| `services/core/src/pharmacy_core/` | `api/`, `conversation/`, `medications/`, `pharmacies/`, `clients/`, `storage/postgres/`, `config.py` |
| `services/language/src/pharmacy_language/` | `api/`, `extraction/`, `providers/`, `quota/`, `storage/postgres/`, `config.py` |
| `packages/contracts/src/pharmacy_contracts/` | Shared schemas, protocols and errors |
| `packages/infrastructure/src/pharmacy_infrastructure/` | Connection/environment/workspace helpers and verified historical input resolution |
| `tools/operations/src/pharmacy_ops/` | Explicit setup/import/migrations/backup, Compose verification, schema/fixture export, quota/archive checks |
| `tools/evaluation/src/pharmacy_evaluation/` | Datasets, scoring, budgeted runners, reporting/freeze/resume validation |
| `tests/architecture/`, `tests/integration/`, `tests/support/` | Cross-package boundaries/integration and shared fixtures |
| `deploy/` | Maintained Compose files and `nginx/nginx.conf` |

The root is a virtual uv coordinator with six installable members and one
lockfile. Each member owns its dependencies and tests. R6 removed the legacy
`src/pharmacy_assistant` code, duplicate root tests/helpers, Streamlit launcher/UI,
collection/enrichment/overlapping commands, root Alembic configuration and old
database-only Compose file. There are no final compatibility shims.
Only the maintained `tests/__init__.py` remains as a root test-package marker.

After R6, the user explicitly authorized removing verified ignored leftovers,
including nested obsolete caches and scratch directories. Root `.streamlit/`,
`src/`, `migrations/`, `reports/` and `tmp/` are removed, as are obsolete empty
directories and the throwaway R5 evaluation environment. Regenerable bytecode
caches were pruned. The primary `.venv`, `.runtime`, `.env`, editor settings,
active npm dependencies and current validation evidence remain untouched.
Previously ignored raw/staging data moved byte-preserved to ignored
`archive/local/`, with its own local hash manifest; do not add it to Git or confuse
it with the public archive manifest. The follow-up record is
`docs/validation/cleanup-r6-housekeeping.json`. Earlier R6 baseline JSON describes
the state before this explicitly authorized local housekeeping.
The follow-up removed 9,629 obsolete files, preserved 6,433 ignored raw/staging
files with hashes after relocation, and passed 38 focused offline checks (18
PostgreSQL checks intentionally skipped; no stack started). All 204 canonical
source hashes and the public archive manifest remain unchanged. No bytecode
caches were regenerated by the checks. The active `data/` tree now contains only
`imports/` and `evaluation/`. R7 subsequently validated this cleaned tree.

## Data and archive

Authoritative inputs now live in `data/imports/`:
`ammps_medications_enriched.jsonl` (9,936 presentations) and
`pharmacies_rabat.jsonl` (327 records). The relational import reconstructs 7,302
medication groups, 3,128 linked observations and 1,260 conflicts. Preserve source
IDs, prices/missing values, provenance and conservative grouping; 1,126
presentations have no recorded public price. Migration revisions/SQL semantics
and all input bytes are unchanged.

`data/evaluation/` contains active annotations/regressions. Raw snapshots,
historical secondary data, public reports/screenshots and superseded documents
are preserved unchanged under `archive/historical/<original-path>`.
`archive/manifest.json` maps 1,002 historical files and two active input relocations
with exact R1 hashes and original Git identities. Git attributes protect their
bytes. `pharmacy-archive` checks all 1,004 mapped files.

Maintained evaluation tools use the read-only archive resolver for missing old
input paths, validating hashes. Historical reports, source paths, model outputs
and freezes are not rewritten. New fingerprints/freezes hash canonical workspace
implementations and relocated inputs; old freezes cannot authorize current live
execution. Generated reports belong in ignored `artifacts/`; writes/locks reject
`data/`, `reports/` and `archive/`.

Historical frozen held-out results were 34/40 backend cases, intent F1 92.86%,
entity slot F1 95.91%, 48/48 schema-valid completions. Later correction results
were 14/14 backend cases and 20/20 schema-valid completions, raw slot F1 85.71%.
These belong to earlier versions/development rechecks, not a fresh current
benchmark. Synthetic annotations were assistant-authored/reviewed; independent
native-speaker validation is not claimed. No hosted inference or held-out
execution is part of cleanup.

## Commands and evidence

Run `uv sync --frozen` after updating the workspace. The maintained Python runner
is `.\.venv\Scripts\pharmacy-check.exe`; old root unittest discovery is retired.
Frontend checks run from `apps/web`: `npm run build`, `npm run lint`, `npm test`.
Playwright uses installed Edge on Windows by default and closes its temporary
Vite test server. Artifacts are ignored under `artifacts/web/`.

Operations expose `pharmacy-db`, `pharmacy-backup`, `pharmacy-compose-setup`,
`pharmacy-compose-verify`, `pharmacy-export-contract`, `pharmacy-fixtures`,
`pharmacy-quota`, `pharmacy-archive` and `pharmacy-check`. Evaluation uses
`pharmacy-evaluate` subcommands. See `docs/operations/tooling.md` and
`docs/development/evaluation-tools.md` for arguments and explicit live budgets.

The configured four-container demo uses `.runtime/compose.env` and
`deploy/compose.yaml`; its default web address is localhost:8080. Existing
`.env`, `.runtime/postgres.env`, named volume, project/service names and phone/
debug overlays remain unchanged. Do not print credentials or expanded Compose
configuration. Normal startup does not migrate/import. The user may start/stop
the stack using `docs/operations/setup.md`; `down` without `--volumes` preserves data.

R5 passed 238 offline Python tests, 22 browser tests, all ten isolated stack
checks and all 18 PostgreSQL tests. Its complete 282-method coverage map is
`docs/validation/cleanup-r5-coverage.json`; frozen R1–R5 JSON remains evidence of
those checkpoints, not a description of current file paths.
R6 passed 247 offline Python tests, 22 browser tests, all ten isolated stack
checks and all 18 PostgreSQL tests with no skips in the isolated run. Six package
wheels/source distributions, all four image builds, installed-image checks,
historical rescoring and original OpenAPI preservation passed. All 1,010 R6
preserved files match their R1 hashes. The lock removed 26 unused dependencies;
the retained 39 entries did not change versions. The test stack removed its own
resources and did not modify the application volume or private state. No hosted
inference occurred. No containers remained running at the R6 handoff.
R6 results: `docs/validation/cleanup-r6-baseline.json`,
`cleanup-r6-removals.json`, `cleanup-r6-images.json` and `cleanup-r6-container.json`.
Detailed R6 logs/builds belong in `artifacts/cleanup/r6/`.

R7 verified a clean export of 1,290 publishable files from the uncommitted tree,
not a remote clone. Six frozen, noneditable independent installs, six package
builds, four production image builds/installed-image checks, fresh frontend
install/build/lint, unchanged contracts/types and archive verification passed.
There were 247 passing offline Python tests, 22 passing offline browser tests,
all ten isolated stack checks and all 18 PostgreSQL tests (zero isolated skips).
Offline PostgreSQL skips were covered by that isolated run. Two preexisting
frontend hot-refresh lint warnings remain; there are no lint errors.
No automated hosted inference occurred and no current model accuracy was measured.
The user reported the laptop demo works perfectly and waived the final phone
review. See `docs/validation/cleanup-r7-user-review.json` for their exact statement.
Temporary test resources, clean export and disposable environments were removed;
compact evidence/builds remain under `artifacts/cleanup/r7/`. The user's demo
stack was stopped afterward at the user's explicit request; its database volume
was preserved. Service startup/shutdown remains user-controlled. Current results:
`docs/validation/cleanup-r7-baseline.json` and
the linked evidence in `docs/validation/cleanup-r7.md`. Engineering cleanup is
finished. No automatic commits, pushes or further feature work are authorized.

Current explanations: `docs/architecture/overview.md`, `docs/operations/setup.md`,
`docs/project/data-and-evidence.md` and `docs/project/requirements-audit.md`.
The related-work study and final submission/presentation preparation remain
separate work after engineering cleanup; do not infer authorization to start them.
