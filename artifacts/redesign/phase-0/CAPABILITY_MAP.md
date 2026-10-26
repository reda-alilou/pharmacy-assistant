# Existing capability → proposed UI map

Scope: the current `apps/web/` route tree, frontend feature modules, technical coverage map and API contracts. Nothing below is removed because it is absent from a representative screenshot. All UI changes remain proposals.

**Coverage:** C = representative composition in all three alternatives; S = specified in the blueprint/system, not a complete interactive prototype. Local prototype simulations do not verify real endpoints. A/B/C use different layouts for the same capabilities; the chosen direction must retain all rows during implementation.

## Accounts and navigation

| Existing capability / source owner | Proposed location and behavior | Coverage / later phase |
| --- | --- | --- |
| Introduction and visitor assistant (`accounts/pages`, `App`) | Honest two-path introduction; assistant remains public and independent. | S /5–6 |
| Analyst registration, login, throttling/CSRF/native validation (`accounts`) | Labeled forms, contextual error summary; no auth-contract changes or persistent password input. | S /5 |
| Protected/admin route guards and login return | Keep existing routes/query context; navigation visibility never replaces backend authorization. | S /5 |
| Own displayed-name/profile editing | Simple profile editor, warning-only exits, explicit save. | S /1,5 |
| Password change and session invalidation | Existing current/new password flow, consequence confirmation, no password storage. | S /1,5 |
| Logout and session refresh/expiry | Guard ordinary dirty logout; forced expiry follows security; no recovery promise or cross-account cache. | S /1,5 |
| Dataset/analysis/dashboard/profile/admin destinations | A horizontal navigation; B primary rail; C horizontal document tabs. Labeled mobile alternative and active location. | C representative nav; full routing S /5 |
| Unknown route, history, refresh, title/focus/skip links | Existing paths remain; deliberate new-content focus and titles, native browser semantics. | S /5 |

## Dataset/import lifecycle and exploration

| Existing capability / source owner | Proposed location and behavior | Coverage / later phase |
| --- | --- | --- |
| Private own/shared lists, pagination and archives (`datasets/pages`) | Resource list with access/state and clear Import; archive filter remains. | S /5 |
| CSV upload, explicit new dataset vs append version (`datasets/import`) | File stage identifies target; no publication on upload/Next. | S /3 |
| File/row/column/cell limits, UTF-8/Windows-1252 | File-stage guidance and corrective errors, unchanged bounds. | S /3 |
| Auto/comma/semicolon/tab delimiter and decimal conventions | Interpret controls next to original preview. | S /3 |
| Trim and exact missing markers | Advanced interpretation with examples; distinguish blank marker, zero, false and text empty. | S /3 |
| Six types: text/integer/decimal/boolean/date/datetime | Grouped searchable column settings, explicit per-column override. | S /3 |
| Date iso/dmy/mdy, boolean conventions, timezone/microseconds | Contextual controls only for applicable types; no ambiguous inference. | S /3 |
| Preview inference/sample vs full-file validation | Clearly labeled sample and separate Validate complete file. | S /3 |
| Structure/type issues, bounded/full validation report | Linked line/column summary, correction path and existing report download. | S /3 |
| Metadata title/description/category/source/observation date | Describe stage; explicit user-declared source, no implied source verification. | S /3 |
| Resumable private receipt, expiry, already-published state | Same receipt URL and GET; last accepted server state only, no recovery of unsaved fields. | S /3 |
| Validation revisions, publication/cancel, atomic immutable versions | Review stage, explicit publish/cancel; changed config invalidates old validation; uncertain outcome verifies receipt. | S /3 |
| Source IDs, original cells, exact decimals and leading zeros | Preview/table original/interpreted presentation, backend facts unchanged. | C data summary/table; full S /2–3 |
| Dataset overview/data/columns/analysis/quality/versions tabs | Existing local views, pinned source strip, warning before destroying metadata edits. | S /1–5 |
| Full-version search, typed filters, AND/OR and presence | Compact toolbar + expanded filter builder; scope summary; no visible-row-only filtering. | C scope; full S /2 |
| Sort, missing-last semantics, pagination/page size | Table toolbar and clear counts; preserve original server query behavior. | S /2 |
| Original/interpreted toggle and missing/empty distinctions | Explicit table mode and accessible cell text; presentation-only column hiding. | C sample exact values; full S /2 |
| Profiles: types/dimensions/completeness/distinct/min/max/mean | Columns/quality summary clearly states full-version scope. | C representative completeness; full S /2 |
| Immutable version selector/history/config/source hash | Source selector and history inspection, never silent latest-version substitution. | C selector/context; history S /2–5 |
| Owner metadata editing/archive/restore | Management area, explicit save, warning-only current editor. | S /1,5 |
| Dependencies, exact-title deletion and blocked deletion | Consequence/dependency review separate from archive/suspension; keep backend refusal. | S /5 |
| Suspended source and retained data/access records | Unavailable-state explanation; only permitted revoke/admin restore routes shown. | S /2,5 |

## Analysis and visualizations

| Existing capability / source owner | Proposed location and behavior | Coverage / later phase |
| --- | --- | --- |
| Explicit dataset/version picker including archives/pagination (`analytics/controls`) | Source stage/strip; retain existing selected source even if not in current list page. | C representative picker; full S /4 |
| Independent source search/filters | Scope summary and advanced builder; recompute only on explicit Calculate. | C scope; full S /4 |
| All 13 operations (`analytics/contracts`, `api`) | Measure picker: rows/present/missing/distinct/sum/mean/median/min/max/q1/q3/stddev_sample/stddev_population. | C mean; all others S /4 |
| Up to eight labeled measures | First required measure visible; additional measures disclosure, none removed. | C single measure; full S /4 |
| Up to two groups, time intervals | Grouping controls with exact/day/month/year where applicable. | C group; full S /4 |
| Ranking by measure/group, direction, group limit/omissions | Advanced result ordering; retained explicit omissions and full denominators. | S /4 |
| Table/KPI/bar/line/histogram/pie/scatter (`charts`, `results`) | Readable plot/metric plus exact tables; correct eligibility, axes, missing data and limits. | C bars/counts/completeness; other charts S /2,4 |
| Histogram bins, constant/missing values | Distribution setup/result details; retain interval conventions and exact boundaries. | S /2,4 |
| Scatter pairs, omitted/missing points, deterministic order | X/Y/point limit, readable points and exact-pair inspector, no causal claim. | S /2,4 |
| Temporal grouping, UTC and missing breaks | Time controls/plot with actual observed groups; no inferred history from collection metadata. | S /2,4 |
| Labels/unit/precision/legend (`DefinitionControls`) | Optional appearance disclosure; readable rounding only, exact source values inspectable. | C representative; full S /2,4 |
| Pharmaceutical templates/prerequisites | Early template/custom choice; unavailable reason, never guess field mapping. | S /4 |
| Missingness: columns/groups/rates/affected rows | Dedicated result structure with denominator, exact table and permitted original-row inspection/pagination. | C representative 1/9; full S /4 |
| IQR: factor/min group/quartiles/fences/insufficient/zero-IQR | Dedicated diagnostics, comparable group explanation and affected rows; no automatic correction. | C representative flag where shown; full S /4 |
| Recommendations: types/cardinality/reasons/editable definitions | Recommendation choice opens an editable configuration; Calculate/Save remain explicit. | S /4 |
| Comparison: two sources, schema/mappings, independent filters | Two clearly labeled source contexts and mapping review; no name-based equivalence. | S /4 |
| Comparison: complete unique keys/type validation/row differences | Separate optional key stage, exact counts/rows and actionable duplicate/incomplete-key errors. | S /4 |
| Saved definitions/title/description/revision/source FKs | Save at outcome boundary; reopen configured, calculate explicitly, no result snapshot. | C save affordance; full S /1,4 |
| Saved list/edit/delete and source dependency protection | Resource list/management retains owner control and existing revision/dependency constraints. | S /4–5 |
| Shared read-only advanced results/copy | Exact permitted saved execution; originals/diffs require separate dataset rights. | S /4–5 |
| Stale/failed/invalid/busy/unknown/conflict states | Explicit result lifecycle, input retained while mounted, no stale result or auto POST replay. | Local calculation specimen; full S /1,4 |

## Dashboards

| Existing capability / source owner | Proposed location and behavior | Coverage / later phase |
| --- | --- | --- |
| Own/shared list/create/open (`dashboards/pages`) | Clear title/revision/access, widget count and next action. | C open shell; full S /5 |
| Empty or saved-analysis widgets, copied definition | Edit add controls; selected saved analysis copied, later original edits do not propagate. | S /2 |
| Per-widget source/filter/calculation/appearance/preview | Focused inspector uses same analytical controls; readability layer does not change definition. | C inspect affordance; full S /2 |
| Standard/horizontal/donut; KPI/table/group/time/histogram/scatter | Same eligible variants remain configurable and inspectable. | C representative bars; full S /2 |
| Order/duplicate/remove, width4/6/12 and height3–12 | Explicit layout controls plus existing pointer/keyboard gestures; mobile order matches array. | S /2 |
| Explicit view/edit/save/discard, optimistic revision | Clear mode/action boundary; warning-only edits, no automatic saves. | C representative actions; full S /1–2 |
| Category/numeric/date/presence filters | Reader toolbar with readable applied scope, fixed-vs-editable state; native accessible control patterns. | C representative category scope; full S /2 |
| Allowed categories/bounds/defaults and explicit mappings | Structured author mapping review by source/widget; retain validation and effective condition limits. | S /2 |
| Reader reset retains authorized perimeter/base filters | Plain explanation, no mutation of owner defaults; no unrestricted reset. | Local preset specimen where implemented; full S /2 |
| Per-widget pending/error/stale recovery and queue/debounce | Independent honest status; no new unbounded requests or stale inaccessible values. | S /2 |
| Expanded inspection/exact values/source/method | Legible dedicated inspection using authorized result route, keyboard return/focus. | C disclosure/specimen; full S /2 |
| Copies require every source and inherit no grants/approvals | Management copy with clear requirements; unchanged server decision. | S /2,5 |

## Sharing and administration

| Existing capability / source owner | Proposed location and behavior | Coverage / later phase |
| --- | --- | --- |
| Exact-email dataset/analysis/dashboard grants (`sharing/panel`) | Resource sharing review; no user directory or anonymous link. | S /5 |
| Separate dataset vs result access and immediate revoke | Clearly state scope and next-request consequences; no raw data for result-only grant. | C context; enforcement S /5 |
| Original-owner onward authorization by exact saved revision | Source/config review with explicit approval/revoke; changes require renewal. | S /5 |
| Dataset archive/disabled-owner grant behavior | Separate access consequences; retained valid explicit grants per contract. | S /5 |
| Admin overview totals/imports/failures (`admin/pages`) | Compact operational overview; explain metric meanings and bounded failure counts. | S /5 |
| Account role/active review, session invalidation/last-admin | Names first, explicit before/after confirmation, existing safeguards. | S /5 |
| Dataset metadata/version supervision, suspension/restoration | State-specific management with reason and consequences; no implicit content reading. | S /5 |
| Explicit logged content inspection/query/sort/page | Protected inspector with reason/confirmation per page; no private patient conversation access. | S /5 |
| Activity actor/action/kind/resource/outcome/UTC dates/pagination/details | Recent readable events; advanced UUID filters disclosed; all current filtering remains. | S /5 |

## Pharmacy assistant

| Existing capability / source owner | Proposed location and behavior | Coverage / later phase |
| --- | --- | --- |
| Visitor accessibility, independent account state (`chat`, `App`) | Distinct conversation surface within the candidate's visual family; no login prerequisite. | C /6 |
| Three example-prefill prompts | Compact first-use aid; prefill only, never auto-submit. | S /6 |
| Medication identity/strength/form/presentation (`results`) | Highly legible identity/package hierarchy before recorded fact. | C /6 |
| Ambiguity, suggestions, refinements and candidate pagination | Difference-readable choice rows, inactive previous-step choices labeled; no silent selection. | S /6 |
| Contextual follow-ups and multiple-reference choices | Context visible in transcript/result; explicit reference selection. | C representative question; full S /6 |
| Recorded unit price and complete-package totals | Backend numbers formatted only; missing prices stay unknown. | C unit price; total S /6 |
| Quantity clarification/incomplete totals | Actionable clarification with no invented sum. | S /6 |
| Source/date/status/conflicts and full details | Compact visible primary provenance plus attributed source-detail disclosure; commercialization not stock. | C primary provenance; conflicts S /6 |
| Pharmacy names/address/city/phone/source/date | Readable directory results, safe telephone/source links. | S /6 |
| Default city, partial/truncated Rabat coverage | Visible limit and refine action; no distance/duty/open-hours/stock claim. | S /6 |
| French/Arabic/Darija/mixed extraction and automatic script direction | Preserve backend and per-message direction; French chrome not full RTL localization. | S /6 |
| Temporary 30 min state/read-only refresh restoration | Existing accepted server transcript only; no replay/renewal or new patient history/draft persistence. | C duration; full S /6 |
| 2,000-character limit/IME/Enter/Shift+Enter | Visible invalid count/correction, preserve current draft, appropriate input/focus. | Local specimen where implemented; full S /6 |
| Loading, follow-latest and focus/scroll behavior | Honest in-flow waiting, controlled scroll, no hidden content behind keyboard/composer. | S /6 |
| Failed typed question/edit/retry | Failed text visible and editable while mounted; explicit retry only. | Local specimen; full S /6 |
| Pending/uncertain outcome/verification | Verify read-only state before another send, no automatic POST replay. | S /6 |
| Quotas/cooldown, offered choices without inference | Clear countdown and eligibility, no paid/provider fallback. | S /6 |
| Storage blocked/restoration unavailable | Existing mechanism retains explicit notice; warning-only policy adds no storage. | S /6 |
| Explicit reset/cancel/server invalidation/reset failure/expiry | Distinct destructive review, clear only after success or expiry; no false restoration. | Local visual specimen; full S /6 |
| No clinical recommendation/diagnosis/live offers | Factual limitations in copy and result hierarchy across all directions. | C /6 |

## Cross-surface requirements and future verification

Focus/keyboard, native labels, semantic current location, route titles, text contrast, legible data, reduced motion, meaningful loading/error/empty/success and no page overflow apply to every row. Permission/authentication tests require a real authorized test backend; a visual role toggle or fixture cannot prove enforcement. Numeric oracles remain the CP6 README and existing test suites. All current maximum bounds and API validation remain unchanged.

This mapping was checked against `src/app/App.tsx`, the feature modules in `accounts`, `datasets`, `analytics`, `dashboards`, `sharing`, `admin`, `chat`, `results`, and `docs/project/full-stack-coverage.md`. Proposed presentation-only column search/visibility and local staged navigation do not create new server-backed product features. Search over all resources, new import formats, forecasting, public publishing, server drafts and permanent patient history are excluded.
