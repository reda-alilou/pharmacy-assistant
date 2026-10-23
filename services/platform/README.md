# Platform service — accounts, datasets and analytics

Express 5 / TypeScript owns accounts, private CSV datasets, analytics/saved
definitions and the `platform` schema. It has no Python
implementation dependency, provider key, catalogue query or patient-history API.
Dashboard and sharing services now extend this foundation; administration workflows
remain future work. Checkpoint 4 host checks and the final production gate pass,
including the frontend source-switch mapping fix; ready for user review.

From this directory, Node 22.23.2+:

```powershell
npm ci
npm run build
npm test
npm run admin -- --help
```

`npm run test:postgres` requires the dedicated test PostgreSQL service described
in [platform setup](../../docs/operations/platform-accounts.md). It refuses to
use an application URL. Migrations are checksummed SQL files in `migrations/`,
applied transactionally under an advisory lock by an explicit command. Startup
checks readiness and runtime isolation; it never migrates or grants privileges.
The runtime image contains compiled JavaScript, production dependencies and owned
migrations. Administrative credentials belong only to `platform-setup` jobs.

`npm run test:datasets` uses that same dedicated cluster for migration from
populated accounts, CSV validation, atomic failure, immutable versions, ownership,
typed queries, measured limits and backup/restore. The dataset service owns parser,
contracts, queries and lifecycle transactions under `src/datasets/`; it never
reads peer tables. `0002_datasets.sql` extends the preserved account revision.

`npm run test:analytics` verifies exact and large-decimal statistics, advanced
missingness/IQR/recommendations/comparison, source permissions, saved settings,
dependency migration/deletion and dump/restore. `src/analytics/` owns definitions,
SQL engines and lifecycle routes; `0003_analyses.sql` adds only owned tables and
extends activity. Explicit grants preserve peer isolation and immutable source
tables. No new dependency/library is needed for the numeric engines.

`npm run test:dashboards` verifies populated Checkpoint 3 upgrade, constrained
filters, separate grants, original-owner revision approvals, copies/revocation,
concurrent saves and maintained backup/restore. `src/dashboards` owns contracts,
filter mapping and lifecycle; `src/sharing` owns grants and readable owner review;
`src/access.ts` keeps dataset and result permissions distinct. Migration
`0004_dashboards_sharing.sql` preserves earlier revisions. See
[API/permissions](../../docs/architecture/dashboards-sharing-api.md) and
[current upgrade/tests](../../docs/operations/dashboards-sharing.md).

See [API and security contract](../../docs/architecture/platform-api.md),
[setup and test commands](../../docs/operations/platform-accounts.md), and
[dataset API](../../docs/architecture/datasets-api.md),
[dataset upgrade/tests](../../docs/operations/datasets.md), and
[Checkpoint 2 evidence](../../docs/validation/platform-checkpoint-2.md).
Current [analytics API](../../docs/architecture/analytics-api.md),
[upgrade/tests](../../docs/operations/analytics.md), and
[Checkpoint 3 evidence](../../docs/validation/platform-checkpoint-3.md).
