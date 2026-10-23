# Pharmaceutical platform — Checkpoint 4 evidence

Date: **2026-10-23**. Status: **implemented and verified in host/browser and final production-image checks; awaiting user review**.
The user authorized continuation after Checkpoint 3's final passing gate. Work
continues on `feat/pharmaceutical-analytics`; the working tree was clean before
editing. No applicable AGENTS.md was found in the repository or its ancestors.
Checkpoints 5–6 have not started.

## Current implementation

Owned migration `0004_dashboards_sharing.sql` adds revisioned dashboard
configurations, restrictive source/version references, separate dataset/analysis/
dashboard grants, and original-owner authorizations tied to a saved revision.
Frozen earlier migrations and source cells remain unchanged. Runtime permissions
remain confined to `platform`.

Dashboard widgets reuse the existing analytics engine. Saved query definitions
and explicit filter mappings determine reader calculations; a presentation grant
does not authorize arbitrary columns, source changes or raw dataset browsing.
Category and numeric/date boundaries stay applied when filters reset. Copies
require actual source permissions and inherit no sharing or onward approval.
Dataset recipients can explore and create their own saved configurations, while
original metadata/version/deletion operations remain owner-only.

The React builder/navigation/sharing UI passes its real browser workflows. Desktop grid movement/resizing has pointer and keyboard controls;
mobile uses DOM order in one column. Explicit saving, revisions, unload/route
warnings, held-save editing locks and stale-result removal are checked, including a follow-up warning before session invalidation on logout.

## Checks actually run so far

| Check | Observed result |
| --- | --- |
| Backend build | Passed after new contracts and permissions |
| Dashboard/sharing PostgreSQL | Final 13 scenario groups + parent = 14 test results passed, zero skips, including UTC microsecond date boundaries, concurrent save/approval and bounded recipient/owner-review pagination |
| Maintained real backup/restore | Passed inside the new PostgreSQL suite: source values, configurations, grants, authorizations and dependencies retained; sessions/throttles/staging absent; restored authorization revocation enforced |
| Frontend build | Passed after the final source-switch fix; main bundle 425.38 kB and assistant separately loaded |
| Frontend lint | Passed after correcting the new drag-handle ref read; only two preexisting button/badge fast-refresh warnings remain |
| Real browser | All three workflows passed in 43.5 s: builder pointer/keyboard layout, all filter types, donut/histogram, saved login/reopen, held-response/error recovery, desktop/mobile axe, three-account approval/revocation and shared-analysis copies. Follow-up dirty-logout guard passed its full builder workflow in 28.5 s; final source-switch regression passed the builder workflow in 15.4 s |
| Retained PostgreSQL | Accounts 8, dataset lifecycle 10, analytics 12 results passed, zero skips; current migration count 4 |
| Retained browser | Accounts 1, dataset lifecycle 2, analytics 2 workflows passed (10.4 / 14.8 / 16.0 s) |
| Unit/offline browser | 8 Node unit tests passed; 28 offline browser checks passed, 1 deployment-only skip |
| Focused operations/architecture | 23 Python tests passed, including mocked verifier probes and reporting/cleanup |
| Full production images/Nginx stack | Final user-run gate passed all 18 named checks and 18 assistant PostgreSQL tests, zero skips, including the source-switch regression; cleanup confirmed, no inference or application-volume changes |

The user started the dedicated test PostgreSQL service. The agent has not started
or stopped containers, changed the normal application volume, regenerated private
credentials, run hosted inference or published Git changes.

## Development findings

The first browser probes used two incorrect expected French labels. They were
corrected to the actual interface text. A later layout assertion depended on CSS
serialization order; it now checks computed row/column spans instead. Pointer
reordering and keyboard movement/resizing reached the expected layout before
that assertion. The subsequent full builder gate passed; failed attempts are not counted as passes.

Widget results initially lacked configured column labels. The backend now returns
metadata only for referenced visual/filter columns, avoiding disclosure of the
rest of a dataset's schema to presentation-only readers.

The axe scan found repeated landmark names across widgets; all result/table/bar
regions now use a widget-specific scope. Final desktop/mobile axe and overflow
checks pass; screenshots were also viewed. A source review found logout could
invalidate a session before an editor's navigation warning. A cancelable
pre-logout guard now warns before any logout request; the regression proves a
declined warning preserves both the draft and session. The first added test had
an asynchronous native-dialog listener race; explicit dialog synchronization
corrected the test, and the full builder workflow passed. The visitor-introduction
regression was updated to describe implemented dashboards/sharing and future
administration; the subsequent full offline suite passed.

After requesting the initial image build, source review found that changing a
widget to an unrelated dataset could retain interactive mappings when column
identifiers matched. The editor now removes that widget's mappings on dataset
change, requiring explicit remapping; same-dataset version changes retain
settings for server validation. The targeted regression imports another dataset
with identical column names, confirms the changed widget loses its mappings while
the other widget retains its own, and passes the full builder workflow. Final
frontend compilation/lint passed after this fix. The initial production report
does not cover this later frontend change; the final user-run gate below does.

Original-owner review uses readable source/version/column/measure/filter settings,
not raw configuration JSON or other owners' sources. Recipient and dependent-review
lists have bounded pagination. All earlier SQL/Alembic revisions are untouched.

## Evidence locations and remaining verification

Ignored logs are `artifacts/platform-cp4-{analytics,datasets,accounts,dashboards}.log`,
`platform-cp4-browser.log`, `platform-cp4-{analytics,dataset,account}-browser.log`,
`platform-cp4-logout-guard.log`, `platform-cp4-source-switch.log`, `platform-cp4-offline-browser.log` and
`platform-cp4-operations.log`. The last source builds/lint passed in the tool
transcript. Browser JSON and desktop/mobile/filter/sharing screenshots are under
`artifacts/platform-cp4/browser/`.

The extended production verifier has 18 distinct named checks and all 18 retained
assistant PostgreSQL tests. Its mocked early dashboard/API path records seven
checks, then injects a later failure and verifies structured reporting, cleanup
invocation and temporary-file removal without Docker. Production fixture suites
clear only their generated disposable project's auth throttle counters between
suites, keeping real limits/sessions intact. The initial user-run image/Nginx gate
passed on **2026-10-23 at 21:37:45 UTC**: 18 named checks and 18 assistant PostgreSQL
tests, zero skips, complete isolated cleanup, no inference and no application-volume
modification. Its exact report is retained as
[initial container evidence](platform-checkpoint-4-initial-container.json).
After the frontend fix, the user reran the isolated gate. The final report at
**2026-10-23 21:49:13 UTC** records **18 named checks and 18 assistant PostgreSQL
tests passing**, zero skips, including the source-switch regression in the real
dashboard browser workflow through production Nginx. It confirms complete isolated
cleanup, no hosted inference and no application-volume modification. The exact
public report is retained as [final container evidence](platform-checkpoint-4-container.json),
copied from `artifacts/platform-cp4/full-stack-final.json` and checked for all
18 true named checks, PostgreSQL counts and safety flags. Application source was
unchanged after the verification handoff; only documentation/evidence was updated
after receiving the result. No further CP4 verification gate is outstanding.
Exact commands are in
[dashboard/collaboration operations](../operations/dashboards-sharing.md). Normal-volume upgrade and manual UI/device review
remain distinct. Stop for user review before Checkpoint 5.
