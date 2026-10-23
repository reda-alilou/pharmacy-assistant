# Maintained administration tools

Run `uv sync --frozen` from the repository root after updating the workspace.
Operations live in the `pharmacy-ops` package under `tools/operations/`. They
depend explicitly on the owned service packages; running services do not depend
on administration or evaluation tools. Every command supports `--help` without
reading credentials or starting a service.

| Entry point | Responsibility |
| --- | --- |
| `pharmacy-db` | Explicit environment initialization, migrations, grants, catalogue import/verification and read-only legacy quota import |
| `pharmacy-backup` | Backup and verification in a newly created restore database; temporary conversations are excluded |
| `pharmacy-compose-setup` | Create a new ignored Compose environment from existing configuration; refuses overwrite |
| `pharmacy-compose-verify` | User-invoked isolated stack, browser and PostgreSQL verification |
| `pharmacy-export-contract` | Export the core OpenAPI schema without loading runtime settings |
| `pharmacy-fixtures` | Generate browser fixtures using real local facts and synthetic interpretation; no hosted calls |
| `pharmacy-quota` | Read PostgreSQL quota status without inference |
| `pharmacy-check` | Run maintained Python suites, optionally selected with repeated `--group` |
| `pharmacy-archive` | Verify every archived file and authoritative input relocation against the preservation manifest |

PowerShell uses executables under `.venv/Scripts/`, for example:

```powershell
.\.venv\Scripts\pharmacy-check.exe
.\.venv\Scripts\pharmacy-check.exe --group operations --group architecture
.\.venv\Scripts\pharmacy-export-contract.exe --output artifacts/operations/core.openapi.json
.\.venv\Scripts\pharmacy-fixtures.exe --output artifacts/operations/responses.json
```

Database imports now read `data/imports/`. Database actions retain their arguments. The default host environment
is `.runtime/postgres.env`; `--env-file` selects another file explicitly.
`pharmacy-db migrate` uses the two owned Alembic configurations. It does not
reset the database or import facts. `grant`, `import`, `verify` and `import-quota`
are separate actions. Existing environments and private ledgers stay in place;
do not run initialization again for the configured demo.

Checkpoint 1 adds a separate TypeScript CLI under `services/platform` for platform
SQL migrations, restricted grants, explicit administrator provisioning and
confirmed account status/role changes. Python `pharmacy-db` still owns only the
original core/language operations. Use the exact [platform commands](platform-accounts.md);
normal Compose now needs the additional private `.runtime/platform.env`. Neither
runtime service receives migration credentials, and no startup runs migrations.

`pharmacy-backup backup <new-path>` writes a new dump. `pharmacy-backup verify
<path>` creates and drops its own restore database, comparing catalogue facts
and quotas with the original. PostgreSQL 17 `pg_dump` and `pg_restore` must be on
PATH or installed in the standard Windows PostgreSQL 17 location.

The dump excludes `platform.sessions`, `platform.auth_throttles` and temporary
`platform.import_uploads`, while retaining accounts, activity, datasets, immutable
versions/columns/typed and original rows, dependencies and permanent import receipts.
Verification compares those tables when present and checks excluded state is
absent. Restored incomplete receipts cannot resume without excluded upload bodies.
Reapply explicit runtime grants after restoring. Checkpoint 3 also retains and
compares `analyses` and `analysis_sources` with their dependency registrations.
Dashboard/sharing relationships remain future work. [Current commands](analytics.md).

To read the host language ledger, first select its already configured environment:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
.\.venv\Scripts\pharmacy-quota.exe
```

## Isolated verification

The user starts Docker Desktop and invokes this explicitly:

```powershell
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/operations/container-check.json
```

The verifier creates a unique Compose project with generated test credentials and
a fresh volume. The language network blocks inference egress. It verifies fresh
and repeated migrations/import, all public facts, gateway errors, outages,
cooldowns, inference-free choices, transcript restoration, resets and persistence.
`--frontend` includes the real React integration test; it requires the frontend's
installed npm dependencies and an available Playwright browser.

After the ordinary internal-port checks, it exposes only this disposable
PostgreSQL cluster on a random localhost port. Eighteen additional tests use new
databases in that cluster for concurrent/cross-process reservation accounting,
budget resume and missing-ledger rejection, invalid-import rollback, read-only
legacy import, owned credentials and backup/restore. Hosted inference is mocked.
The helper refuses an ordinary application administrator/environment file.

The upgraded verifier explicitly migrates/grants platform before its five-service
startup and probes account cookies/CSRF/roles through Nginx. It uploads a CSV above
the former gateway body limit, validates/publishes it, checks microsecond timestamp
precision, full-version pagination and persistence after replacement. With
`--frontend` it also runs the real dataset browser lifecycle against production
Nginx, including versions, ownership, archive/delete and invalid-input recovery.
Checkpoint 3 extends this to exact statistical/advanced APIs, saved-source
dependencies and persistence, and the real analysis builder/chart/four-feature
browser flow. With `--frontend` it now expects 16 named checks plus the 18 assistant
PostgreSQL tests. Account/dataset suites remain included.
The dedicated
`npm --prefix services/platform run test:postgres` and
`npm --prefix apps/web run test:accounts` checks cover account adversarial and
browser scenarios against the separately user-started test cluster; they do not
start/stop containers. Dataset suites use `test:datasets` in each npm package.
Analytics suites use `test:analytics` in each package, including known-input,
precision, comparison-key and restored-definition checks. See
[Checkpoint 3 evidence](../validation/platform-checkpoint-3.md).
[Checkpoint 2 evidence](../validation/platform-checkpoint-2.md) records actual runs,
separately from pending normal-volume upgrade and review. Historical Checkpoint 1
and R7 reports remain unchanged.

Finally, it removes its project, test volume, generated environments and port
overlay. It preserves the application's project, volume, credentials and ledgers.
Reports default to ignored `artifacts/compose/`; diagnostics remain ignored in
`.runtime/`. Check `passed` and `isolated_resources_removed` in the result.

Normal demo startup/shutdown still uses `deploy/compose.yaml` and the existing
`.runtime/compose.env`. Startup never migrates or re-imports automatically.
The operations image installs the package and owned migration assets; it contains
no legacy source, Streamlit or private configuration.
Archive verification is a host-checkout operation; the administration image does
not include the 95 MB historical archive. Run `pharmacy-archive` from the workspace.
