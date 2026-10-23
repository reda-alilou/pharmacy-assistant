# Checkpoint 3 — analytics upgrade and checks

The user controls every container lifecycle. Keep the existing branch, private
configuration, administrator, migration history and application volume. No new
credentials, automatic source import, hosted inference or Git publication is
required. This page retains the analytics workflow. Checkpoint 4 now implements
dashboards/collaboration; use the [current upgrade/check guide](dashboards-sharing.md)
for all four migrations and the current 18-check isolated gate.

## Existing workspace upgrade

If platform accounts were never installed on the normal volume, first follow
[initial platform setup](platform-accounts.md) once. Otherwise reuse
`.runtime/platform.env` and the existing administrator. The current explicit
migration command now applies all four owned revisions without modifying old ones.
From the root, the **user runs**, in order:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build platform platform-setup web database-setup
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait postgres
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Startup checks readiness and never migrates or recreates tables. Grant adds only
owned runtime privileges; no password rotation. Existing imported versions and
profiles are retained. New imports and cp3-v1 analyses use the higher-scale mean;
old immutable profiles are not backfilled. Core/language ownership and volume
identity stay unchanged. See [the calculation contract](../architecture/analytics-api.md).

Open <http://127.0.0.1:8080>, log in and choose **Mes analyses**, or open a dataset's
**Analyse** tab to start with its selected version. Select source/version, filters,
operation/grouping/chart and **Calculer l’analyse**. Results report denominators,
missing values, limits and source versions. Run the pharmaceutical templates on
the attributed sample, or configure arbitrary supported uploaded columns.

For the four advanced features choose **Type d’analyse**: missingness, IQR,
recommendations or comparison. Recommendations create editable chart definitions.
Comparisons need explicit source mappings; row matching additionally requires
explicit complete unique keys. Duplicate keys are rejected rather than guessed.
Outlier flags do not change data. Save with a title only after reviewing the
result; reopen from **Mes analyses**, then explicitly recalculate. Importing a new
version never changes an existing saved source. Source-picker refresh only reloads
available choices and preserves the selected version.

Deleting an analysis requires confirmation and removes its dependency registrations;
datasets remain. A dataset with a saved dependent analysis cannot be deleted until
the analysis is deleted or explicitly updated to another valid source.
Dashboards and sharing are implemented in Checkpoint 4. Administrative supervision
remains future work.

## Host verification

```powershell
npm --prefix services/platform run build
npm --prefix services/platform test
npm --prefix apps/web run build
npm --prefix apps/web run lint
npm --prefix apps/web test
.\.venv\Scripts\pharmacy-check.exe --group operations --group architecture
```

The **user starts** the dedicated temporary PostgreSQL cluster:

```powershell
docker compose -f deploy/compose.platform-test.yaml up -d --wait
```

Tests then run against random databases in that verified dedicated cluster:

```powershell
npm --prefix services/platform run test:postgres
npm --prefix services/platform run test:datasets
npm --prefix services/platform run test:analytics
npm --prefix apps/web run test:accounts
npm --prefix apps/web run test:datasets
npm --prefix apps/web run test:analytics
```

No test starts/stops containers or selects an application URL. Browser harnesses
start temporary host Vite/Express processes and omit secret-bearing traces.
Run heavy browser/large-import benchmarks sequentially to avoid CPU contention.
Local analytics benchmarks are in `artifacts/platform-cp3/analytics-benchmarks.json`.
The existing 10-second per-statement/60-second request limits remain; errors clear
stale results. Performance numbers are local measurements, not production SLAs.

## Production images and complete isolated stack

After final source changes, the **user runs**:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/platform-cp3/full-stack.json
```

The Checkpoint 3 baseline recorded **16 named checks** with `--frontend`, including
exact aggregates/four advanced APIs/saved dependencies through Nginx, saved-source
persistence after whole-stack replacement, real dataset and analytics browser
workflows, and all 18 assistant PostgreSQL tests. It controls only its own random
project/volume and cleans those resources; it never upgrades the normal volume.
The user invokes this lifecycle. [Actual evidence](../validation/platform-checkpoint-3.md)
records which gates ran and passed; earlier checkpoint reports remain historical.
The current verifier adds dashboard/collaboration probes for **18 named checks**;
use the current guide linked above for its commands and evidence.

When finished, the **user stops** the dedicated test database:

```powershell
docker compose -f deploy/compose.platform-test.yaml down
```

Normal shutdown preserves the application volume:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml down
```

Backup/restore now retains analyses and their sources/dependencies, plus prior
account/dataset data, while excluding live sessions/throttles, upload staging and
temporary patient history. Reapply explicit runtime grants after restore.
The user authorized Checkpoint 4 after the analytics review. Stop for user review
before Checkpoint 5.
