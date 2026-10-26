# Interaction blueprint — all three visual alternatives

Proposed UI organization; existing contracts remain authoritative. The three candidate visual systems change composition and density, not capability or permission semantics. Mode: **Operate** for workspaces/assistant; **Read/Persuade** only for the introduction's explanatory content. No candidate is selected.

## Shared frame, state vocabulary and navigation

Keep current route URLs and supported dataset/version/tab queries; retain deep-link and protected-return behavior. Registre uses horizontal primary navigation and a parallel parameter/result workspace; Traverse uses a left primary rail with a staged task surface; Cahier uses horizontal document tabs and sectioned reports. At tablet widths parallel panes collapse deliberately. At 390/320px use labeled navigation/disclosures and one primary reading column; no icon-only navigation or crushed desktop plot.

Every work view exposes its title, current location, ownership/read-only state and meaningful source/version/scope. Primary actions name the operation: Calculate, Save analysis, Validate complete file, Publish version. Never label calculation as saved or saving as sharing. Local selection state must not imply a backend write. Shared screens show only metadata authorized by their response; they do not fetch raw rows for a convenient inspector.

States: initial/empty; loading; loaded; changed and not calculated; calculating; result available; edited and not saved; saving; saved; validation failed; source unavailable; permission denied; conflict; outcome unknown. Preserve status announcements and distinguish an explicit mutation from read-only verification. Keep stable layout/context during loading where possible. Show an actionable error and preserve current-editor input; never show stale success after a failed or modified request. **[Warning-only policy](UNSAVED_CHANGES.md)** applies wherever leaving destroys unsaved input.

## 1. Entry, authentication and signed-in workspace

Routes `/`, `/connexion`, `/inscription`, `/espace`, `/profil`. The introduction explains two actual paths: private CSV analysis and a visitor-accessible temporary pharmacy assistant. A labeled synthetic example may demonstrate the workflow; no customers, clinical authority or live price claims.

Keep existing registration/login/password requirements, names, autocomplete, CSRF and exact-origin checks. Errors appear beside relevant fields and in a linked summary after failure; retain inputs as permitted and never store passwords. On protected login return, preserve valid source/version/query destinations. Route changes update title/current location and deliberately place focus at new content without trapping browser navigation.

The signed-in workspace prioritizes existing authorized datasets/analyses/dashboards and Import, not decorative KPI tiles. Existing paginated lists support these entry points; no global search, full recent-history service, user directory or new endpoint is invented. Profile edits and password changes retain current own-user/session behavior. Permission-dependent controls complement backend checks.

## 2. CSV import: File → Interpret → Describe → Validate/publish

Routes `/donnees/importer`, `/donnees/imports/:id`, with optional existing dataset target. The four stages are real navigable UI stages in one logical in-memory editor, not new backend entities.

1. **File:** accepted CSV format/encoding/limits and attributed sample; select/upload explicitly. Empty/oversized input receives immediate guidance. Show progress/status without pretending publication has begun.
2. **Interpret:** compact file/row/column summary, original sample preview beside delimiter/encoding/decimal/trim/missing-marker choices. Group column settings with clear names/types and a search/filter only over the local returned column definitions. Allow all six types and explicit date/boolean conventions. An inferred type is a suggestion. Original cells and identifiers remain intact.
3. **Describe:** title/description/category/source/date fields for a new dataset; for added versions show the existing target and retained metadata clearly. Changes between safe in-editor stages retain the same mounted values. Leaving warns before destruction; no persisted draft restoration.
4. **Validate/publish:** explicitly validate the entire file. Show structure/type errors by line/column, linked configuration correction and existing full report download. Any relevant edit invalidates the former validation. Valid review states exact target, dimensions, interpretation and resulting private immutable version. Publication requires its own explicit action.

Handle private resumable receipt GET, one-hour expiry, already-published receipt and uncertain publication without duplicate mutations. A refreshed receipt reflects only server-accepted state, not unsaved options/metadata. Cancel staging uses its existing explicit endpoint and consequence. Publication success offers Explore this actual version / Analyze this actual version. No partial success, row dropping, silent invalid-to-null conversion, JSON/Excel import or automatic publication.

## 3. Dataset exploration and lifecycle

Routes `/donnees`, `/donnees/:id`, existing overview/data/columns/analysis/quality/versions views. Lists distinguish owned, shared, archived and suspended resources. Offer import clearly when empty and keep pagination. No resource type is hidden to simplify the UI.

Use an explicit version selector and compact source summary. The data view leads with rows, then a compact search/sort/filter toolbar; advanced filter construction is discoverable. Search/filter/count/pagination retain full-selected-version semantics. Typed operators, AND between filters/OR within selected values, missing/present and canonical input conventions remain clear. Original/interpreted toggle is explicit. A deliberate horizontal table scroller, sticky context and optional presentation-only column visibility do not change calculation scope.

Column and quality profiles retain dimensions, types, completeness, present/missing/distinct and min/max/mean semantics; full-version profiles must not appear to reflect active row filters. Version history retains source hashes/configuration and immutability. Overview metadata editing follows warning-only safeguards. Archive/restore, administrative suspension, grant revocation and permanent deletion have different labels/consequences. Deletion still reviews versions/dependencies/grants, blocks when required and confirms exact title. Shared dataset recipients can explore/create personal analyses but cannot mutate the original.

## 4. Analysis: Source → Question → Result → Save

Routes `/analyses`, `/analyses/nouvelle`, `/analyses/:id`, dataset analysis deep link. Registre shows parameters beside results; Traverse stages the work; Cahier sections a report with source/calculation strips. All retain a visible compact source/version/scope and a nearby Calculate action.

Select a pinned immutable source. Offer applicable pharmaceutical templates and custom analysis early; show unavailable prerequisites instead of guessing mappings. Required measure/column/group/visualization precedes advanced filters, extra measures, ranking, chart labels/unit/precision and detailed conventions. All 13 operations, up to two groups/eight measures and configured limits remain available. Source switches reset/revalidate exactly as existing behavior; never silently use latest versions or same-name equivalence.

Calculation is explicit. Clear obsolete results on settings changes/failure. Results lead with useful values and readable plots; source/method/missing denominators/omissions remain visible or clearly inspectable. Exact decimal table alternatives are accessible; presentation rounding does not change canonical strings or calculations. All chart types have eligible-data guidance; invalid mean/sum pies remain invalid.

Title/description and Save appear at a logical result boundary, not several screens away. Saving retains the complete definition and source references, not a result snapshot or sharing grant. Reopening presents saved configuration and an explicit Calculate action. Pending/save-conflict/unknown states keep input while mounted and offer honest verification. Ordinary exit warns; accepted discard/reload has no recovered draft.

### Advanced functions

- **Missingness:** selected columns, optional groups, rates/denominators, affected typed/original rows and pagination; zero/false/empty text stay distinct.
- **IQR:** comparable groups, numeric column, 1.5/3 factor, minimum group convention, Q1/Q3/fences, insufficient/zero-IQR states and affected rows. Explain a statistical flag is not a correction or clinical judgment.
- **Recommendations:** inspect selected types/cardinalities, read reasons/limits, apply a suggestion as an editable definition; calculate/save explicitly. No hosted model is implied.
- **Comparison:** two explicitly labeled versions/sources and their independent filters; separate statistical correspondences and optional complete/unique row keys. Review schema/type differences, unmapped columns, summary statistics and permitted row differences. Duplicate/missing keys are actionable errors, not fuzzy matching.

Saved analysis lists support reopen/edit/delete. Shared analyses are read-only exact definitions: permitted execution, context, no unauthorized originals/row diffs, and a permission-checked private copy action. Add-to-dashboard copies the saved definition rather than live-linking future edits.

## 5. Dashboard reading, editing, filtering and inspection

Routes `/tableaux`, `/tableaux/nouveau`, `/tableaux/:id`. Reading leads with dashboard title/revision/access and mapped filter scope, then meaningful readable widgets. Each widget shows its result and source/version; full exact values/method are a named expanded inspection. No full analysis-form boilerplate inside a tiny widget. Loading/errors remain per-widget; revoked or unavailable sources remove old values rather than leaving a stale favorable chart.

Authors explicitly enter Edit and Save/Discard. Retain add-empty/add-saved-analysis, widget configuration/duplication/removal, array reading order, 4/6/12 widths, 3–12 heights, supported variants, preview and pointer/keyboard arrangement. Keep metric settings separate from display dimensions. Mobile stacks in the same reading order, with accessible controls replacing drag dependence.

Filter authors configure category/numeric/date/presence, allowed choices/bounds/defaults, reader-editability and explicit widget/column mappings. Improve presentation with structured mapping review and approachable selection controls, but do not infer equivalent columns. Reader changes stay local; Reset means the full **authorized perimeter**, never an unrestricted dataset. Preserve base widget filters and UTC date handling. Rendering must respect the existing two-operation queue/debounce rather than firing new computations per keystroke indiscriminately.

Expanded result inspection is a focused view with exact table, source/scope and clear return/focus. It must use only its already-authorized result route, not call raw rows for result-only readers. Copy retains immutable references and requires every source grant; grants/approvals never copy with it.

## 6. Sharing, permissions and administration

Sharing stays attached to datasets/analyses/dashboards. Present What is shared / With whom / Required source authorization. Use exact email of an existing account, no directory or new user lookup. Show recipients and explicit revoke confirmation; saving itself never grants access. Distinguish raw dataset access across its versions from permitted result queries. Original-owner authorization review is revision-bound; any edit requiring renewal must be explained before outward sharing. No prototype pretends to validate real permissions.

Administrator route `/administration` keeps overview/users/datasets/activity. Show meaningful names and outcomes first; disclose UUID and advanced filters. Preserve overview counts/import failures, account role/active review, session invalidation and last-admin protections. Dataset supervision metadata does not silently inspect content. Content inspection requires reason/confirmation and is logged per page; suspension/restoration keeps data/configurations and only valid existing access. Activity filters/events/details retain UTC and audit semantics. No admin access to patient conversations is introduced.

## 7. Pharmacy assistant

Route `/assistant` remains independent of account authentication. Compact welcome explains recorded information and partial Rabat coverage; keep three useful examples as optional prefill rather than a large decorative hero. No example submits automatically.

The response composition prioritizes medication name, strength, form and package; recorded unit/complete-package total; primary observation date/source; stock/coverage qualification. Candidate choice lists make package differences equally legible before selection. Retain refinement and further-candidate pagination, multiple references and contextual follow-ups. Unknown prices/dates stay unknown. Commercialization is recorded status, not stock. Source conflicts retain primary facts plus attributed differences, not a synthesized new price.

Pharmacy results show recorded name/address/city/phone/source/date with safe phone/source links, default-city and truncated-result guidance, and unknown hours/duty/stock. No proximity claim or clinical advice. French interface supports automatic Arabic/mixed message direction; it is not full RTL localization.

The composer explains length/invalidity visibly and accessibly at every width. Preserve Enter/Shift+Enter and IME composition. Announce new messages/status without focus stealing; keep result and focused controls above the mobile keyboard. Temporary expiry, restore pending, blocked browser storage, cooldown, provider unavailable, failed/unknown/pending outcomes and reset failure get truthful next actions. Offered choices may remain usable when inference is blocked. Retry/edit/verify are explicit; no POST replay, automatic provider change or billable call in design review. Reset's destructive confirmation and server invalidation precede clearing the UI.

No unsent draft persistence or patient history is added. Existing accepted server messages may be restored by their existing read-only mechanism; that does not restore an unsent question after an accepted reload/crash.

## 8. Common state and accessibility requirements

### Readable graphics across existing chart types

The chosen candidate's data palette is semantic, separate from error/success feedback. Use stable series assignment, explicit units and tabular text values; combine hues with labels, line patterns or point markers. Extended palettes in the candidate JSON files are proposals, not an accessibility guarantee. Do not shrink an entire SVG to fit a widget: responsive bounds change plot geometry while labels retain CSS pixel size (axis minimum12px, values/tables minimum14px). Long labels wrap or use an accessible full-value disclosure, rather than disappearing in an ellipsis alone.

| Existing presentation | Proposed legibility contract |
| --- | --- |
| KPI | Measure, value, unit and denominator in a meaningful widget; no decorative secondary metric or invented trend. |
| Bars / horizontal bars | Zero baseline, units, consistent comparison scale, visible group/value labels and exact table. Avoid dense rotated categories; use the existing horizontal variant or a deliberate bounded plot region. |
| Line / temporal grouping | Actual UTC intervals, visible axes, distinct series markers/patterns, gaps for missing observations; no fabricated interpolation or trend claim. |
| Pie / donut | Existing eligibility only; direct category/value/percentage labels and an exact alternative. Preserve denominator and declared omitted groups; a color legend alone is insufficient. |
| Histogram | Clear interval/last-bin conventions, count axis, actual bounds and missing/constant-data explanations; no clinical interpretation of a distribution. |
| Scatter | X/Y column and unit, readable point markers, omitted-pair count and deterministic exact-pair table. Do not imply causality or calculate an unrequested regression. |
| Exact tables | Semantic row/column headers, right-aligned numeric columns, original precision accessible, explicit missing text, named keyboard-scrollable region where needed. |

On a narrow widget or phone, move supporting legends/method prose and stack exact values; do not silently drop series or change aggregation. Existing widget geometry and analytical limits remain authoritative. A focused inspection provides space without new API permissions. Loading never leaves an old plot labeled as the current result. None of these rules changes calculation algorithms or introduces a new visualization feature.

| State | UI expectation |
| --- | --- |
| Empty | Explain what is absent and a permitted next action; distinguish no resources from no matching rows and denied access. |
| Loading | Keep context/structure where possible; status announcement and truthful pending label; no decorative repeated animation. |
| Changed | Explain result must be recalculated/saved, using separate labels; do not show obsolete numbers as current. |
| Validation failure | Linked summary and near-field guidance, focus where useful, no input wipe. |
| Success | Persistent contextual confirmation of exactly what succeeded; no implied publication/sharing. |
| Network/unknown outcome | Preserve mounted values, identify uncertainty, verify existing state, explicit retry only. |
| Conflict | Explain current resource changed; retain mounted input; no silent merge. |
| Permission/source unavailable | Remove inaccessible results, preserve honest scope; do not expose content to help explain denial. |

Use native labels, semantic headings, real buttons/links, aria-current, dialogs with focus restoration, visible focus, text alternatives/exact data for graphics and reduced motion. Color is not the sole status signal. Essential details remain readable; target primary touch actions at least 44px, without misrepresenting this as a universal conformance threshold. Normal text targets 4.5:1; meaningful control/state cues 3:1 where required. Deliberately scrolling data tables/plots are allowed; page-wide accidental overflow is not.

## Review boundary

### Full navigation placement after a direction is selected

| Destination | A — Registre | B — Traverse | C — Cahier |
| --- | --- | --- | --- |
| `/espace` | Workspace/home text link | Workspace primary rail entry | Workspace top-level link |
| `/donnees`, import, dataset views | Data primary link; Import action; dataset local tabs | Data rail entry; import progression and local dataset tabs in content | Data top-level link; dataset document tabs/sections |
| `/analyses`, new/saved analyses | Analysis primary link; list/new then parameter/result split | Analyses rail entry; source/question/result/save in task area | Analysis top-level link; list/new then document tabs and section anchors |
| `/tableaux`, new/saved dashboards | Dashboards primary link; focused widget inspector | Dashboards rail entry; view/edit toolbar and inspector | Dashboards top-level link; view/edit toolbar, report-styled widgets within the saved grid |
| `/profil`, logout | Labeled account menu | Labeled bottom-rail account utility; mobile utility | Labeled account menu in top frame |
| `/administration` | Administrator-only primary/menu destination | Administrator-only rail entry | Administrator-only top/menu destination |
| `/assistant` | Public assistant surface in same visual family | Public assistant surface; public-access utility replaces authenticated account identity | Public consultation surface in same family |

Primary grouping never changes the route table. Public assistant access does not acquire an AccountProvider/login dependency; platform links from it follow current protected routing. Use a labeled mobile navigation disclosure when full authorized destinations no longer fit. Keep navigation distinct from open-resource document tabs; the static prototypes' comparison/index links are review tools, not proposed product destinations.

The prototypes show representative structures and local interaction specimens, not every workflow above. [CAPABILITY_MAP.md](CAPABILITY_MAP.md) identifies what is composed, specified or reserved for later production/browser checks. Scope and warning policy are decided; composition, final tokens and selected direction still require approval. Phase 1 cannot start from merely viewing a prototype.
