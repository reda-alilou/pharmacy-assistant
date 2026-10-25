# Installed functional review — Checkpoint 6

Status, 2026-10-25: **agreed installed review complete; all four focused
workflows passed by user reports/screenshots**. Phases A/B's listed checks also
passed. Retained automated isolated suites and installed infrastructure/public-
screen checks provide separate evidence. Engineering implementation/verification
is ready for checkpoint review; Git publication remains under the user's control.

Scope update, 2026-10-25: user accepted four focused installed workflows for
remaining acceptance: (1) v2 publication/saved-v1 pinning/comparison, (2) dashboard
filter/save/reopen, (3) sharing/read-only boundaries/revocation across two accounts,
and (4) dataset suspension/restoration. Other detailed cases below remain covered
by retained isolated automated evidence, rather than requiring every operation
to be repeated manually. Such cases are not marked manually passed. Preserve
all completed observations and investigate any new failure before acceptance.

Use only the small [synthetic review fixtures](../../apps/web/tests/fixtures/functional-review/README.md),
with a dataset title such as `TEST CP6 — functional review`. Never alter the
assistant catalogue, provider settings, quota or existing user resources. No
hosted inference is required. Keep all passwords local and hidden.

We run the following phases in order and record actual observations. Once a
phase is handed to the user, stop work/changes until the results return.
Unexecuted phases remain pending; preparing steps is not passing evidence.

| Phase | Review / expected outcome | Actual result |
| --- | --- | --- |
| A — CSV and exploration | Import v1, verify inferred/correctable types, full validation, private publication, 9 rows/8 columns, `001` stays text, zero present and one missing price. Search/filter/sort return expected results; reload retains dataset/version. Check malformed structure and forced numeric validation fail without publication. | Passed by user report: valid import/exploration and both rejected imports/cancellation, original remains 9 rows/one version with no extra dataset |
| B — Analysis and advanced features | Global price sum 410, mean 51.25, min 0/max 200; group A mean 15/B 87.5. Missingness 1/9, IQR 1.5 flags only `008`, chart recommendation can be applied/edited, multiple chart types show the same exact results/table. | Listed checks passed by user values/screenshots: aggregates, missingness/IQR, recommendation application/editing and all six chart types (KPI/bar/pie/histogram/scatter/temporal). Fourth advanced feature, version comparison, remains in phase C |
| C — Saved analyses and versions | Save/reopen/refresh the v1 analysis; append v2 to the same dataset. V1 stays unchanged and saved v1 mean remains 51.25. Explicit v2 mean 45; comparison key `presentation_id` reports 1 added/0 removed/2 changed/7 unchanged. | Passed: save/list/reopen/refresh/pinning confirmed by user; comparison screenshots show v1/v2 rows 9/10, means 51.25/45, sums 410/450, missing 1/0 and keyed differences 1/0/2/7 |
| D — Dashboard | Create KPI and grouped chart widgets, change order/width/height with accessible controls, map a group filter explicitly to both compatible sources. Group A shows four rows/mean 15. Explicitly save/reopen/refresh; filter state/configuration and results behave as specified. | Focused workflow passed by user report: two saved v1 widgets; mapped A gives mean 15/count 4. Reopen/refresh preserves mappings; B gives mean 87.5/count 5. Reader reset returns mean 51.25 and counts A=4/B=5. Detailed layout cases retain isolated coverage and are not claimed manually exercised |
| E — Sharing and authorization | Use separately signed-in synthetic analyst accounts. Unshared dataset is inaccessible by direct URL; a dataset grant permits reading and private derived analysis, not original edits. A result-only grant permits its result, not raw rows or arbitrary execution. Test revocation, copy requiring source access and explicit original-owner onward approval; verify forbidden changes fail at the backend. | Focused workflow passed by user report: separate reader's dashboard-only grant permits results and allowed filters, with read-only label/no edit button. Direct unshared dataset URL is denied with no rows; after owner revokes the dashboard grant, reader refresh is denied with no widget results. Other detailed cases retain isolated coverage |
| F — Administration | Existing admin reviews test-user/dataset metadata/activity, explicitly inspects test content with reason and confirms audit. Suspend only the test dataset: owner/shared analytics/widgets become unavailable; restore brings back only still-valid rights. Disable a test analyst and verify session loss; preserve their resources. Keep the existing admin's permissions unchanged; last-active-admin rejection/concurrency remains covered by the retained isolated tests. | Focused suspension/restoration passed by user report: owner widgets unavailable without previous results during suspension; restored owner sees KPI 51.25/counts A=4/B=5; revoked reader remains denied. Detailed inspection/activity/account/last-admin cases retain isolated coverage and are not claimed manually repeated |
| G — Lifecycle/recovery and cleanup | Archive/restore the test dataset, verify dependency-blocked deletion, remove only test grants/dashboards/analyses and then explicitly delete the test dataset if desired. Test failures keep drafts/clear obsolete results. Leave existing users/data alone; record remaining labelled review accounts/resources. | Detailed lifecycle cases retain isolated coverage under the accepted focused scope. No manual archive/delete pass claimed. Cleanup optional and not performed: TEST CP6 dataset (v1/v2), saved analysis/dashboard and ordinary reader account retained; dashboard grant revoked, dataset unshared and restored |

For role/sharing phases, create ordinary analyst accounts through registration,
for example `cp6-owner@example.test` and `cp6-reader@example.test`, named clearly
`TEST CP6 owner/reader`. Use separate browser profiles/contexts; ordinary private
windows in one browser may share a cookie jar. Keep the existing admin in its own
session. Do not provision another admin or change real user permissions.

Phase A can begin with the current administrator as dataset owner, or the review
owner account if already created. Record which owner holds the dataset and retain
its URL for later phases. Owner/recipient boundaries are checked in phase E;
do not mistake admin navigation alone for that verification.

For the focused remaining sharing flow, the existing admin may remain the
original test-data/dashboard owner, with one synthetic reader analyst in a
separate browser context. Additional borrowed-source/copy/onward and account-
disable/last-admin/archive/delete cases retain their isolated automated coverage;
no extra administrator or real-account permission change is needed.

Start with v1 import and exploration; report the observations before continuing.
If anything differs, capture the visible error/expected versus actual result,
preserve the fixture/draft and fix/retest the affected path. Do not share session
tokens, passwords or private environment files. Results will be recorded here
and in the CP6 evidence, separately from previous isolated automated passes.

## Observations

- 2026-10-24: user reports the `cp6-v1.csv` import succeeded. This records the
  successful import only, without assuming every suggested value check passed.
- User confirms all exploration checks worked: unfiltered original values, search `Synthetic H`
  (one row `008`), `group = A` (four rows), price `> 20` (five rows `004`–`008`),
  missing price (one row `009`), descending price (200 first, missing last), and
  reload after clearing filters (original nine rows/version still available).
  Clear search/filters between checks; exploration query persistence across a
  reload is not required here. Invalid-file recovery and phases B–G remain pending.
- User confirms both rejection tests behaved exactly as expected: malformed
  structure blocked publication; forced decimal price rejected the invalid
  number; staging cancelled, original v1 remains nine rows/one version and no
  extra dataset created. Phase A is passed by user report.
- User reports the exact global v1 aggregate values: mean
  `51.250000000000000000000000`, sum `410`, minimum `0`, maximum `200`.
- User screenshot confirms v1/no filters/no search: 9 rows, two groups.
  B has 5 rows, 4 present prices, 1 missing and mean 87.5; A has 4 rows,
  4 present prices, 0 missing and mean 15. Global/grouped aggregation checks pass.
- User screenshot confirms horizontal bar chart B=87.50/A=15.00 and the unchanged
  exact aggregate table below. Graphical labels round; table decimals remain exact.
- Missingness screenshot confirms 9 rows, 8 present/1 missing price (11.11%) and
  one affected source line 10 (record `009`), original empty text retained.
- IQR screenshot confirms 8 present/1 excluded missing, Q1=17.50, Q3=52.50,
  IQR=35.00, fences -35.000/105.000 and exactly one flagged price 200 at source
  line 9 (record `008`). No source value correction/deletion is reported.
- Recommendation screenshot for `group` + `ppv_price_mad` shows numeric
  distribution/KPI and categorical count/share/mean options, including
  `Mesure par catégorie`. User confirms applying that option produces grouped
  mean bars B=87.5/A=15; editing its operation to sum produces B=350/A=60.
  Recommendation generation, application and editability pass.
- The assistant incorrectly instructed a sum-based pie. Current documented chart
  rules support additive row/present/missing counts only. User screenshots show
  the expected incompatible-measure rejection and replacement of the old result
  with `Résultat à calculer`; this is a validation/recovery pass, not a sum-pie
  implementation defect. No application code change is needed for this instruction.
- Corrected pie screenshot confirms two slices B=5/A=4, nine contributions and
  table shares 55.56%/44.44%, with no filters/search. Pie rendering passes.
- Histogram screenshot confirms four bins [0,50), [50,100), [100,150), [150,200]
  with counts 5/2/0/1; eight present values and one excluded missing. Both drawing
  and exact interval table agree, including zero and the inclusive maximum.
- User confirms scatter check passed: X=quantity, Y=price, eight plotted points,
  one missing pair excluded; quantity 8 corresponds to price 200.
- User confirms the temporal mean chart grouped by observation month matches
  January 2026=15/February 2026=87.5. After removing the group and selecting KPI,
  user confirms the global mean card shows 51.25. Phase B's listed checks pass;
  explicit comparison (the fourth advanced feature) remains in phase C.
- User confirms saving `TEST CP6 — prix moyen v1` and finding it in Mes analyses.
  Reopening and refreshing retains version 1, mean operation, price column and
  KPI visualization; recalculation still shows 51.25. Save/reopen/reload pass.
- 2026-10-25: user confirms both requested outcomes: v2 is published on the same
  test dataset with 10 rows; opening the saved analysis without changing its
  source/version still selects v1 and recalculates 51.25. Publication/pinning pass.
- 2026-10-25 comparison screenshots confirm explicit left v1/right v2, no
  filters/search, row counts 9/10, present prices 8/10, missing 1/0, sums 410/450
  and means 51.25/45. Unique-key results: 1 added/0 removed/2 changed/7 unchanged;
  `008` price 200→80, `009` missing→70, `010` added with 90. Leading-zero keys
  remain text. Version comparison and focused workflow 1 pass; all four advanced
  features have now been manually exercised. Existing saved v1 KPI preserved.
- User confirms creating/saving `TEST CP6 — dashboard` from the saved v1 mean
  analysis: KPI is 51.25. After adding a second `Lignes par groupe` widget on v1
  and saving, user confirms both widgets show 51.25 and B=5/A=4 respectively.
- User confirms the saved category filter `Groupe`, allowed choices A/B and
  explicit `group` mappings to both widgets work: selecting A shows mean KPI 15
  and only group A with four rows in the chart. Recorded as a user-reported pass.
- User confirms reopening/refreshing the saved dashboard preserves its filter
  mappings: choosing B gives KPI 87.5 and only B=5; resetting reader filters
  restores KPI 51.25 and A=4/B=5. Focused dashboard workflow passes by user
  report. Reader selections are temporary; configuration/mappings persist.
- User confirms the separate reader account's dashboard-only access works:
  unfiltered KPI 51.25/counts A=4/B=5, reader filter A gives KPI 15/count 4,
  read-only label visible and dashboard edit button absent. Dataset left
  unshared. These are user-reported view/filter/UI-boundary checks; direct
  dataset denial and revocation are not yet claimed passed.
- User confirms both final sharing checks: reader's direct unshared dataset URL
  is denied without rows; owner revokes the dashboard grant and reader refresh
  is denied without widget results. Focused sharing/revocation workflow passes
  by user report. The synthetic reader account remains; its dashboard grant is
  revoked and no dataset grant was created.
- User confirms the final suspension/restoration outcomes: while the synthetic
  test dataset is suspended, both owner widgets are unavailable without previous
  results; after restoration, owner results return to KPI 51.25/counts A=4/B=5.
  The reader remains denied after refresh because its grant stays revoked.
  Focused workflow 4 passes by user report; all four agreed workflows are done.
- Review resources deliberately retained: restored/unshared TEST CP6 dataset
  with versions 1/2, saved v1 analysis, dashboard and ordinary synthetic reader
  account. Dashboard grant revoked. No cleanup, real-account permission change,
  assistant source change or hosted inference was performed by the agent.
  Minor UI tweaks remain deferred by the user; no required review test remains.
