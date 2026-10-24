# Checkpoint 4 — dashboards/collaboration upgrade and checks

This page retains the Checkpoint 4 workflow/evidence. Current code adds Checkpoint 5
administration; use the [current guide](administration.md) for all five migrations
and the 20-check verifier. Historical CP4 reports remain unchanged.

The user runs every container lifecycle command. Reuse existing private
configuration, administrator and volume; do not regenerate credentials. If the
normal volume has never had platform accounts installed, first follow
[the one-time platform setup](platform-accounts.md). Otherwise the explicit
migration command applies all four revisions without changing earlier SQL.

## Upgrade the existing normal volume

From the repository root, the **user runs**, in order:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build platform platform-setup web database-setup
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait postgres
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

No migration/import runs at service startup. Migration `0004_dashboards_sharing.sql`
adds only the owned domain; previous SQL/Alembic revisions, typed/original source
cells and volume identity remain intact. Grant extends only platform runtime
privileges and does not rotate an existing password. Backup includes dashboards,
source dependencies, grants and onward approvals; sessions/throttles, staging
and temporary patient history remain excluded. Explicit grants are needed after
a restore. Administration/suspension remain Checkpoint 5.

## Demonstrate the implemented workflow

1. Log in, open **Mes tableaux de bord**, create a titled dashboard. Add a blank
   widget or select an existing saved graphical analysis and explicitly add it.
2. Configure its immutable source/version, measures/chart and base filters;
   preview. Duplicate/edit/remove widgets, reorder by pointer or keyboard, resize
   or choose explicit dimensions. Mobile retains a single-column reading order.
3. Add a category/numeric/date/presence filter. Map each affected widget and
   column explicitly; choose the permitted categories/bounds, defaults and reader
   editability. Save changes; reload or log out/in to reopen the pinned sources.
   Changing a widget to another dataset removes its interactive mappings even
   when column names match; remap explicitly before saving. Same-dataset version
   changes retain settings for server validation.
4. Adjust view filters/reset. They update results without saving over defaults;
   allowed categories/bounds and base filters still apply. Check empty/error
   states and retry; obsolete results are removed.
5. Use **Gérer les destinataires** and an existing account's exact email. Dataset
   grants permit exploration/personal work on current/future versions. Analysis/
   dashboard grants permit saved results, without implicit dataset browsing.
6. For borrowed data, its original owner opens that dataset's sharing section,
   refreshes dependent configurations and reviews named versions/columns/measures/
   filter limits before explicitly approving that revision's onward diffusion.
   Changing the configuration requires renewed approval. Demonstrate revocation.
7. Demonstrate a denied presentation-only copy, then a permitted private copy
   after a distinct dataset grant. Copies inherit no sharing or onward approvals.

## Host checks

Build/lint/unit/offline checks do not control containers:

```powershell
npm --prefix services/platform run build
npm --prefix services/platform test
npm --prefix apps/web run build
npm --prefix apps/web run lint
npm --prefix apps/web test
.\.venv\Scripts\pharmacy-check.exe --group operations --group architecture
```

The **user starts** the dedicated test database:

```powershell
docker compose -f deploy/compose.platform-test.yaml up -d --wait
```

Run these sequentially against verified random databases in that dedicated cluster:

```powershell
npm --prefix services/platform run test:postgres
npm --prefix services/platform run test:datasets
npm --prefix services/platform run test:analytics
npm --prefix services/platform run test:dashboards
npm --prefix apps/web run test:accounts
npm --prefix apps/web run test:datasets
npm --prefix apps/web run test:analytics
npm --prefix apps/web run test:dashboards
```

Browser harnesses create temporary host servers; no test starts/stops a container
or selects an application database. Real-suite traces are disabled to exclude
session-bearing network data. Avoid parallel large imports/browser runs because
of the documented CPU-sensitive 60-second import deadline.

## Production images and isolated gate

After final source changes, the **user runs**:

Finish implementation and independent checks before requesting this gate. While
the user builds/runs it, stop work and wait for the result; do not change the
source under verification. Any necessary later fix requires a separate final run.

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/platform-cp4/full-stack.json
```

The verifier expects **18 named checks** plus all **18 assistant PostgreSQL tests**.
The initial user-run pass is retained separately. The final frontend source-switch
fix passes its targeted browser/build/lint checks and the final production gate.
For that final run, the **user ran** this frontend-only rebuild and isolated gate:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml build web
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/platform-cp4/full-stack-final.json
```

The final report records all 18 named checks and 18 assistant PostgreSQL tests
passing, zero skips, at **2026-10-23 21:49:13 UTC**, with isolated cleanup confirmed,
no inference and no application-volume changes. See the
[retained final report](../validation/platform-checkpoint-4-container.json).
No additional test run is required for the documentation-only status update.

New probes verify constrained dashboard queries, result-only permissions,
revocation, denied copies and persistence of filters/sources/grants through
whole-stack replacement. The real dashboard builder/collaboration browser suite
runs through production Nginx alongside retained assistant/dataset/analytics flows.
It uses a fresh random project/volume and removes only those resources. It performs
no hosted inference and leaves the normal application volume untouched.

The independent browser suites together create more fixture accounts than the
normal 10/IP/15-minute registration limit. Between suites, this user-invoked
verifier clears **only auth throttle counters in its generated disposable stack**.
It preserves sessions and application fixtures; the actual runtime limits and
normal application stack are unchanged. This fixture isolation does not claim
production rate-limit endurance; retained account tests verify throttling.

When finished, the **user** can stop the dedicated test service:

```powershell
docker compose -f deploy/compose.platform-test.yaml down
```

See [API and permission boundaries](../architecture/dashboards-sharing-api.md)
and [actual Checkpoint 4 evidence](../validation/platform-checkpoint-4.md).
Stop for review before Checkpoint 5.
