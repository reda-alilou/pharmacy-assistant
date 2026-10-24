# Pharmaceutical platform — Checkpoint 5 evidence

Date: **2026-10-24**. Status: **implemented and verified in host/database/browser
and isolated production-image checks; ready for user review**.

The user authorized Checkpoint 5 after reviewing and pushing Checkpoint 4.
Branch `feat/pharmaceutical-analytics` was clean and synchronized before edits;
the user's `888159d` Checkpoint 4 commit is preserved. No applicable AGENTS.md was
found in the repository or ancestors. The user retained the stopped dedicated
test database container. No container lifecycle has been run by the agent.
Normal-volume upgrade is deferred until after Checkpoint 5 acceptance; no
credential regeneration, hosted inference, scraping or Git publication occurs.

## Implemented work

Migration `0005_administration.sql`, four admin UI/API sections, permission
revisions/session invalidation/last-admin safeguards, explicit audit-required
content inspection, reasoned suspension/restoration and activity filters.
Suspension checks extend ordinary dataset use, imports/mutations, direct/saved
analyses, templates/comparisons, widgets/copies, grants and onward approval while
preserving configurations, source facts/history and revocation paths. Activity
retention is indefinite without automatic purge; no permanent account deletion.
The existing assistant and private service/schema boundaries are preserved.

## Checks actually run

| Check | Observed result |
| --- | --- |
| Backend build | Final source build passed, including the year-zero validation fix |
| Node unit/security/CSV suite | 8 passed, zero skips |
| Frontend TypeScript/production build | Passed; admin page lazy-loaded (24.24 kB); main bundle 424.79 kB; assistant separate |
| Frontend lint | Passed with only two preexisting button/badge fast-refresh warnings |
| Operations/architecture | 11 + 12 = 23 tests passed, including the mocked admin API verifier path and controlled later-failure cleanup/reporting |
| Administration PostgreSQL | 11 scenario groups + parent = 12 results passed, zero skips (2.7 s final run): populated CP4 migration, permissions/audit/content boundaries, suspension/revocation/restoration/onward checks, concurrent last-admin changes, HTTP CSRF/strict validation and real maintained backup/restore |
| Restored lifecycle | Full users/datasets/activity/source rows/resources/grants compared; restored suspension enforced and explicitly resumed; source database remained suspended; sessions/throttles/staging absent |
| Retained PostgreSQL | Accounts 8, datasets 10, analytics 12 and dashboards/sharing 14 results passed, zero skips (11.4 / 15.5 / 5.8 / 3.0 s) |
| Administration real browser | Both workflows passed in 24.7 s: account confirmation/session invalidation/self-change/last-admin guard, explicit logged inspection/decline/pagination/failure recovery, suspended dataset and widget UI, owner/shared APIs, restore and activity filters; desktop/mobile axe and overflow checks passed |
| Retained real browser | Accounts 1, datasets 2, analytics 2 and dashboards 3 workflows passed (9.0 / 15.6 / 46.2 / 60 s) |
| Offline browser regressions | Initial concurrent run: 26 passed, 2 assistant refresh/restoration assertions failed, 1 deployment-only skip. Sequential full rerun: all 28 passed, 1 deployment-only skip (1.6 min); no assistant source change needed |
| Production images/Nginx | Final user-run gate passed all 20 named checks and all 18 assistant PostgreSQL tests, zero skips; isolated cleanup confirmed, no inference or application-volume changes |

The first frontend build in the process sandbox could not spawn Vite helpers/load
the native compiler; the same source built successfully with the authorized host
process permissions. No dependencies were changed to bypass that restriction.
Earlier checkpoint reports remain baseline evidence; this report records the new
CP5 checks and its own retained passing production run.

## Findings and corrections

- The initial administration database run passed its behavior/restore scenarios
  but the activity assertion expected one suspension after two deliberately
  separate suspension scenarios. The expectation now counts both; the complete
  rerun passes. No production behavior was changed for this fixture correction.
- The retained analytics upgrade test ran the current importer against its
  historical CP2 schema, which lacks the new version-created activity action.
  That fixture now seeds the actual old table representation directly, including
  original/typed cells and old profiles, before upgrading. Complete immutable
  versions/columns/rows are compared before/after. Production startup still
  requires current explicit migrations; no backward-compatibility shortcut or
  frozen-migration edit was introduced. The retained suite then passed all 12.
- Initial browser failures were test synchronization/locator assumptions: a
  permission POST was not awaited before checking another session; an exact
  wrapping-label selector did not match the activity select; and a login helper
  rejected the correct remembered admin destination after self-role changes.
  Tests now await the response, use the select's accessible role/name and accept
  that documented protected return route. The retained real account test now
  supplies the full service and checks actual admin overview instead of the old
  placeholder. Complete admin/retained browser reruns pass.
- Review found ISO year zero accepted by the date validator but unsupported by
  PostgreSQL. Admin activity ranges now reject it with 422; both contract and real
  HTTP regressions pass. Invalid days and reversed ranges remain rejected.

Desktop/mobile activity and suspended-content inspection screenshots were viewed
after the passing run. Their layout is readable, the mobile page does not
overflow, and audit events expose reasons/IDs without inspected cell contents.

Ignored logs: `artifacts/platform-cp5-operations.log`,
`platform-cp5-offline-browser.log`, `platform-cp5-offline-browser-final.log`,
`platform-cp5-unit.log`, `platform-cp5-administration{,-initial}.log`,
`platform-cp5-{postgres,datasets,analytics,dashboards}.log`,
`platform-cp5-analytics-initial.log`,
`platform-cp5-administration-browser{,-initial,-second}.log` and
`platform-cp5-{accounts,datasets,analytics,dashboards}-browser.log`.
Real admin JSON/screenshots are under `artifacts/platform-cp5/browser/`.

See [API and lifecycle](../architecture/administration-api.md),
[exact user-run operations](../operations/administration.md). Finish independent
work before requesting user-run service commands, then stop until results arrive.
Stop for user review before Checkpoint 6.

Before the dedicated-database handoff, `git diff --check` passed; the previous
four platform migrations, Python service sources/migrations, authoritative source
inputs and CP4 retained validation report were verified unchanged. The branch
remains `feat/pharmaceutical-analytics`. Only the new fifth migration changes
database structure. The verifier AST has 20 distinct named marks. No private
environment or expanded secret-bearing configuration was printed.
The user subsequently started that dedicated test database and all real host
checks above ran against randomly named databases in it. The normal installation
has not been upgraded.

## Final user-run production gate

At **2026-10-24 07:06:35 UTC**, the user-run verifier passed all **20 named checks**
and **18 assistant PostgreSQL tests**, zero skips. This includes the real admin
account/inspection/suspension/activity workflow through production Nginx, explicit
migrations/grants, permission/session/last-admin boundaries, persisted resources,
retained assistant/dataset/analytics/dashboard workflows and backup/concurrency.
The report confirms complete isolated cleanup, no hosted inference and no
application-volume changes.

The exact public report is retained as
[container evidence](platform-checkpoint-5-container.json), copied byte-for-byte
from `artifacts/platform-cp5/full-stack.json`. Validation checked that its 20 true
names exactly match the verifier's expected named checks, plus the PostgreSQL
counts, timestamp and cleanup/no-inference/no-normal-volume-change flags.
Application source was unchanged after the verification handoff. Only evidence/
documentation status was updated after receiving the result; no additional test
run is needed for that documentation-only update.

No CP5 automated verification gate is outstanding. Normal-volume upgrade and
manual UI/device acceptance remain separate user actions. Checkpoint 6 has not
started; stop for user review before continuing.
