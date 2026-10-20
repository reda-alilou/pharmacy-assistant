# Maintained evaluation tools

`pharmacy-evaluation` lives in `tools/evaluation/`. Its scoring, datasets,
runners and reporting modules depend on canonical service/shared packages.
They import neither the temporary `pharmacy_assistant` namespace nor Streamlit.
Install workspace commands with `uv sync --frozen`.

One entry point selects the task:

```powershell
.\.venv\Scripts\pharmacy-evaluate.exe --help
.\.venv\Scripts\pharmacy-evaluate.exe baseline --help
.\.venv\Scripts\pharmacy-evaluate.exe scenarios conversation --help
.\.venv\Scripts\pharmacy-evaluate.exe baseline offline --output artifacts/evaluation/backend-new.json
```

| Subcommand | Responsibility |
| --- | --- |
| `baseline` | Deterministic backend oracle checks, budgeted live extraction or baseline summary |
| `development` | Budgeted development/regression predictions, optional targeted case IDs |
| `held-out` | Execution against an explicitly verified current freeze |
| `interpretation` | Budgeted multilingual interpretation checks |
| `scenarios conversation` / `scenarios pharmacy` | Consolidated budgeted development scenario runners |
| `freeze` | Check development provenance and freeze current workspace inputs |
| `report` | Score recorded live evidence without new inference |
| `merge` | Merge explicitly recorded development rechecks with provenance |
| `datasets` | Dataset validation/profile information |

Help, dataset checks and the offline baseline do not require a model call.
Offline annotated extraction is an oracle for backend behavior, not a new model
accuracy measurement. Historical measured results and their limitations remain
unchanged. No held-out execution or hosted inference was performed during R5.

## Explicit live work

Live runners require provider configuration and the owned language PostgreSQL
URL. Select the existing host database environment with `DATABASE_ENV_FILE`;
provider fields still come from the existing private `.env` and process
environment. Evaluation settings have no core database credential or SQLite
ledger option. The normal language quota factory uses PostgreSQL directly.

Only execute a live run when requested. For an authorized development run:

```powershell
.\.venv\Scripts\pharmacy-evaluate.exe development --output artifacts/evaluation/development-new.json --max-requests 4 --interval 20
```

`--max-requests` counts outbound attempt reservations, including eligible
retries. Shared provider cooldowns and spacing still apply. `--resume` continues
the same report, validating saved results and PostgreSQL budget rows before
sending anything. A missing/inconsistent ledger fails closed. Completed cases
are not replayed, and interruption saves conservative reservation counts.

New outputs belong in ignored `artifacts/evaluation/`. The report writer and
lock refuse paths within `data/`, `reports/` and `archive/`. Preserve completed
evidence; use a new output path unless explicitly resuming it.

## Provenance and tests

Fingerprints identify the reorganized PostgreSQL runner and hash canonical
workspace implementations. Freeze inputs include service/shared/tool sources,
manifests, owned migrations, lockfile, authoritative import files and evaluation
datasets. Legacy compatibility files do not stand in for the implementations.
Old recorded reports can be scored as historical evidence; their earlier
fingerprints/freezes cannot silently authorize current live work.

`pharmacy-check` runs the maintained suites across services, packages, tools and
root architecture/integration directories. Shared fixtures live in
`tests/support/`; tests do not import other test modules. Offline evaluation
uses a test-only memory ledger, outside installed packages. Eighteen real
PostgreSQL checks run only through the explicit isolated verifier, including
budgeted evaluation pause/resume and no replay with mocked interpretation.

The [R5 coverage map](../validation/cleanup-r5-coverage.json) accounts for all
282 R1 Python methods, including React replacements and retired capabilities.
R6 removes the old root suites and forwarding modules; `pharmacy-check` remains
the maintained suite command. Historical inputs are read through the archive
manifest with preservation hashes; their old embedded paths are unchanged.
See [the archive guide](../../archive/README.md). Existing archived freezes are
readable as evidence and still cannot authorize current live execution.
