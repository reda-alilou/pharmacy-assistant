# Pharmaceutical platform — Checkpoint 3 evidence

Date: **2026-10-23**. Status: **implemented and verified in final host/browser and
isolated production-image checks; awaiting user review**. The user authorized Checkpoint 3 after
the passing rebuilt Checkpoint 2 results. Checkpoints 4–6 have not started.
Historical Checkpoint 1/2 and R7 reports remain unchanged.

## Scope implemented

Parameterized full-version aggregations, pharmaceutical templates, editable
analysis charts and private saved version-pinned definitions. Four advanced
features have visible results/rules: grouped missingness and affected-row
inspection; grouped strict IQR flags; recommendations that create executable
editable chart settings; schema/statistic and optional exact-key row comparison.
Saved analyses maintain real dataset dependencies and block accidental deletion.
New owned migration/grants and backup coverage extend the preserved foundation.
No dashboard builder, sharing/copy grants or administrative workflow is implied.

## Checks actually run

| Gate | Observed result |
| --- | --- |
| Branch/tree | `feat/pharmaceutical-analytics`; existing planning and Checkpoint 1/2 changes retained; no branch/commit/push |
| Platform build/unit tests | Build passed; all 8 retained unit/security/CSV tests passed |
| Analytics real PostgreSQL | 11 scenario groups plus parent: 12 results passed, zero skips |
| Retained dataset PostgreSQL | 9 scenario groups plus parent: 10 results passed, zero skips, with migration count extended to 3 |
| Retained account PostgreSQL | 7 scenario groups plus parent: 8 results passed, zero skips, with migration count extended to 3 |
| Real analytics browser | Final 2 workflows passed in 40.5 s, including all four features, saved version pinning, ownership, every chart type, held-save locking, desktop/mobile axe and no overflow |
| Frontend build | Final build passed; analytics loads as a separate chunk |
| Frontend lint | Passed with two preexisting button/badge fast-refresh warnings; no new warnings |
| Focused Python operations/architecture | Final recheck: 11 operations and 12 architecture tests passed (23 total), including the new mocked verifier reporting/cleanup regression |
| Offline assistant/account browser | 28 passed, 1 deployment-only skip; includes retained assistant regressions and protected analytics deep-link recovery |
| Real account/dataset browser regressions | Final account workflow passed in 18 s; both dataset workflows passed in 17.8 s |
| Production images/Nginx/whole isolated stack | User built all images successfully. After the helper-only fix, the final rerun passed all 16 named checks, including the actual analytics browser workflow through Nginx, and all 18 assistant PostgreSQL tests with zero skips; isolated cleanup confirmed |
| Normal-volume upgrade/manual acceptance | Not established by host or disposable-stack checks |

No hosted inference, scraping, credential regeneration, application-volume writes,
container lifecycle or publication by the agent. The user started the dedicated
test PostgreSQL service. All real host tests create/drop only verified random
test databases and temporary host processes, without selecting application URLs.

## Correctness and edge cases

Known-input tests cover sums/means/median/quartiles and both deviations, present/
missing denominators, full-filter counts, rankings/omissions and UTC month groups.
Numeric source values larger than JS's exact integer range retain low fractional
digits, including mean `.015` between large `.01` and `.02` observations. Returned
data stays decimal strings; coordinates are normalized independently.

Advanced tests cover all-missing/zero-row/constant selections, zero IQR, strict
fence equality, too-small groups, null group versus literal text `null`, full
affected/flagged counts and pagination. Recommended definitions execute through
the same engine; same-month dates do not create a suggested time series.
Pharmaceutical templates operate only on available fields and respect filters.

Comparison checks schema differences, missingness and numeric statistics, explicit
mapping, complete unique keys, duplicates/missing-key refusal, exact added/
removed/changed/unchanged counts and both-source authorization. Text/numeric keys
are not silently coerced. Saved analyses preserve algorithm/settings and original
versions; revisions prevent lost updates; disabled accounts cannot save. Real
FK/dependency registrations block source deletion. SQL migration from populated
Checkpoint 2 preserves source rows and owned revisions. Maintained real dump/
restore preserves saved definitions and their source/dependency relationships,
with sessions excluded. HTTP checks exercise CSRF, source tampering and ownership.

## Local performance measurements

Last completed analytics benchmark: **2026-10-23 19:58:32 UTC**;
[retained measurements](platform-checkpoint-3-benchmarks.json).

| Fixture | Rows | Mean/median/quartiles/deviation | IQR plus missingness | IQR + ranking across 25,000 unique groups |
| --- | ---: | ---: | ---: | ---: |
| Complete pharmaceutical source | 9,936 | 32 ms | 60 ms | — |
| Larger synthetic source | 25,000 | 62 ms | 123 ms | 335 ms |

Catalogue missing-price count remains **1,126**. Source data/identities/prices/
nulls/provenance are unchanged. Measurements use local PostgreSQL and exclude
upload/import time. They are not concurrency/production SLAs. Existing supported
import bounds and the documented heavy-load 60-second upload/publication timeout
remain; calculations additionally retain 10-second SQL statement limits.

## Development failures and corrections

Tests found missing explicit text types in parameterized JSON labels and an
ungrouped SQL projection; both were corrected. IQR threshold arrays were initially
inlined repeatedly, causing a statement timeout on larger fixtures. Materialized
scalar thresholds plus hashable null-safe group joins resolved it; the catalogue,
25,000-row and 25,000-group scenarios pass.

A precision probe showed unscaled PostgreSQL averages rounding at the input scale
for very large close decimals. Numeric(80,24) inputs now preserve the `.015` mean,
with a dedicated regression. Previously published immutable profiles are retained;
current analyses recompute from unchanged typed values. Newly imported profiles
use the improved scale too.

Browser testing exposed stale source-picker options after another import; explicit
refresh now reloads choices while preserving selected versions. Analysis type
controls wait for selected source metadata. Changing datasets resets configuration
and filters; changing an immutable version retains settings for explicit server
revalidation. Measure labels reset on operation change to prevent a mean being
labelled as a row count. Protected analytics deep links retain source/version query
parameters through login. Pending operations lock all editable analysis fields.

The first user-run production verifier reached the end of its analytics API probes,
then failed with `TypeError`: a feature response variable had overwritten the
report dictionary. This also prevented structured failure reporting. The response
variable is now distinct. A mocked orchestration regression reaches the analytics
mark, injects a later failure and verifies the six recorded checks, failure report,
cleanup invocation and temporary-file removal without running containers. The
focused 23-test suite passes. Read-only Docker inspection confirmed that the failed
real run left no containers, volumes or networks for its exact isolated project.
This helper-only fix requires no application-image rebuild. The failed attempt
does not count as a passing production gate.
The subsequent user-run rerun passed the complete gate; no additional image
rebuild or runtime change was required.

## Evidence and remaining acceptance

Ignored logs: `artifacts/platform-cp3-backend.log`, `platform-cp3-browser.log`,
`platform-cp3-datasets.log`, `platform-cp3-accounts.log`,
`platform-cp3-offline-browser.log`, `platform-cp3-account-browser.log`,
`platform-cp3-dataset-browser.log` and `platform-cp3-operations.log`.
The latter contains the earlier 22-test operations/architecture run; the subsequent
23-test run with the verifier regression passed in the tool transcript.
Benchmarks: `artifacts/platform-cp3/analytics-benchmarks.json`. Screenshots and
browser JSON are under `artifacts/platform-cp3/browser/`.

The [retained final container report](platform-checkpoint-3-container.json), inspected
against `artifacts/platform-cp3/full-stack.json`, records **16/16 named checks** and
**18/18 retained assistant PostgreSQL tests, zero skips**, with no inference,
no application-volume modification and complete isolated cleanup. The report's
UTC timestamp is `2026-10-23T20:13:54.140709+00:00`. It verifies analytics/saved
dependencies and original source persistence after whole-stack replacement,
and runs the actual assistant/dataset/analytics browser suites through production
Nginx. Its legacy `pharmacy-checkpoint4-test-…` project prefix refers to the older
architecture verification phase; it does not mean analytics Checkpoint 4 started.
Commands are in [analytics operations](../operations/analytics.md).

Normal-volume upgrade, user layout/workflow review and physical device acceptance
remain distinct from automated evidence. Stop for review before Checkpoint 4.
