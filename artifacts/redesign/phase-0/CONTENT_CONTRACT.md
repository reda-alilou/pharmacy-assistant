# Phase 0 composition contract — proposals only

All alternatives use the same content. They are isolated, local static prototypes, without API calls, dependencies, remote assets, storage or real saving. Application code and baseline DESIGN.md must not change.

## Data and surfaces

Use `apps/web/tests/fixtures/functional-review/cp6-v1.csv` and its README. Label the source **TEST CP6 · Observations synthétiques**, file `cp6-v1.csv`, version 1, 9 rows, 8 columns, source `SYNTHETIC_CP6_REVIEW`. There are 8 present prices and 1 missing; mean51.25, sum410, min0, max200. Group A has4 rows/4 present prices/mean15; B has5 rows/4 present prices/mean87.5. Counts A4/B5. Missing price1/9=11.11%. IQR Q1=17.5 Q3=52.5 lower−35 upper105, only record008 price200 flagged. No clinical conclusions. Source observation dates Jan/Feb2026. Do not label them current market prices.

Each direction must offer views `?view=analysis`, `?view=dashboard`, `?view=assistant` in its standalone HTML file, with readable view navigation and an index link to `index.html`. Keep a slim visible note “Prototype · données de test · aucune action réelle”. Use French UI copy.

### Analysis

Show selected source/version, visible/editable configuration (measure mean, column ppv_price_mad, grouping group, visualization bars), concise scope (9 rows/no filters), a legible grouped bar plot and exact aggregate table: B87.50/4 present/1 missing; A15/4 present/0 missing. A clear Calculate action and explicit Save action, plus useful advanced/method disclosure. Make results the focus, source context persistent. No giant hero number or ornamental metrics. Structural alternatives must differ, not only their theme.

### Dashboard

Show populated, meaningful widgets using the same source: grouped means, group counts, missing price11.11% (1 missing/8 present), optional IQR observation008=200. At least3 widgets with real inspectable numbers. Show editing/inspect/filter affordances. Base view all categories. If a category filter is interactive, update every represented affected statistic correctly or clearly mark it as an interaction specimen rather than pretending calculations ran. Prefer precomputed fixtures, not a new calculation engine. Keep plot labels as HTML or unscaled text≥12px; no tiny900-wide SVG labels. No decorative data.

### Assistant

Read existing `apps/web/tests/fixtures/responses.json` selected medication (ABIP15MG, aripiprazole, boîte de30 comprimés pelliculés, recorded public price372.00MAD, AMMPS observation18Oct2026). Label fixture example, not newly verified information. Make identity/presentation/date/source and “Stock non vérifié” all readable≥14px. Show contextual question and answer, source disclosure, temporary conversation30min, next-question composer, optional alternate presentation20tablets268MAD only when clearly a choice not selected. No new clinical guidance. Source links may be shown in local details but do not fetch them or load remote assets.

## Interactions and accessibility

All local controls should either demonstrate their stated interaction (details, dialogs, navigation, read-only states, preset mocked result) or explicitly announce “Simulation: ... aucune action réelle”. Never fake a save/publication or claim to exercise backend behavior. Use native labels/selects/buttons/dialogs, keyboard focus and escape/cancel. Prototype changes exist in memory only; no storage APIs, fetch, XHR, serviceworkers or network. No persisted drafts. Navigation with changed analysis controls should warn; Stay preserves in-page values, Discard permits leaving. This is a specimen for later implementation, not Phase1 production work.

Desktop1440px and mobile390px required; account for320/768px. Text must wrap without page overflow, tables may deliberately scroll with cues, charts/labels must remain legible, mobile controls generally44px. No gradients or decorative card side stripes, no emojis or fake icons. Use local fonts, optional authored SVG icons/plots only. Responsive composition must be intentional, not a squeezed desktop screenshot.

Produce each direction as `<direction-id>.html` (self-contained CSS/JS, no dependencies) and `<direction-id>-system.json` + `<direction-id>-system.md` with candidate tokens, typography, navigation/layout, components/states/motion/breakpoints. Do not set a winning direction or modify `.impeccable` project settings. Root will render/inspect all three and assemble documents/index.
