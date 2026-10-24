# Checkpoint 5 — administration and integration

The user controls every container lifecycle, including dedicated test services
and disposable verification stacks. Keep the branch, normal application volume,
existing credentials and administrator. Do not rerun environment initialization,
provision an existing administrator again or re-import sources as an upgrade.
The user chose to upgrade the normal installation after Checkpoint 5, before
delivery/manual review. Implementation verification uses isolated fixtures.

## Independent checks

```powershell
npm --prefix services/platform run build
npm --prefix services/platform test
npm --prefix apps/web run build
npm --prefix apps/web run lint
npm --prefix apps/web test -- --workers=1
.\.venv\Scripts\pharmacy-check.exe --group operations --group architecture
```

Sequential browser workers avoid contention with other local verification jobs;
do not run large database imports or browser suites concurrently on this machine.

## Dedicated database checks

When implementation/independent checks are ready, ask the **user** to start the
existing dedicated service, then stop and wait for their result:

```powershell
docker compose -f deploy/compose.platform-test.yaml up -d --wait
```

It uses tmpfs and localhost:55433, no application credentials or application volume.
The retained stopped container may be reused. Tests verify the cluster identity
before creating/dropping randomly named databases. No test starts/stops a container.
After the user confirms readiness, run sequentially:

```powershell
npm --prefix services/platform run test:postgres
npm --prefix services/platform run test:datasets
npm --prefix services/platform run test:analytics
npm --prefix services/platform run test:dashboards
npm --prefix services/platform run test:administration
npm --prefix apps/web run test:accounts
npm --prefix apps/web run test:datasets
npm --prefix apps/web run test:analytics
npm --prefix apps/web run test:dashboards
npm --prefix apps/web run test:administration
```

The new suite covers populated CP4 migration, constrained runtime grants, exact
metadata/overview boundaries, audited inspection including audit-write failure,
suspension/revocation/restoration, borrowed-source onward approval, disabled-owner
policy, concurrent last-admin changes, real backup/restore, HTTP roles/CSRF and
pagination/filtering. Real browser workflows cover account confirmations/session
invalidation, last-admin rejection, inspection consent, pagination and recovery,
suspended owner/shared results, restoration and activity/desktop/mobile access.
Actual results, including any failures, belong in the evidence report.

## Production image gate

Only after source changes and host verification are complete, ask the **user** to
run the following, then stop work until they return the result. Do not edit the
source under verification.

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml --profile tools build
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/platform-cp5/full-stack.json
```

The current verifier expects **20 named checks and all 18 assistant PostgreSQL
tests**. New API/browser checks use one explicitly provisioned synthetic admin
only in the generated disposable project; normal configuration/admin credentials
are untouched. It checks permission/session boundaries, last-admin rejection,
logged content inspection, suspension/restoration, the admin UI and prior
assistant/dataset/analytics/dashboard/collaboration persistence/regressions.
Between independent browser suites it clears only that disposable project's test
auth throttle counters; normal limits/sessions are unchanged. No hosted inference
is performed. Require `passed:true` and `isolated_resources_removed:true`.

The final user-run gate passed all **20 named checks and 18 assistant PostgreSQL
tests**, zero skips, at **2026-10-24 07:06:35 UTC**. It confirms cleanup, no inference
and no application-volume changes. The exact report is retained as
[container evidence](../validation/platform-checkpoint-5-container.json).
No additional run is required for the documentation-only status update after
that result. Checkpoint 5 is ready for review; normal-volume upgrade remains a
separate user-run step.

## Upgrade the normal installation after acceptance

If platform accounts have never been installed, follow the
[one-time platform setup](platform-accounts.md) first. Otherwise reuse the existing
`.runtime/platform.env` and administrator. The explicit migration applies all five
owned revisions; no migration or catalogue import runs at service startup.
When ready, the **user runs**, in order, from the repository root:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build platform platform-setup web database-setup
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait postgres
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Open Administration with an explicitly provisioned admin. Demonstrate overview,
searchable users, reviewed role/status changes, last-admin rejection, dataset
metadata/version/import supervision, explicitly confirmed inspection, suspension
and restoration, affected widgets and filterable activity. The assistant remains
visitor-accessible, with independent temporary conversation state.

Keep existing backup procedures; restored permission/suspension/activity fields
and sharing dependencies must remain functional. Sessions/throttles/upload staging
and temporary patient conversations remain excluded. No automatic audit purge is
added. The user may leave the dedicated test service stopped when finished:

```powershell
docker compose -f deploy/compose.platform-test.yaml stop
```

See [API/lifecycle contract](../architecture/administration-api.md) and
[actual evidence](../validation/platform-checkpoint-5.md). Stop for review before
Checkpoint 6.
