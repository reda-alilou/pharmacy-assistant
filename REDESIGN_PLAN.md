# Pharma Analyse redesign plan

**Status: Phase 0 accepted and closed. Direction B — Traverse, with the agreed V2 refinements and green identity, is the approved design foundation. Phase 1 is implemented on `feature/ui-ux-redesign` and awaits user acceptance. Phases 2–7 have not started and remain gated.**

Prepared 2026-10-25 for the existing web application in `apps/web/`.

## 1. Direction and scope

The user selected a coherent redesign of both the import-to-result journey and dashboard readability, plus a recomposed pharmacy assistant that prioritizes medication identity, recorded prices, observation dates and provenance. This is a workflow and interaction redesign supported by a consistent visual system.

The platform will organize work around **source → question → result → saved work**, rather than a sequence of equally prominent feature panels. The assistant will organize answers around **identity/presentation → recorded fact → date/source → next useful action**, with a shorter welcome and clear recovery.

The user authorizes a major visual redesign and exploration of substantially different professional visual directions. The incumbent palette, navigation composition and component styling are not preservation requirements. Phase 0 presented three alternatives with comparable content. The user has now selected Direction B — Traverse with the V2 refinements below. No further Traverse V2 prototype is required; implement refinements directly in their relevant approved phases. Tables, plots, forms and toolbars should look like the task they perform. Cards are reserved for meaningful independent objects; a border and rounded container are not the default answer to every grouping problem. No gradients, decorative card side strips, decorative statistics, invented clinical imagery, arbitrary icon tiles or oversized marketing headings inside task screens.

Existing names, factual French copy, functionality and product/security constraints remain the basis. The Traverse candidate system supplies the approved foundation; minor implementation choices may be resolved autonomously within its green identity and preservation constraints. [DESIGN.md](DESIGN.md) remains the existing-design record and is not overwritten during Phase 0.

### Approved decisions

1. **Major visual redesign:** explore substantially different professional directions; the current look is evidence, not approval. Direction B — Traverse is now selected, with the V2 refinements below; A/C remain reference studies. Existing no-gradient/no-decorative-card-side-strip constraints remain.
2. **Warning-only unsaved changes; no persisted drafts:** ordinary routes, local tabs, back/forward and logout must not silently discard edits. Staying preserves values in the current editor; explicit discard permits leaving and losing them. Failed saves retain current input. Reload/close use native unsaved-change warnings where supported. No sessionStorage, localStorage, IndexedDB, background synchronization or new backend endpoint may be introduced for draft persistence. Accepted reload, crash or discarded navigation has no draft-recovery promise. Existing saved resources, validated import receipts and temporary assistant-conversation restoration retain their current behavior; they are not new unsaved-draft recovery.
3. **Phase order and acceptance:** retain Phases 0–7. Each phase needs explicit user acceptance before the next starts. Overall plan approval does not authorize production implementation or later phases. Phase 0 is closed and Phase 1 production safeguards/feedback are authorized. Explicit Phase 1 acceptance is still required before Phase 2; no blanket implementation approval is inferred.

### Approved Traverse V2 integration

- **Identity:** retain forest/green leadership, readable sans typography, restrained sage selection, clean light working surfaces, and semantic warning/error accents. Minor shades/spacing/component details use implementation judgment; no gradients or decorative side strips.
- **Mobile navigation (Phase 5):** one compact labeled header/menu rather than the tall wrapped rail. Compact task progress preserves every destination/stage and permission-dependent action.
- **Analytical density (Phases 2 and 4):** borrow A’s precise alignment and simultaneous parameter/result visibility when desktop space permits. Keep B’s navigation/progression and full-width advanced/comparison controls where needed. Never shrink chart text or remove exact values to fit.
- **Source readability (Phases 3 and 4):** borrow C’s concise source hierarchy. Keep pinned version, relevant dates and active analytical scope visible; disclose supporting identifiers/method details without hiding important context.
- **Assistant composition (Phase 6):** one authoritative medication fact block per response; no second mobile dossier repeating identity/package/price/date/source. Desktop evidence adds unique provenance/conflicts. Retain historical messages, clarification and temporary-conversation behavior.
- **Truthful editing status (Phase 1 onward):** no “Brouillon local” label or recovery implication. Distinguish never-saved, modified, calculation-required, confirmed save, conflict and unknown outcome. Calculate is not Save.
- **Authorization:** no V2 prototype; implement these refinements directly as relevant phases are approved. Phase 1 provides the shared warning/feedback foundation in the existing screens, not the Phase 2–6 composition redesign.

## 2. Evidence and priorities

Sources: [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md), the [completed critique](.impeccable/critique/2026-10-25T17-41-25Z__apps-web.md), current frontend code, and browser evidence under `artifacts/critique-apps-web/`.

The critique baseline is **24/40 for the analytical platform** and **29/40 for the assistant**. These are expert heuristic assessments, not task-success rates or accessibility certification.

| Priority | Established problem | Evidence boundary |
| --- | --- | --- |
| 1 | Analysis header navigation and dataset local tabs discard edits without confirmation. Save feedback can disappear on refresh. | Reproduced in the current frontend with intercepted synthetic responses; source corroborated. Import/profile draft risks require explicit characterization. |
| 2 | SVG chart text shrinks to approximately 5–6px bounds; widget prose and nested scrolling obscure results. | Current synthetic renders and measurements, consistent with retained captures. |
| 3 | A simple analysis exposes 37 main controls and a result page over 5,500px desktop / 6,500px mobile. Import step labels do not sequence the work. | Current synthetic renders and source. |
| 4 | Global location is unmarked; mobile navigation wraps; page focus/title and task hierarchy are weak. | Current rendered and source evidence. Screen-reader consequences were not directly tested. |
| 5 | Assistant identity/provenance is small; a 2,001-character mobile draft disables Send while hiding its explanation. | Current rendered results/local drafts. |
| 6 | Equivalent actions and states use different controls, spacing, confirmations and visual emphasis. | Current source and rendered evidence. |

The plan also closes the critique's inspection gaps through real authenticated browser review where available. Synthetic UI checks will never be reported as proof of backend correctness or actual permissions.

## 3. Non-negotiable preservation contract

- Keep existing route paths, supported query parameters, deep links, refresh behavior and protected-destination return after login. Reorganizing navigation does not rename URLs.
- Preserve API paths, request/response schemas, CSRF/origin checks, account sessions, roles, backend ownership checks and current error semantics. No backend/domain migrations or new endpoints are assumed.
- Preserve raw/original cells, identifiers/leading zeros, missing versus zero/false/empty text, decimal strings, timestamps, source attribution, immutable versions and atomic publication.
- Preserve analytical algorithms, explicit version pinning, filters/search over complete versions, denominators, chart eligibility, declared omissions, numeric precision and all four advanced features. Layout code must not become a second calculation engine.
- Preserve separate dataset/result grants, revision-bound original-owner authorization, permission-aware copies, immediate server authorization, revocation and suspension effects. A compact UI must not hide or circumvent these distinctions.
- Preserve administrative logged inspection, reasons/confirmations, last-admin safeguards and session invalidation. No account directory is added to sharing.
- Preserve assistant matching/clarification, stored-price arithmetic, multilingual interpretation, source conflicts, temporary 30-minute conversations, read-only restoration, cooldowns, explicit retry/reset and no automatic POST replay/provider fallback. No permanent patient history is introduced.
- Keep frontend data ownership separate from the assistant catalogue. CSV imports must not imply that they update the assistant's medication records.
- Keep existing runtime credentials, private data, source/history/evaluation evidence and database volumes intact. No container/backend lifecycle, hosted inference, deployment, commit or publication is implied by plan approval.
- Preserve all currently available functionality. Advanced controls may move behind clear disclosure, but cannot disappear or become accessible only through an unsupported shortcut.

Any proposal that cannot meet these boundaries with the existing contracts returns for a separate decision. The implementation must not quietly widen scope to make a design easier.

## 4. Phase structure and review gates

| Phase | Independently reviewable outcome | Dependency |
| --- | --- | --- |
| 0 | Three visual proposals, complete interaction blueprint/capability map, warning-only specification and candidate systems | Accepted and closed; Traverse plus V2 selected |
| 1 | Reliable warning-only editing safeguards and feedback across current screens | Authorized now; stop for user review on completion |
| 2 | Readable charts, data tables and dashboard view/edit experience | Phase 1 accepted |
| 3 | Guided CSV import and useful handoff into exploration/analysis | Phases 1–2 accepted |
| 4 | Guided analytical workspace covering basic and advanced analysis | Phases 1–3 accepted |
| 5 | Coherent navigation, workspace, resource management, sharing and administration | Phases 1–4 accepted |
| 6 | Recomposed, legible pharmacy assistant and complete recovery presentation | Shared foundations and Phase 5 accepted |
| 7 | Cross-application consistency, accessibility, integration and final validation | Phases 1–6 accepted |

The order follows the user's priorities. Foundational typography/components are designed in Phase 0 and implemented incrementally with the first surface that needs them; they are not deferred to a cosmetic pass at the end. Phase 7 verifies convergence and closes remaining cross-surface inconsistencies.

**Every phase ends with a stop for user review.** Its packet contains changed routes/components, before/after evidence, completed acceptance checks, regression results, known limitations and the next phase's scope. Technical checks passing do not substitute for user acceptance. Unresolved material failures stay open or are explicitly deferred by the user. Plan approval does not waive later gates or authorize starting all phases together.

## Phase 0 — Blueprint and visual foundation

**Review packet:** [artifacts/redesign/phase-0/index.html](artifacts/redesign/phase-0/index.html) presents Registre, Traverse and Cahier with desktop/mobile compositions. [REVIEW.md](artifacts/redesign/phase-0/REVIEW.md) records the approval decisions, evidence and limitations. The user subsequently approved Traverse with V2 and authorized Phase 1. The three original compositions are retained as historical evidence; do not build another V2 prototype.

**Routes/components:** representative `/donnees/imports/:id`, `/donnees/:id?tab=data`, `/analyses/nouvelle`, `/tableaux/:id`, `/assistant`; shared shell, buttons, fields, feedback, disclosures, tables, chart labels and dialogs. Sources: `src/app/styles/`, `src/shared/ui/`, affected feature components.

**Problems addressed:** the existing record is not an approved direction; the critique's proposed structures need coherent behavior, realistic density and a shared component vocabulary before production edits.

**Authorized Phase 0 work:** create three genuinely distinct professional alternatives, each with desktop (1440px) and mobile (390px) compositions for an analytical workspace, populated dashboard and medication-result assistant. Consider 320px/tablet behavior. Keep comparable existing synthetic/test-fixture content across alternatives. Save navigable static prototypes, screenshots, a comparison, complete interaction blueprint, existing-capability mapping, warning-only specification, candidate component/token systems and a review/limitations document under `artifacts/redesign/phase-0/`. Do not touch application source, backend/runtime, dependencies, credentials or the DESIGN.md baseline. No hosted inference or billable asset generation. Render local static prototypes where available and correct obvious issues before presentation. No direction is chosen automatically.

**Risks/preservation:** a visually appealing prototype could omit advanced features or permission states. Map every current capability and control to its proposed location. Do not rewrite PRODUCT.md or replace the incumbent DESIGN.md as though the proposal were implemented. No raster-first or landing-page build default is assumed; these are operational app designs.

**Acceptance criteria:**

- Each representative composition shows real fixture content, meaningful long labels, source/version context, the next action and a mobile alternative.
- The capability map accounts for all existing analysis kinds, chart types, dataset lifecycle actions, sharing/admin safeguards and assistant recovery paths.
- The approved warning-only policy is specified without persistence, synchronization or a recovery promise after accepted loss; visual tokens remain proposals until user selection.
- Component/state examples demonstrate stronger hierarchy without excessive panels or decorative content.
- The proposed type specimen uses 15–16px equivalent task/body text, at least 14px for essential medication/provenance text and at least 12px effective plot labels, with rem-based sizing and text enlargement checks. Final values require this review; these are usability targets rather than claims about the incumbent design.

**Browser verification:** review the compositions at 1440×1000 and 390×844, with 320px and tablet checks. If interactive prototype files are used, keep them outside the application and label simulated actions. They must not call production APIs or be mistaken for working functionality. Screenshots and annotations alone do not verify real editing, calculations or permissions.

**Review gate: closed by explicit user approval.** Traverse and the agreed V2 refinements are the foundation. Phase 1 is authorized; later phases retain individual acceptance gates.

## Phase 1 — Warn before discarding and establish reliable feedback

**Delivery:** implemented; awaiting user acceptance. [Phase 1 review](artifacts/redesign/phase-1/REVIEW.md) records the exact files, behavior, 54 passing browser tests, build/lint results, inspected React screenshots and verification limits. The user-approved no-persistence policy is retained. No Phase 2 implementation has begun.

**Routes/components:** analysis creation/editing, dataset overview metadata and local tabs, import configuration/metadata, dashboard editing, profile forms and logout. Primary files: `features/analytics/pages.tsx`, `datasets/pages.tsx`, `datasets/import.tsx`, `dashboards/pages.tsx`, `accounts/pages.tsx` and account/session context. Proposed shared editor-state, navigation-guard, confirmation and feedback helpers belong in shared frontend modules; exact filenames follow implementation review.

**Problems addressed:** SPA navigation bypasses analysis unload warnings; local tabs unmount metadata drafts; busy and dirty behavior varies by editor; metadata confirmation vanishes when its component remounts. Import/profile edge cases need characterization rather than assuming identical failure mechanisms.

**Proposed improvements:**

- Distinguish clean, edited, submitting, saved, failed, conflict and outcome-unknown states. Keep publication and ordinary save distinct.
- Guard internal links, back/forward, local-view changes and logout. Stay keeps work; Discard is explicit. The discard confirmation contains only Stay/Discard; saving remains a separate explicit action in the editor. Use native browser unload protection where custom UI is impossible.
- Keep unsaved values only in the current editor's memory. Staying after a navigation warning preserves that editor and its input. Explicitly discarding permits the requested route/tab/history/logout action and destroys its unsaved draft. Navigable stages within one logical editor may preserve its existing in-memory values; do not add a cross-route draft cache or promise later restoration.
- Do not introduce sessionStorage, localStorage, IndexedDB, filesystem/browser draft persistence, automatic background saves/synchronization or new backend endpoints. A warning is protection against unintended loss, not a promise that a discarded or crashed editor can be recovered.
- Reload/close use native unsaved-change warnings where supported; cancelling keeps the current document/input, accepting may lose all unsaved changes. Browser restrictions and crashes cannot be overridden by a recovery mechanism. Password forms follow the same warning-only policy without storing values. Existing one-hour uploaded-file receipts and their last server-accepted configuration retain their current behavior; they do not recover unsaved configuration/metadata or resurrect expired uploads/files.
- Keep success feedback outside refresh/remount boundaries. Unknown request outcomes lead to status/resource verification and explicit retry, never automatic replay. Retain revision-conflict input only in the current mounted editor for deliberate comparison/correction; leaving after explicit discard loses it.

**Risks/functionality to preserve:** guard loops, false prompts after successful save, blocked password logout, accidental navigation before the user decides and confusing warnings with recovery. Never use a guard to bypass session expiry or current permission checks. Forced authentication/access loss follows existing security behavior; no cross-account draft restoration is introduced. Readers remain read-only. Keep existing request IDs, throttles and revision checks.

**Acceptance criteria:**

- Both critique reproductions warn before losing work. Stay leaves entered values unchanged; explicit discard leaves and loses that unsaved draft. Test route links, local tabs, back/forward and logout separately.
- Browser reload/close warn where supported. Cancelling preserves the current editor; accepting reload starts from the existing server state, with no recovery offer. Crash and discarded-navigation tests must not imply recoverable drafts.
- Failed saves keep values. A 409 does not overwrite; an uncertain response does not duplicate a mutation. Pending controls and confirmations explain what can still finish server-side.
- Success remains visible until the next relevant edit/navigation or deliberate dismissal; it is not lost to an immediate resource refresh.
- No persistent draft store, background draft request or new endpoint exists. Browser storage being unavailable does not affect the warning-only editor policy; retain the assistant's separate existing storage/restoration behavior.

**Browser verification:** use delayed/interrupted/failed/conflicting intercepted responses for repeatable frontend checks, then repeat representative save/reopen flows against an authorized test backend. For every guarded exit, test Stay and Discard, including local tabs, history and logout; test native reload cancel/accept where supported. Verify no draft-storage writes or background synchronization were added and no recovery message appears after accepted loss. Test authentication/permission loss without weakening security. Retain no credential-bearing traces. Re-run relevant account/dataset/analytics/dashboard regressions.

**Review gate:** demonstrate editing safety in the incumbent layout before the larger workflow restructuring begins.

## Phase 2 — Readable results, tables and dashboards

**Routes/components:** `/donnees/:id` data/column/quality views; analysis and shared-analysis results; dashboard list/new/detail view/edit. Main files: `features/analytics/charts.tsx`, `results.tsx`, `shared.tsx`, `datasets/pages.tsx`, `dashboards/pages.tsx`, `dashboards/filter-controls.tsx`; corresponding CSS. Shared result/table primitives may be extracted without moving domain calculation logic into them.

**Problems addressed:** chart text scales with the desktop SVG; full analysis prose dominates widgets; nested scrolling hides content; tables lose row/column context; dashboard editing/filter mapping is visually dense.

**Proposed improvements:**

- Separate full analytical inspection from a compact dashboard result presentation. A widget leads with its metric/chart, followed by concise source/version/scope. Exact values, assumptions, omissions and full method remain accessible through labeled disclosure or an expanded inspection view.
- Make plots container-aware. Preserve readable labels/ticks after all transforms; allow intentional chart scrolling or adapted orientation when content cannot fit. Keyboard users receive an equivalent value-inspection path; native hover titles alone are insufficient.
- Provide a focused expanded-widget view with clear return/focus restoration. Keep chart configuration independent of saved grid size. Preserve 4/6/12 column widths, 3–12 row heights, array reading order, all current variants, keyboard/pointer controls and copied-definition semantics.
- Use a compact exploration toolbar and collapsible advanced filters. Add column visibility as presentation state, sticky header/identifying column where applicable, scroll cues and explicit original/interpreted mode. Never imply that hidden columns or visible rows alter analytical scope.
- Format displayed numerical summaries for reading while making the original exact decimal string accessible and copyable. This is presentation only; no float conversion or recalculation of authoritative source/result values.
- Replace ambiguous category multi-select presentation with accessible selection controls inside the existing permitted values model. Group author mappings by filter and widget/source. Retain explicit mappings, defaults, reader-editable status, authorized bounds and clearly labeled applied filters.

**Risks/functionality to preserve:** accidental client aggregation, numeric precision loss, misrepresenting a truncated plot, changed pie/count eligibility, altered filter scope, layout order drift, hiding an error in a collapsed widget and stale results after revocation. Preserve current request queue/debounce and backend validation. Result-only inspection must never fetch raw dataset rows; displaying a compact source line must use only metadata already authorized by that response.

**Acceptance criteria:**

- Essential chart labels have at least 12 CSS px effective font size after SVG transforms at supported sizes; if this cannot fit, the view changes or deliberately scrolls. Nominal `font-size:14px` alone does not pass.
- A default small widget shows a legible metric/comparison and source/version context without scrolling past method boilerplate. Exact tables and full method are reachable through named controls. The normal overview avoids nested vertical scrolling; an explicit inspection region may scroll.
- Eight-column fixture tables remain navigable at 320/390px without losing identifying context. Hidden-column presentation does not change filters/results or remove access to original cells.
- Each existing chart type/variant covers empty, missing, zero, negative, constant, large-decimal and long-label cases where valid. Limits/omissions are visible. Invalid configurations still receive the existing rejection.
- Dashboard reorder/resize, duplicate/remove, save/discard, mapped filters and reader reset retain their behavior. A widget copied from an analysis remains independent of later original-analysis edits.
- Result-only access, revoked source/result access, dataset suspension and source failure remove unavailable results and offer permitted recovery; no unauthorized table/expand path appears.

**Browser verification:** measure effective SVG text size with transforms and inspect actual screenshots—not just computed font declarations. Review 4/6/12-column widgets and desktop/mobile tables. Drive every chart variant and keyboard-only expansion/filter/layout flow. With the CP6 fixture, confirm mean 51.25, group means A=15/B=87.5 and counts A=4/B=5, including filter/reset behavior. Repeat permission/revocation/suspension checks with separate test accounts on the real test backend.

**Review gate:** accept the complete result-reading and dashboard view/edit experience before rebuilding input workflows.

## Phase 3 — Guided import and useful dataset handoff

**Routes/components:** `/donnees/importer`, `/donnees/imports/:id`, dataset version-add flow and resulting overview/data/analysis entry. Main files: `features/datasets/import.tsx`, `shared.tsx`, relevant `pages.tsx` views and dataset styling. Keep current API modules/contracts.

**Problems addressed:** static steps above one expanded form; configuration, all column definitions and metadata compete; validation issues are remote from corrective controls; publication lacks a focused handoff into useful work.

**Proposed improvements:** make File → Interpret/preview → Describe → Validate/publish actual navigable stages. Maintain a compact file/row/column/configuration summary. Keep the preview close to interpretation choices; provide searchable/grouped column configuration for up to 100 columns without exposing 100 expanded editors. Explain inference versus explicit choices. Surface structure/type errors by line and column with a focused error summary, correction route and full existing report. Final review states whether this creates a private dataset or appends an immutable version. After publication offer Explore this version / Analyze this version.

**Risks/functionality to preserve:** accidentally validating only the sample, applying outdated validation after a configuration edit, resetting user-selected types, changing source identifiers, double publication and losing a receipt after navigation. Maintain current preview/validate revision progression, full-file validation, one-hour receipt expiry, atomic publication, bounded reports, server limits and original-cell retention. Back/Next alone must not publish or mutate an existing dataset. Existing-version metadata stays unchanged as the contract requires.

**Acceptance criteria:**

- Exactly one main next action per stage, a meaningful current/completed indicator and usable Back/edit paths. Returning preserves eligible work under Phase 1.
- Preview remains explicitly a sample; full-file validation is required before publication. Any relevant configuration change invalidates the former validation state.
- Invalid structure and invalid numeric fixtures block publication with a useful route to correction; no partial dataset/version appears. Cancel and expiry clearly explain what is retained or lost.
- CP6 v1 imports as nine rows; `001` remains text, 0 remains present, blank price remains missing, dates retain declared interpretation.
- Adding v2 yields ten rows in the same dataset without altering v1. A repeated/uncertain publication uses existing receipt verification instead of creating an extra version.
- The post-publication analytical entry contains the actual published immutable version ID.

**Browser verification:** run new-dataset and add-version journeys at desktop/mobile, including keyboard error-summary navigation, Back, reload, expiry, changed settings after validation, malformed files, interrupted publication and cancel. Test existing supported encodings/delimiters/date/boolean conventions and boundary-sized synthetic files; preserve limits rather than increasing them. Confirm actual versions/rows on the real test backend.

**Review gate:** accept import-to-published-version and its handoff; do not begin analysis restructuring until this journey passes.

## Phase 4 — Analytical workspace from question to saved result

**Routes/components:** `/analyses`, `/analyses/nouvelle`, `/analyses/:id`, dataset analysis entry, shared-analysis reading/copy and add-to-dashboard handoff. Main files: `features/analytics/pages.tsx`, `controls.tsx`, `shared.tsx`, result integration and analytics CSS; use the established Phase 1/2 helpers.

**Problems addressed:** 37-control baseline, long distances between configuration/result/save, late templates, confusing optional settings and cognitively heavy advanced comparisons.

**Proposed improvements:** present a stable source/version summary, then a template or custom question, then only the required measure/group/visualization decisions. Show results next to setup where width permits, or as a distinct result stage on narrow screens. Preserve configuration when switching stages. Put optional filters, additional measures, ranking and styling behind named advanced disclosure. Keep Calculate and Save explicit, with a persistent contextual action area that never obscures focused content. Reopening shows saved settings and a clear action to calculate; it must not imply stored result snapshots. Provide a deliberate comparison composition with two labeled sources and a mapping review; distinguish statistical correspondences from unique row keys. All four advanced analysis kinds have their own explanatory result structure.

**Risks/functionality to preserve:** hidden settings changing meaning, invalid type defaults, accidentally selecting the latest version, implying therapeutic comparisons, rerunning on every keystroke, incorrect dirty state and turning a recommendation into an automatic saved analysis. Preserve existing algorithm/version, exact arithmetic, source filters, constraints, calculation limits, explicit source switches, IQR conventions, comparison semantics and existing save/dependency behavior. A schema-valid setting is not automatically an analytically valid chart; server rejection stays authoritative.

**Acceptance criteria:**

- The simple mean-by-group journey needs no advanced styling/filter disclosure and ends at a readable result with a nearby explicit save action. All 13 aggregate operations, supported chart kinds, grouping/ranking and settings remain reachable.
- Changing configuration removes/marks obsolete results correctly. Stale or failed calculations never appear as the new result. Busy operations lock conflicting actions without trapping navigation recovery.
- Saved v1 mean remains 51.25 after publishing v2; explicitly selecting v2 gives mean 45. Source/version references are inspectable before calculation and saving.
- Missingness remains 1/9 for v1; type-7 IQR flags only price 200 with Q1=17.5/Q3=52.5 and fences -35/105. Recommendations remain editable definitions. Comparisons retain explicit mappings/keys and give 1 added, 0 removed, 2 changed, 7 unchanged for the fixture.
- Count pie remains B=5/A=4; sum/mean pies remain rejected. Existing histogram, scatter, temporal/KPI checks remain correct. Large decimals stay exact behind readable labels.
- Result-only readers cannot edit source definitions or inspect original rows without dataset permission. Copies and add-to-dashboard use current contract/permission behavior.

**Browser verification:** replay the CP6 known-result journey, exercise every analysis kind and saved/reopened state, test missing/incompatible columns and duplicate/incomplete comparison keys, failure/retry/conflict, and keyboard access to advanced sections. Compare decoded API definition payloads with the baseline; exclude volatile IDs/tokens and never retain credentials. Use real-backend numeric checks as distinct evidence from UI mock fixtures.

**Review gate:** accept the full new import → explore → analyze → save → dashboard path, including advanced analysis, before changing global navigation.

## Phase 5 — Navigation, workspace and resource administration

**Routes/components:** `/`, `/espace`, `/connexion`, `/inscription`, `/profil`, dataset/analysis/dashboard lists and resource lifecycle/sharing panels, `/administration` sections. Main files: `app/App.tsx`, `features/accounts/pages.tsx` and context, `sharing/panel.tsx`, `admin/pages.tsx`, feature list/metadata/lifecycle views and platform/admin styles.

**Problems addressed:** absent global location, wrapping mobile header, generic feature panels, fragmented confirmations, remote sharing context, technical administration filters and weak route announcements.

**Proposed improvements:**

- Use compact persistent desktop primary navigation for datasets, analyses and dashboards, with account/admin utilities separated and an explicit assistant entry. On phones use a clearly labeled menu with current section and predictable close/focus behavior rather than several rows of links. Keep normal browser/deep-link behavior.
- Add route-specific document titles, `aria-current`, breadcrumbs where resource context helps, and deliberate focus on route transitions/error summaries. Distinguish local-view changes from full navigation to avoid excessive focus jumps.
- Make the signed-in workspace a route to existing authorized saved work and import—not a decorative KPI dashboard. Use existing list responses; do not invent global cross-resource search, recent-history endpoints or permanent patient history.
- Present owned/shared/access states clearly in lists and resource headers. Keep lifecycle actions in predictable management areas, with clear archive/suspend/revoke/delete distinctions.
- Retain exact-email sharing and revision-specific authorization review, but organize it around who can see what, sources and consequences. No autocomplete account directory or new privilege checks are invented. Uncertain copy permissions receive honest explanation and existing server validation.
- Rework administration around named users/resources and recent activity, with UUID and advanced filters disclosed. Keep content inspection behind its explicit reason/confirmation, and render suspension/access outcomes consistently.
- Clarify the introduction's two paths using an honestly labeled synthetic CSV-to-analysis example. Keep auth/profile forms concise, accessible and connected to the intended protected destination.

**Risks/functionality to preserve:** route/query loss, failed login return, focus traps, CSRF/logout regressions, exposing unauthorized names/content, inaccessible mobile menus and accidentally conflating management states. A capability-aware UI is supplementary to server authorization. Do not add help/search functionality that requires unsupported backend capabilities.

**Acceptance criteria:**

- Every route retains its existing path and refresh/deep-link behavior; supported source/version/query context survives login.
- Current section is visually and programmatically clear at 320px through desktop. All destinations remain keyboard accessible without a multi-row default mobile header.
- Visitor/analyst/admin and owner/dataset-recipient/result-recipient presentations are appropriate. Direct unauthorized URLs remain denied by the backend.
- Account/profile/password/logout and guarded navigation work together; password changes preserve session-invalidating behavior.
- Grant/revoke, onward authorization after revision changes, permission-aware copy, suspension/restoration and archive/dependency deletion preserve current outcomes. Restoring a dataset does not restore a revoked reader.
- Admin content is not requested merely by opening metadata supervision; logged inspection and last-admin protections remain intact.

**Browser verification:** test direct URLs, refresh, history/back, login redirects, query persistence and mobile menu focus. Use isolated owner/dataset-recipient/result-recipient/admin accounts. Reproduce result-only sharing → raw-row denial → revocation and owner suspension/restoration, confirming both UI and real backend denials. Review a screen-reader route transition and menu once the relevant assistive tool is available; disclose any unavailable verification.

**Review gate:** accept role-aware navigation and management flows, then begin the assistant redesign.

## Phase 6 — Recompose the pharmacy assistant around trustworthy answers

**Routes/components:** `/assistant`; `features/chat/components/chat.tsx`, `chat/state/conversation.ts` presentation integration, `features/results/components/` medication/pharmacy/clarification/sources, presentation formatting and assistant CSS. Preserve conversation/service logic unless a separately reviewed UI integration is necessary.

**Problems addressed:** decorative welcome receives more emphasis than the eventual factual answer; small package/provenance text; hidden mobile invalid-length feedback; inconsistent comfort/focus and dense recovery details.

**Proposed improvements:** shorten the introduction and move useful examples nearer the composer. Preserve an inviting first-use explanation without dominating the screen. Establish a result hierarchy of medication name/strength/form/presentation, recorded price/package total, observation date/source and clear stock/coverage limitations. Render candidate differences as a readable choice list. Use the same typography/control/state system as the platform while retaining a conversation-centered layout. Keep source differences and full provenance inspectable. Place the price date next to its recorded-price label; do not imply source freshness beyond supplied facts. Improve loading, cooldown, uncertain outcome, retry/edit, expiry and reset presentation. Keep length correction visible and announced at every breakpoint. Avoid automatic mobile focus that summons an unwanted keyboard until verified on a real device.

**Risks/functionality to preserve:** accidental answer rewriting, hiding ambiguity/unknown prices, loss of Arabic directionality, focus stealing during response announcements, retry duplicates, restoring expired state, permanent transcript storage and misleading availability claims. Preserve backend amounts, reviewed matching and explicit choices, raw source dates/conflicts, temporary conversation token model, no POST replay and no provider fallback. French chrome stays French; automatic message direction is not represented as complete Arabic localization.

**Acceptance criteria:**

- Essential identity/package/date/source/limitation text is at least the approved readable supporting scale (proposed minimum 14 CSS px); no essential qualifier depends on 10px microtype or hover alone. Price context remains visible rather than buried entirely in details.
- A user can distinguish presentations before selection and identify the price's package and observation date after it. Unknown dates/prices and partial Rabat coverage stay explicit.
- Pasting 2,001 characters keeps the draft, explains how to correct it, announces invalidity and disables sending until valid; valid input, IME composition, Enter/Shift+Enter and mixed/Arabic text retain current behavior.
- Source disclosure, phone links, long names, missing facts, multiple medication results and complete-package totals work on phones and desktop. No client price arithmetic or invented facts appear.
- Loading/error/cooldown/expiry/storage-blocked/reset-failure and outcome-unknown states offer truthful next actions. Reset clears only after server success/expiry; failed questions remain editable; refresh never repeats or renews a question.
- Composer remains visible without covering the active result/focused controls, including a real mobile keyboard. Main controls target 44×44 CSS px where practicable; this is a usability target, not a blanket WCAG threshold claim.

**Browser verification:** deterministic intercepted conversations for every named state, followed by authorized existing test-backend/mocked-provider conversation checks without hosted inference. Inspect focus, polite announcements, reduced motion, source disclosure, keyboard reset/cancel, long/RTL content, virtual keyboard/viewport changes and tab refresh/expiry. Use only test catalogue fixtures; do not treat their prices as newly verified observations.

**Review gate:** accept the full assistant composition and state matrix before the final cross-application review.

## Phase 7 — Final consistency, accessibility and integrated acceptance

**Routes/components:** all routed screens, shared tokens/components and their uses, including public/auth/profile/admin/shared resources and assistant states. Documentation includes the approved implemented DESIGN.md and `.impeccable/design.json`; retain an explicit reference to the previous baseline.

**Problems addressed:** progressive phases can leave duplicate styling, inconsistent disclosure/focus/error patterns or regressions where new shells and old feature code meet. Earlier critique did not verify screen readers, real touch keyboard behavior or all protected workflows.

**Proposed improvements:** finish common action hierarchy, typography, density, spacing, alignment, responsive navigation, semantic state colors, focus and motion. Remove obsolete styles/components only after confirming no remaining consumers. Audit meaningful field boundaries, readable numeric text, error summaries and scroll affordances. Keep essential disclosure context visible. Update design documentation to match the approved implementation rather than describing an imagined ideal.

**Risks/functionality to preserve:** global CSS cascades, React/Radix behavior changes, imports/code splitting, keyboard traps, forgotten read-only states and an aesthetic cleanup becoming a domain refactor. No broad test snapshot replacement to conceal regressions. Preserve untouched data/history and all contracts.

**Acceptance criteria:**

- No unresolved P0/P1 in implemented scope without explicit user disposition; previous draft-loss/chart-overload cases pass. P2 exceptions have named rationale and owner-approved follow-up scope.
- Keyboard-only primary workflows, route/menu/dialog focus, semantic headings, labels, live status and error recovery pass. Run a real screen-reader smoke review where available; unavailable coverage remains an explicit limitation.
- Normal text meets the agreed contrast target, meaningful control cues are distinguishable, and focus is visible. Use WCAG 2.2 AA as the proposed technical target, not a certification claim. Review manual exceptions/context, not automated counts alone.
- At 320/390/768/1024/1440px and a wide desktop, content is readable, controls remain reachable and there is no accidental page overflow. Allow deliberate two-dimensional table/chart inspection. Check browser zoom/text enlargement, reduced motion and mobile keyboard behavior.
- Existing functional/security suites and the numeric/permission matrix below pass in their proper environments. No new accessibility violations in affected routes/states; axe is a partial check, not the entire gate.
- Final evidence matches the built/served source under review. Re-score the two products separately using the same Nielsen framework; score improvement supports, but never replaces, task-based acceptance.

**Browser verification:** replay the complete synthetic CP6 journey and a separate real authenticated test-backend run, including error/permission cases; inspect before/after captures at identical viewports/content. Review all chart types and advanced features, two accounts with different access and administration boundaries. Capture source/version/request-definition assertions and exact outcomes without secrets. Complete a fresh independent design review of the finished implementation when authorized, resolve its material findings, then present the final user review packet.

**Review gate:** user accepts the completed application. Publishing/deployment remains a separately authorized action.

## 5. Shared acceptance data and invariants

Use [existing CP6 fixture documentation](apps/web/tests/fixtures/functional-review/README.md), its v1/v2 CSVs, invalid fixtures and existing browser regressions rather than inventing replacement oracles.

| Test | Expected preserved outcome |
| --- | --- |
| v1 import | 9 rows / 8 columns; 8 present prices, 1 missing; text identifiers keep zeros. |
| v1 price statistics | Sum 410, mean 51.25, minimum 0, maximum 200. |
| Grouped v1 | A: 4 rows, sum 60, mean 15. B: 5 rows, sum 350, mean 87.5. |
| Missingness / IQR | Price missing 1/9; Q1 17.5, Q3 52.5, IQR 35; only 200 flagged at factor 1.5. |
| Charts | Count pie B=5/A=4; invalid sum-based pie still rejected; histogram bins 5/2/0/1; scatter quantity/price has 8 valid pairs, 1 missing pair. Temporal means Jan=15/Feb=87.5. |
| v2 and pinning | 10 rows, mean 45, sum 450, no missing prices; saved v1 remains 51.25. |
| Explicit keyed comparison | 1 added / 0 removed / 2 changed / 7 unchanged. |
| Dashboard filter | A gives mean 15/count 4; B gives 87.5/count 5; reset preserves authorized perimeter and original v1 results. |
| Result-only recipient | May read permitted results/filter scopes; cannot explore raw rows without a separate dataset grant. |
| Revocation / suspension | Subsequent requests lose unauthorized results; restoration restores only still-valid access, not revoked grants. |
| Invalid import / uncertain mutation | No partial/duplicate publication; existing receipt/revision rules remain authoritative. |

Add boundary cases around these stable oracles: empty selections, absent prices, zero/false/text-empty, negative/large decimals, long labels, incompatible fields, maximum permitted rows/columns/widgets, duplicate keys, owner changes in session and unavailable sources. No analyst skill level, clinical use or customer behavior is assumed from the fixtures.

## 6. Verification and operational discipline

- Each phase gets focused behavior tests for its material risks plus relevant existing suites. Build and lint when frontend code changes. Do not create tests that merely mirror CSS; assert task outcomes, accessible interactions, retained values, source/version identity and authorization outcomes.
- Existing commands include `npm run build`, `npm run lint`, `npm test`, and the dedicated `test:accounts`, `test:datasets`, `test:analytics`, `test:dashboards`, `test:administration` suites. Select only suites whose lifecycle respects the current authorization; real suites are not implicitly safe to run.
- Several Playwright configurations automatically start Vite, and real suites start temporary Express processes/create test databases. Do not assume `npm test` or `DEPLOYMENT_ORIGIN` makes every suite read-only. Review the chosen configuration and lifecycle before running it. Do not start or stop backend services or containers. Frontend-only Vite/build and browser tests with locally intercepted APIs are permitted; they must not start backend/database lifecycles or hosted inference. If an authorized real test backend is unavailable, report that gate as unverified.
- Synthetic interceptions are for deterministic UI/recovery states. Real calculation/authentication/permission assertions need an authorized real test backend and separate isolated test resources. Never use private normal resources as disposable fixtures or ask for passwords in chat. The user can sign into a test browser locally.
- Protect credentials and test data in recordings: no credential-bearing traces, expanded environment/configuration dumps or screenshots of secrets. Do not run hosted inference for design verification.
- Keep evidence under `artifacts/redesign/phase-N/`, labeled with source/build identity, viewport, role, fixture, state and whether responses were real or synthetic. Preserve the original critique evidence. Inspect every delivered screenshot at useful scale; full-page thumbnails alone cannot prove chart readability.
- At each gate provide: work completed, routes affected, before/after, acceptance checklist, test results, exact unresolved issues, scope limitations and rollback path. Keep phases as separate reviewable diffs; Git commits remain user-controlled. Revert a UI phase through its diff without changing data, migrations or saved source definitions.

## 7. Decisions reserved for review

1. The major-redesign exploration, warning-only/no-persistence policy and Phase 0–7 order are the user's final decisions. Phase 0 is accepted and closed; Phase 1 alone is authorized for production implementation.
2. Direction B — Traverse plus V2 is approved. Skip further prototypes and integrate its refinements during the relevant phases. The unsaved-change policy is already decided; review its specification for fidelity rather than reopening persisted-draft alternatives. Do not infer visual approval from the incumbent DESIGN.md.
3. Accept each phase's outcome before the next starts. This includes explicit treatment of unverified real-device/screen-reader or real-backend cases, rather than treating synthetic evidence as equivalent.

Optional new business capabilities—new import formats, public dashboards, server-side draft synchronization, additional analytics, permanent chat history and broader localization—remain outside this redesign. A polished outcome must improve the existing product's usability while retaining its correctness and trust boundaries.
