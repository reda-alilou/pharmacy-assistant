# Checkpoint 2 setup and checks

Current code also includes Checkpoint 3 analytics. Use the
[current analytics upgrade/check guide](analytics.md) for the latest migration,
test scripts and 16-check isolated verifier; this page retains the CSV workflow.

The user controls container startup/shutdown and all isolated stack lifecycles.
No agent command upgrades the normal volume, regenerates credentials, imports
samples automatically or runs hosted inference. Stay on
`feat/pharmaceutical-analytics`; no commit/push is part of this checkpoint.

## Upgrade

If Checkpoint 1 has not yet been installed against the normal application volume,
first follow [platform account setup](platform-accounts.md). The migration command
applies all owned account/dataset/analysis revisions; do not provision an existing
administrator again or recreate `.runtime/platform.env`. If Checkpoint 1 is
already installed, keep its existing configuration and accounts. From the root,
the **user runs**:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build platform platform-setup web database-setup
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait postgres
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

This preserves the original project/volume and source inputs. Never edit the old
migrations, initialize credentials again or run an import to “repair” an upgrade.
The runtime refuses missing dataset tables; it does not migrate them at startup.
The grant command deliberately adds only the new platform privileges and does not
rotate passwords. Core/language retain their own schemas and credentials.

Open <http://127.0.0.1:8080>, log in, choose **Mes données**, then **Importer un
CSV**. Select a file, inspect/correct encoding/delimiter/types/missing markers,
describe the dataset, validate the entire file, and explicitly publish. There is
no partial successful import. Reopen a dataset to search/filter/sort, inspect
column/completeness profiles and browse versions. **Ajouter une version CSV**
preserves all earlier versions. Metadata saving, archiving and confirmed deletion
are separate explicit actions. Deletion is blocked by registered dependencies.

The sample download in the upload screen contains 28 deduplicated real source
presentations with missing prices and linked provenance. It is imported through
the same pipeline, never copied from Python-private tables. See
[sample provenance](../../apps/web/public/samples/README.md). To explicitly export
the complete dated pharmaceutical input to a new local CSV for testing:

```powershell
node tools/samples/export-pharmaceutical-csv.mjs --output artifacts/pharmaceutical-catalogue.csv
```

The command refuses existing output, uses no network/database/provider and leaves
the authoritative JSONL unchanged. All 9,936 source records and their raw source
attribution/conflicts remain in the preserved input; dates/prices are observations,
not current offers or clinical comparisons. Analytics and dashboards are later work.

## Verification

Host-only checks (no container lifecycle):

```powershell
npm --prefix services/platform run build
npm --prefix services/platform test
npm --prefix apps/web run build
npm --prefix apps/web run lint
npm --prefix apps/web test
.\.venv\Scripts\pharmacy-check.exe
```

The **user starts** the same dedicated test database used in Checkpoint 1:

```powershell
docker compose -f deploy/compose.platform-test.yaml up -d --wait
```

Then run the real account/dataset persistence and browser checks:

```powershell
npm --prefix services/platform run test:postgres
npm --prefix services/platform run test:datasets
npm --prefix apps/web run test:accounts
npm --prefix apps/web run test:datasets
```

Tests check the dedicated cluster identity and create/remove random test
databases, not the application database. They cover migration from populated
Checkpoint 1 tables, permissions, validation, atomic rollback, full-version
search/filter/count/sort, version pinning, dependency safeguards, expired uploads,
account disabling, preserved original values and backup/restore. Dataset checks
also measure 9,936-row, 25,000-row and 1,000,000-cell fixtures; results are local
measurements in ignored `artifacts/platform-cp2/dataset-benchmarks.json`.
Real browser tests use temporary host Vite/Express processes and synthetic
accounts, with no credential-bearing network traces. Avoid running multiple
heavy browser/benchmark suites simultaneously on a resource-constrained laptop.

For production images/Nginx and the complete isolated assistant regression,
the **user runs** from the root:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/platform-cp2/full-stack-final.json
```

The verifier now additionally uploads a CSV above the former 32 KiB gateway
limit, validates/publishes it, checks six-digit timestamp precision, queries bounded
pages and checks dataset persistence after whole-stack replacement. It also runs
the dataset browser lifecycle through production Nginx. With `--frontend`, the
Checkpoint 2 snapshot expected 14 named checks; current Checkpoint 3 expects 16.
It includes the original 18 assistant PostgreSQL
checks and removes only its own isolated resources. It does not migrate the
normal volume. Check the [actual checkpoint evidence](../validation/platform-checkpoint-2.md)
for which runs passed; historical Checkpoint 1/R7 results do not validate new work.

When finished, the **user stops** the dedicated host-test database:

```powershell
docker compose -f deploy/compose.platform-test.yaml down
```

Normal shutdown still preserves the database volume:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml down
```

Backups now retain dataset/version/row/column/dependency and permanent receipt
data while excluding upload bodies/configurations/reports, sessions/throttles
and temporary patient history. Restored incomplete receipts cannot resume
without their excluded staging content. Reapply runtime grants explicitly after
restore. Sharing/analysis/dashboard backup relationships remain later checkpoints.

Stop for user review before Checkpoint 3.
