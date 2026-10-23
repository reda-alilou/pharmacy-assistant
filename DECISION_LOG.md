# Full Stack CdC — decisions and remaining work

Updated **2026-10-23**. Submission: **2026-10-25**. Demonstration: **Monday 2026-10-26**.

Requirement source: [CdC_Application_Full_Stack.md](CdC_Application_Full_Stack.md).
Implemented baseline: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Previous phase

D001–D020 are preserved byte-for-byte in
[the historical decision log](docs/development/decisions-2026-10-19-20.md).
[R7 evidence](docs/validation/cleanup-r7.md) confirms completion of the architecture
and cleanup phase, including remaining D018 validation. Historical “still open”
wording is not a current backlog. Deliberately deferred features, such as full
Arabic UI localization, were not all implemented.

Existing design and operating constraints remain in force until explicitly
superseded. Preserve source facts/history, service ownership, database volumes,
and the user's control of container lifecycle and Git publication.

## How we use this file

Discuss each entry, then record the user-approved decision, chosen approach,
reason, alternatives and remaining details. Keep decision approval separate from
implementation completion, which requires evidence. Continue IDs after D020.

**D021, D022 and D024–D034 are approved by the user, with remaining details
identified in each entry.** D023 has approved navigation boundaries; Checkpoint
1 route/layout details are resolved below and later screen details remain open. The six implementation checkpoints below are approved.
Approval of the product direction is not evidence of implementation or blanket
approval of every proposed feature design. Routine details can be resolved within
agreed scope.
Update this file as choices are made; do not mark proposals approved because of
the deadline. PROJECT_CONTEXT remains a description of implemented behavior.

**User constraint (2026-10-23):** Do not skip important requirements or excessively
simplify functionality in the name of limited time. Cover every mandatory CdC
requirement with working behavior and verification. Choose simpler designs when
they are appropriate, not merely because of deadline pressure. Optional features
remain choices to discuss, rather than automatically included or excluded.

## Baseline and coverage

The assistant baseline includes React/TypeScript, Hooks, REST APIs, PostgreSQL,
Docker, provenance, multilingual extraction and temporary conversations. Checkpoint
1 implements React Router, Express and accounts. The user authorized continuation
after its isolated acceptance; Checkpoint 2 now implements private CSV datasets,
immutable versions and exploration. The user authorized Checkpoint 3 after the
rebuilt-image results. Analytics calculations, four advanced features, charts and
private saved definitions now pass final host/browser and isolated production
checks. All 16 full-stack checks and 18 assistant PostgreSQL tests pass. Dashboards, sharing and
administration remain future work. All 14
Checkpoint 2 container checks pass, including the follow-up metadata-save fix
verified after rebuilding web. Normal-volume upgrade and checkpoint
review are tracked separately below.
The previous requirements audit concerns Challenge 1, not this CdC.

| ID | Topic | CdC sections | Implementation status |
| --- | --- | --- | --- |
| D021 | Product scope | 1–2 | Accounts, CSV/exploration and analytics implemented; dashboard/sharing workflow future |
| D022 | Express backend | 11 | Accounts, datasets and analytics implemented; dashboard/sharing/admin APIs future |
| D023 | Navigation and screens | 3, 11 | Accounts/datasets/analyses/charts/separate assistant implemented |
| D024 | Accounts, roles and security | 3, 12 | Implemented and locally verified for Checkpoint 1 |
| D025 | Dataset management and CSV | 4 | Implemented and verified; user authorized continuation after rebuilt-image checks |
| D026 | Exploration and profiling | 5 | Table, typed filters, profiles and versions implemented; Analysis view is Checkpoint 3 |
| D027 | Analysis and indicators | 6 | Implemented and verified in host/browser and production-image checks |
| D028 | Charts and dashboard builder | 7 | Analysis charts implemented; dashboard builder remains Checkpoint 4 |
| D029 | Saved analyses and sharing | 8 | Private version-pinned definitions implemented; sharing remains Checkpoint 4 |
| D030 | Four advanced data features | 9 | All four implemented and verified in host/browser and production-image checks |
| D031 | Administration | 10 | Account CLI/activity/safeguards only; administration UI future |
| D032 | Platform persistence and setup | 11–13 | Accounts/datasets/analyses, explicit migrations/grants and verified backup/restore implemented |
| D033 | Validation and demo | 12, 14 | Account/dataset/analytics/API/browser evidence; full workflow future |
| D034 | Submission deliverables | 13–14 | Checkpoint 1–3 API/setup/evidence and attributed CSV added; final delivery future |

## D021 — Pharmaceutical analytics product scope

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Accounts, private CSV lifecycle/exploration, analytics
  and private saved definitions implemented. Dashboard/sharing/admin workflows
  remain later checkpoints. Checkpoint 3 host and isolated production checks pass.
- **Requirement:** Import → exploration → analysis → visualization → sharing.
- **Decision:** Extend the project into a pharmaceutical data-analysis
  platform; retain the assistant as an additional feature.
- **Reason:** Reuse the catalogue and provenance while serving the analyst workflow.
- **Still open:** Product name, precise analyst personas, integration details and
  feature designs. Retaining the assistant and covering the complete mandatory
  CdC workflow are agreed, not open scope questions.
- **Acceptance:** Complete the workflow with a newly uploaded CSV. Keep recorded
  prices explicitly dated; make no clinical or live-stock claims.

## D022 — Node.js and Express backend

- **Date / decision status:** 2026-10-23 / Finalized by the user; implementation
  details listed below remain open. Node/Express are imposed by §11.
- **Implementation status:** Express accounts/datasets implemented and verified in
  host/isolated image checks. Analytics/saved configurations now pass both host and
  final image checks. Dashboard/sharing/admin APIs remain future.
- **Decision:** Use React, Node.js/Express and PostgreSQL for the analytics platform.
  Express owns accounts, datasets, analytics, dashboards, sharing and administration.
  Keep the existing Python services backing the additional assistant screen.
- **Architecture:** One React application with React Router, served through Nginx.
  The gateway routes analytics requests to Express and assistant requests to the
  existing FastAPI core, which retains its language-service connection.
  Use TypeScript for Express, with runtime request/response validation.
  Keep the monorepo; the new service owns its package, dependencies, migrations,
  tests and Docker image.
- **Reason:** An Express proxy alone would not demonstrate the required backend.
- **Checkpoint 1 details resolved:** `pg` with parameterized SQL, transactional
  checksummed owned SQL migrations; `/platform-api` to Express, unchanged `/api`
  to core. Zod validates account and dataset contracts; CSV uses bounded raw
  upload followed by validated JSON configuration. Later domain contracts remain
  to implement. The user has approved auxiliary Python
  services; this does not claim that an instructor has independently confirmed
  mixed-backend acceptability.
- **Relationship:** Extends the platform scope of D002, D004 and D014; existing
  Python services and ownership remain intact pending detailed integration design.
- **Acceptance:** Analyst operations use a real Express API with validation,
  consistent errors and explicit service boundaries.

## D023 — React Router and platform navigation

- **Date / decision status:** 2026-10-23 / Single React application, React Router
  and separate analytics/assistant areas approved; detailed screen design open.
- **Implementation status:** Router/accounts/separate assistant and Checkpoint 2
  dataset/import/exploration screens implemented and browser-verified. Checkpoint 3
  adds analysis/chart/saved-configuration routes; dashboard/admin remain future.
- **Proposed approach:** Reuse React/TypeScript/Vite and existing UI controls. Add
  introduction, login/register, datasets, exploration, dashboards, profile and
  administration routes; place the assistant on its own screen.
- **Reason:** Extend the existing frontend into the required multi-screen workspace.
- **Approved boundary:** Keep the assistant on a separate screen accessible to
  visitors and authenticated users. Account registration does not create permanent
  patient history; existing temporary conversations remain separate.
- **Checkpoint 1 details resolved:** French introduction `/`, `/inscription`,
  `/connexion`, `/espace`, `/profil`, visitor `/assistant`; role-guarded
  `/administration` explicitly labels its future workflow. Checkpoint 2 adds
  `/donnees`, `/donnees/importer`, resumable `/donnees/imports/:id` and
  `/donnees/:id` with overview/data/columns/quality/versions views. Checkpoint 3
  adds `/analyses`, `/analyses/nouvelle`, `/analyses/:id` and a dataset Analysis
  tab; protected source/version URLs retain their query through login. Dashboard
  routes are future work. The calm solid-color layout
  preserves assistant content and uses responsive, accessible forms.
- **Acceptance:** Direct URLs, refresh, loading, empty/error states and responsive
  navigation work. Preserve French labels and no gradients/card side strips unless
  explicitly changed. UI route guards do not replace backend authorization.

## D024 — Accounts, profiles, roles and security

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Registration/login/logout, own-profile/name/password editing, secure hashes, PostgreSQL sessions, CSRF, throttling and backend guards implemented and verified. Isolated container acceptance passed; normal-volume upgrade and review remain user-run steps.
- **Requirement:** Visitor, analyst and administrator access; registration,
  authentication, profile management and protected functionality.
- **Decision:** Persistent accounts, secure password hashing, basic profile editing,
  backend role/ownership checks and server-managed sessions. Store an opaque session
  identifier in an HttpOnly cookie and session records in PostgreSQL. Enforce expiry,
  logout invalidation, CSRF protection for state-changing operations, login throttling
  and consistent authentication errors. Disabling an account invalidates its sessions.
  Provision administrators explicitly; public registration creates analysts only.
- **Permissions:** Visitors can view the introduction, register/login and use the
  assistant. Analysts can edit their own profiles, manage their own datasets, analyze,
  build/save dashboards and access explicitly shared resources. Administrators also
  have those capabilities plus account management and platform supervision.
- **Reason:** Support meaningful logout and account suspension without storing
  authentication tokens in browser JavaScript storage.
- **Checkpoint 1 details resolved:** Node scrypt (N=131072/r=8/p=1), random salted
  versioned hashes; 30-minute request inactivity / 12-hour absolute sessions;
  HttpOnly SameSite=Lax scoped cookie, Secure for HTTPS and explicit loopback-only
  HTTP exception; exact-Origin plus session-bound CSRF; PostgreSQL throttle counters.
  Editable displayed name and current-password-protected password changes; login
  email remains unchanged. Explicit hidden-password CLI creates new admins only.
  Role/status/password changes invalidate sessions; last-active-admin protection
  is transactional. See the [API/security contract](docs/architecture/platform-api.md).
- **Acceptance:** Direct API requests cannot bypass ownership or admin permissions;
  credentials are not exposed; validation and errors are clear. Protect login and
  upload endpoints appropriately. Conversation bearers are not account sessions.

## D025 — Dataset management and CSV import

- **Date / decision status:** 2026-10-23 / Finalized by the user; CSV is mandatory.
- **Implementation status:** Implemented in Checkpoint 2: guided preview/configuration,
  full validation/report, atomic publication, metadata editing, private immutable
  versions, archive/restore and dependency-reviewed deletion. Host database/browser
  and production-image checks passed, including follow-up metadata-save protection
  in the rebuilt web image; user review remains pending.
- **Decision:** Owned datasets with title, description, category and source;
  listing, upload preview/import, metadata editing and deletion.
- **Import flow:** Select file → preview/configure → describe → validate/import.
  Detect comma, semicolon or tab separators and allow correction. Show headers and
  sample rows; infer types and permit corrections. Include optional source
  observation date alongside dataset metadata.
- **Types:** Text, integer, decimal, boolean, date and date/time. Preserve identifiers
  as text where needed to retain leading zeros. Preserve original cell text alongside
  interpreted values where needed for traceability.
- **Validation:** Configurable missing markers; do not automatically interpret every
  NA string as missing. Distinguish missingness from zero, false and empty-looking
  textual values. Let users specify decimal/date conventions rather than silently
  guessing ambiguous values. Report row, column and reason for invalid values.
  Never silently drop malformed rows or turn invalid numbers into missing values.
  Users can correct configuration or download a validation report to fix the source.
  Imports are atomic: failed imports do not expose partially usable datasets.
- **Reason:** Fixed administrative JSONL imports do not meet this user workflow.
- **Approved ownership/versioning:** Each dataset has one owner and is private by
  default. Each successful import creates an immutable dataset version; metadata
  remains editable. Replacing a CSV creates a new version. Saved analyses pin a
  version; switching versions requires column/configuration validation. Deletion
  must identify dependent analyses and shared access before proceeding.
- **Checkpoint 2 details resolved:** Pinned `csv-parse`; UTF-8 (fatal decoding) and
  explicit Windows-1252; 10 MiB, 25,000 rows, 100 columns, 1,000,000 cells, 16,384
  UTF-16 units per cell. Preview 20 rows, inference 200 rows with full-file leading
  zero protection; complete-file validation before publication. Decimal precision
  is 38 significant/12 fractional digits; ISO timestamps retain six fractional
  digits. Report counts all errors and retains the first 1,000. Staging expires
  after one hour; five active uploads/account; one heavy CSV operation/process.
  Benchmarks cover all 9,936 source records and larger fixtures. Dependency
  registry/FKs block deletion until future analyses/shares are removed or migrated;
  analysis management is now implemented in Checkpoint 3, sharing remains later.
  [Contract](docs/architecture/datasets-api.md).
- **Acceptance:** A fresh CSV persists and can be explored; empty/malformed files
  and invalid headers receive clear errors. Missing values remain distinct from zero.
- **Optional:** Excel, JSON and external API imports are not necessary for the MVP.

## D026 — Exploration and dataset characteristics

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Overview, Data, Columns, Quality and Versions implemented
  and verified in Checkpoint 2. Checkpoint 3 now adds the analytical builder and
  advanced features; the dataset Quality view retains its initial import profile.
- **Decision:** Paginated table, search, typed filters, sorting, row/column
  counts, inferred types and missing-value summaries.
- **Workspace views:** Overview (metadata, owner, source, version and import summary);
  Data (table); Columns (types, missing/distinct counts and descriptive statistics);
  Analysis (aggregations/grouping/chart creation); Quality (missingness/issues);
  Versions (import history and previous versions).
- **Filters:** Text contains/equals/starts-with/selected values; numeric equality,
  comparisons and ranges; dates before/after/between; boolean true/false; and
  missing/present for all types. Combine filters with AND and selected values
  within one filter with OR. Show active filters and clear-all.
  Backend search, filters and sorting apply to the full dataset, not the current page.
- **Reason:** Make supported uploads inspectable through the application.
- **Checkpoint 2 details resolved:** Parameterized full-version queries; count/page
  share a repeatable-read snapshot; 25 rows/page by default, maximum 100; stable
  typed sort with nulls last. Active filters and clear-all are visible. Immutable
  profiles include present/missing/distinct counts, typed min/max and PostgreSQL
  numeric average, excluding missing cells. Original strings remain inspectable.
  [Query and profiling conventions](docs/architecture/datasets-api.md).
- **Acceptance:** Counts agree with filters, numbers sort numerically and large
  permitted uploads do not render every row at once.

## D027 — Analysis and domain indicators

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Checkpoint 3 implements aggregations, typed grouping,
  pharmaceutical templates, explicit version/filter/algorithm settings and private
  saved definitions. Final host database/browser/regression and production-image
  checks pass; user review and normal-volume upgrade remain separate.
- **Decision:** Select dataset version, filters, measure/aggregation, optional
  grouping columns, sorting, top/bottom limit and visualization.
- **Operations:** General row/present/missing/distinct counts; numeric sum, mean,
  median, min/max, quartiles and standard deviation; categorical frequencies,
  percentage distributions and rankings; date/time grouping by day, month or year
  for counts and numeric aggregates.
- **Interpretation:** Display version, active filters, units and missing-value
  treatment. Show the number of contributing nonmissing observations for statistics
  such as average price. Pharmaceutical templates include presentations by form,
  missing-price rates, price distributions and source disagreements where fields
  exist. Templates use the same engine as user-created analyses.
- **Reproducibility:** Persist version, filters, aggregation definitions and relevant
  algorithm settings. Never silently substitute a newer dataset or changed thresholds.
- **Reason:** Package-price calculations alone are not an analytics workspace.
- **Checkpoint 3 details resolved:** Parameterized full-version PostgreSQL numeric
  aggregation, at most 8 measures/2 grouping columns/200 returned groups, with
  full-group totals and explicit omissions. Quartiles use exact numeric type-7
  interpolation; mean/deviation inputs use numeric(80,24) to avoid rounding away
  small differences at large magnitudes. Both sample (n−1) and population (n)
  deviation are explicit; missing cells are excluded and denominators shown.
  Temporal grouping uses canonical UTC dates, with no invented observations.
  [Complete conventions/API](docs/architecture/analytics-api.md).
- **Acceptance:** Known-input checks verify results, filters and missing values;
  incompatible operations are rejected. Cross-product price averages are descriptive
  statistics, not therapeutic-value comparisons. Do not invent time series from a
  single snapshot; the CdC's example analyses are not all individually mandatory.

## D028 — Visualizations and dashboard construction

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Checkpoint 3 analysis charts support KPI, bar, temporal
  line, histogram, pie and scatter with editable labels/units/precision and exact
  table alternatives. Dashboard widgets/layout/filter mapping remain Checkpoint 4.
- **Decision:** Dashboards have a title, description and configurable widgets.
  Start empty or add visualizations from existing analyses. Support KPI cards,
  bar charts (including horizontal rankings), date/time line charts, configurable
  histograms, pie/donut charts for manageable category counts, scatter plots and
  grouped summary tables. Scatter plots do not imply causation.
- **Widget configuration:** Retain dataset version, measure, grouping, filters and
  visualization settings. Rename, edit, duplicate and delete widgets; preview
  configuration changes. Offer axis labels, units, sorting, legend visibility,
  numeric precision and category limits. Explain Other groupings and omissions.
- **Layout:** Responsive grid with drag-and-drop arrangement and resizing on larger
  screens, keyboard-accessible move controls and explicit width choices. Small
  screens use a predictable single-column reading order. Separate view/edit modes.
- **Saving:** Explicit Save changes, unsaved-change indicator and warning before
  leaving with unsaved edits. Reader filter adjustments never overwrite the owner's
  saved configuration.
- **Filters:** Date ranges, categories, numeric ranges and missing/present. Explicitly
  map each filter to affected widgets and columns; do not infer cross-dataset
  equivalence from matching names. Show active filters, reset and affected widgets.
- **Result states:** Show per-widget loading, empty/error states, dataset version
  and source. Use consistent filter semantics. Failed calculations must not leave
  old values appearing current.
- **Reason:** Provide capable, accessible dashboard editing and understandable
  interaction while preserving reproducible configurations and source meaning.
- **Still open:** Chart/grid libraries, detailed layout and configuration contracts.
- **Acceptance:** Verify widget editing and persistence, filter mappings, responsive
  layout, keyboard operation, units and failure states.

## D029 — Saved analyses and sharing

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Checkpoint 3 private named configurations, immutable
  source references, filters, rules and charts are persisted with revisions and
  real dataset dependency safeguards. Sharing/copy/recipient controls remain
  Checkpoint 4. No save creates a sharing grant.
- **Decision:** Save named configurations with dataset-version references, filters,
  indicators and charts. Private by default; revocable read-only sharing with
  registered accounts. Separate dataset grants from analysis/dashboard grants.
  Dataset recipients can explore and create their own analyses; the dataset owner
  retains editing/deletion control. Dashboard-only recipients see the permitted
  charts, indicators and interactive results, not automatic raw-data browsing or
  downloads. Enforce allowed columns, filters and queries at the API.
- **Collaboration:** No simultaneous editing of shared originals. Recipients use
  their own copies for changes, subject to underlying dataset permissions; a copied
  configuration must not bypass missing or revoked data access.
- **Reason:** Support collaboration without exposing more data than intended,
  while keeping ownership and analysis reproducibility explicit.
- **Sharing controls:** Owners enter an existing account's exact email, select
  dashboard or dataset sharing, review recipients and revoke access. Explain each
  permission plainly; do not expose a searchable directory of all accounts.
  Dashboard owners configure permitted recipient filters. The backend derives
  allowed queries from saved configuration, rejecting arbitrary columns/aggregations.
- **Onward sharing:** Access to somebody else's dataset does not permit distributing
  its results onward. Block sharing of dependent dashboards unless the original
  dataset owner explicitly authorizes it. Copies cannot bypass this boundary.
- **Still open:** Precise query-permission representation, original-owner onward-
  sharing authorization mechanism, copy workflow and deletion handling. Versioning
  follows D025.
- **Acceptance:** Reopen after a new login; recipients can view only the intended
  resources; unauthorized users cannot; revocation is enforced by the API.
- **Optional:** Anonymous public dashboards. Durable patient chat history is not
  required by saved analyst dashboards.

## D030 — Four advanced data features

- **Date / decision status:** 2026-10-23 / Finalized by the user; four selected
  features exceed the CdC minimum of three.
- **Implementation status:** Checkpoint 3 implements all four features, including
  visible rules, affected/flagged-row inspection, editable recommended chart
  definitions and exact optional unique-key comparison. Final host and
  production-image checks pass.
- **Decision:**
  1. Missing-value analysis: completeness by column/group, missingness visualization
     and affected-row inspection. Explain denominators and distinguish source
     missingness from invalid input.
  2. Numeric outlier detection: choose a column and optional comparable groups,
     apply an explained IQR rule and inspect flagged rows. Do not delete or declare
     values incorrect automatically; encourage meaningful grouping for medicine prices.
  3. Chart recommendations: use selected column types/cardinality, explain suitability
     and create a valid editable chart configuration.
  4. Dataset/version comparison: compare schema, row counts, completeness and summary
     statistics. Optional row-level comparison uses user-selected, validated unique
     keys; never silently fuzzy-match medication records.
- **Reason:** Distinct features applicable to uploaded data without hosted inference.
- **Reason for comparison:** Distinguish the pharmaceutical platform through
  provenance-aware analysis and meaningful comparison of successive imports.
- **Other possibilities, not selected:** Quality scoring, geographic analysis
  and correlation.
- **Checkpoint 3 details resolved:** Missingness uses per-group row denominators;
  zero-row rates are undefined. IQR factors 1.5/3, type-7 quartiles, minimum four
  present observations/group, strict outside fences, and explicit zero-IQR behavior.
  Recommendations use filtered types/cardinality and create ordinary editable
  engine definitions. Comparison maps columns explicitly (10 pairs maximum),
  optionally validates up to 3 complete unique key pairs, and rejects duplicates,
  missing keys or implicit text/numeric coercion. Settings persist under cp3-v1.
  [Contract and limits](docs/architecture/analytics-api.md).
- **Acceptance:** Each feature has visible results, explained rules and edge-case
  checks. Outliers are flags, not automatic corrections. Do not rely on counting
  the existing chatbot as a qualifying analytics feature without justification.
- **Verification:** Use manually calculable fixtures and the pharmaceutical sample.
  Cover malformed CSVs, ambiguous dates, decimal conventions, missing values,
  duplicate comparison keys and permission enforcement.

## D031 — Administration and activity

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** No administration workflow/UI yet. Checkpoint 1 includes explicit account provisioning/status/role CLI, account activity and last-active-admin protection as security foundation.
- **Decision:** Four administration sections:
  - Overview: total/active users, datasets/versions, imported rows, saved analyses/
    dashboards, recent imports and failures.
  - Users: search/filter accounts, inspect status, enable/disable accounts and
    manage analyst/admin roles.
  - Datasets: ownership, source, versions, dimensions and import status; explicit,
    logged content inspection.
  - Activity: filter by actor, action, resource, outcome and date.
- **Reason:** Operational CLI commands are not the required administration screen.
- **Approved boundaries:** Administrators can inspect dataset metadata, ownership,
  size and import status platform-wide. Reading actual dataset contents is an
  explicit administrative action recorded in activity logs. Administrative account
  permissions do not expose patient conversations. Account disabling invalidates
  sessions as specified in D024.
- **Account safeguards:** Prevent disabling/demoting the last active administrator.
  Confirm role changes and disabling. Apply changed permissions immediately to
  existing sessions. Explain effects on ownership/shared access when disabling.
  Use disabling rather than permanent account deletion in the UI; permanent
  deletion requires a separate policy for owned resources and retained activity.
- **Dataset suspension:** Administrators can suspend use with a recorded reason.
  Dependent dashboards show source unavailability; preserve data/history rather
  than deleting silently.
- **Activity events:** Import success/failure, dataset version creation, analysis/
  dashboard creation and updates, sharing/revocation, account status/role changes,
  dataset suspension and administrative content inspection. Do not record passwords,
  session tokens or patient conversations.
- **Still open:** Activity retention, exact disabled-owner resource policy,
  suspension lifecycle and detailed UI/API contracts.
- **Acceptance:** Admin can manage accounts and supervise real datasets/activity;
  analysts cannot invoke those APIs. Logs exclude secrets and unnecessary patient text.
- **Verification:** Check immediate permission changes, revocation, blocked onward
  sharing, suspension effects and last-administrator protection.

## D032 — Platform schema, migrations and reproducible setup

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Accounts plus dataset/import/version/column/row/dependency
  foundation implemented with explicit migrations/grants. Backup/restore verifies
  retained datasets/original values/receipts and excluded staging/session state.
  Checkpoint 3 adds analyses/source relationships and extends backup verification;
  dashboard/sharing domain tables remain future work.
- **Decision:** Retain one PostgreSQL server/database and existing volume. Add a
  separately owned platform schema and runtime permissions alongside core/language.
  No direct access to peer services' private tables.
- **Schema design:** Relational tables for users/sessions/status, datasets/versions/
  column definitions, import state/validation/outcomes, saved analyses/settings,
  dashboards/widgets/layout/filter mappings, sharing/onward-sharing grants,
  suspension and activity. Use foreign keys, uniqueness constraints and indexes.
  Store one record per imported row, with variable values in JSONB linked to its
  immutable version. Column definitions retain stable identifiers, display names,
  types and interpretation rules. Preserve original values where needed.
- **Query behavior:** Server-side filtering/aggregation, bounded results and query
  timeouts; PostgreSQL numeric arithmetic where appropriate. JSONB does not permit
  uncontrolled types or require loading whole datasets into the browser. Benchmark
  the catalogue and larger fixtures before finalizing supported limits.
- **Lifecycle:** Publish only fully validated versions atomically. Clean failed/
  abandoned temporary uploads under a documented retention policy. Analyses remain
  pinned to versions. Archiving removes datasets from the owner's normal workspace
  without breaking analyses. Before deletion show dependencies and shares; block
  deletion until dependent analyses are explicitly removed or migrated.
- **Revocation and disabling:** Dataset revocation blocks exploration and execution
  that depended on that grant, while preserving saved configurations. Revoking
  onward-sharing authorization invalidates access dependent on it. Disabled owners
  lose login/sessions, but their resources and recipients' explicit access remain
  unless grants are revoked or datasets suspended.
- **Reproducible setup:** Pinned dependencies → private configuration → service builds
  → explicit migrations/permissions → administrator provisioning → attributed samples
  through the normal import pipeline → user-run startup. Express runtime privileges
  are restricted to platform; migration privileges are separate. Startup never
  silently recreates tables, regenerates credentials or overwrites datasets.
- **Backup/restore:** Extend coverage to platform accounts, datasets, analyses and
  sharing. Exclude active sessions and temporary upload state; retain the existing
  exclusion of temporary patient conversations. Verify restored data and access
  relationships without reviving sessions or abandoned imports.
- **Reason:** Preserve existing core/language ownership and application data.
- **Approved data integration:** Create attributed pharmaceutical analytics samples
  through an explicit export/import process, using the same import/analysis pipeline
  as user uploads. Express does not query the Python services' private tables.
- **Implementation details:** Concrete tables/indexes, retention values, dependency
  handling, database/migration libraries and Compose changes. Select compatible
  libraries during implementation without another product-level approval.
- **Acceptance:** Clean setup and persistence verified; no modification of frozen
  old migrations, schema ownership or existing volume identity. Document updates.
- **Operating rule:** User runs container lifecycle commands. No credential
  regeneration or destructive database reset as a routine setup shortcut.

## D033 — Validation and demo acceptance

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Checkpoint 1–3 API, PostgreSQL, account/dataset/analytics
  browser and relevant assistant regression checks performed. The final Checkpoint 2 container
  run passed all 14 checks and 18 assistant PostgreSQL tests. Full new-product scenario,
  normal-volume upgrade and user review remain separate. Checkpoint 3's final
  isolated gate passed all 16 checks and all 18 assistant PostgreSQL tests.
- **Decision / scenario:** Login → CSV upload → exploration/filtering → advanced
  analyses → dashboard → save/reopen → share with second account → admin activity.
- **Reason:** Prove the full workflow, not just disconnected screens.
- **Checks:** Calculation correctness, malformed CSVs, missing values, persistence,
  ownership/roles, sharing/revocation and browser flow. Verify assistant regressions
  when integration changes affect it.
- **Coverage checklist:** Map every mandatory CdC requirement to its implemented
  screen/workflow, relevant API, verification evidence and demonstration step.
  Rehearse invalid CSV, revoked access, unavailable dataset and failed widget
  recovery as well as the successful workflow.
- **Implementation details:** Exact fixtures and demonstration accounts/data;
  review checkpoints are approved below.
- **Acceptance:** Record passing evidence, rehearse, prepare backup screenshots or
  recording. Core analytics demonstration works without hosted inference.
- **Boundary:** Historical R7 passes do not validate these new features.

## D034 — Submission and presentation deliverables

- **Date / decision status:** 2026-10-23 / Finalized by the user.
- **Implementation status:** Checkpoint 1–3 architecture/API/setup/evidence and an
  attributed pharmaceutical sample CSV added; final packaging, CdC coverage and
  presentation remain future work.
- **Required:** Complete source; database scripts/migrations; architecture summary;
  API documentation or Postman collection; project presentation.
- **Approved additions:** Clean setup instructions, architecture diagram, attributed
  sample CSVs, demo-account setup, requirement-to-screen/API checklist and rehearsed
  demonstration script. Distinguish implemented behavior from future improvements.
- **Presentation:** Need, architecture, features, user scenario, technical choices,
  difficulties and future improvements.
- **Still open:** Submission packaging, presentation format and team contributions.
  The CdC specifies group work; describe actual contributions honestly.
- **Acceptance:** Submit by October 25; rehearse for October 26. Update README and
  PROJECT_CONTEXT with implemented facts and actual validation, not proposed features.

## Checkpoint 1 implementation record — 2026-10-23

- Branch verified as `feat/pharmaceutical-analytics` before editing. Existing
  uncommitted planning files retained; no branch/commit/push or application-volume
  mutation by the agent. The user started the dedicated PostgreSQL test service.
- `services/platform` now owns Express/TypeScript, npm manifest/lockfile,
  parameterized PostgreSQL access, runtime permission checks, a production image
  recipe and explicit migrations/grants/admin CLI. No peer schema/table access.
- `platform` has users, sessions, auth throttles, account activity and checksummed
  migration history. Frozen Python revisions and source identities/prices/nulls/
  provenance are unchanged. Later domain schemas have not been created.
- Router/account screens and backend role/own-profile enforcement are working;
  password changes require the current password and revoke all sessions. Account
  status/role operations are explicit CLI work until the administration checkpoint.
- Maintained backup now preserves account/activity state while excluding sessions
  and throttles. A real dump/restore against disposable databases verified this
  policy. Dataset/upload coverage was added in Checkpoint 2; sharing remains later.
- Verification: 5 Node security/HTTP/configuration tests; 7 real PostgreSQL scenario groups
  (8 Node test results including the parent), zero skips; 1 real React → Express →
  PostgreSQL browser workflow; 26 offline browser checks including 22 retained
  assistant regressions, with one deployment-only skip; 247 Python checks passed
  with 18 real-assistant-PostgreSQL checks intentionally skipped in that offline
  command and subsequently all passed with zero skips in the user-run full verifier. Service/frontend builds and frontend lint passed (two existing UI
  hot-refresh warnings). Initial sandbox/process restrictions and test fixes are
  documented in [actual evidence](docs/validation/platform-checkpoint-1.md).
- User-run container gate: all 12 full-stack checks passed, including Nginx
  account cookie/CSRF/roles and assistant browser/lifecycle behavior; all 18
  assistant PostgreSQL checks passed, zero skips. The verifier confirmed no
  hosted inference, no application-volume modification and isolated cleanup.
  [Container evidence](docs/validation/platform-checkpoint-1-container.json).
- The user subsequently authorized Checkpoint 2 after these results. Upgrade
  against the preserved normal volume remains a user-run operation. Exact commands are in
  [platform operations](docs/operations/platform-accounts.md). Historical R7 is
  unchanged and is not evidence for the platform.

## Checkpoint 2 implementation record — 2026-10-23

- Continued on `feat/pharmaceutical-analytics`, preserving existing uncommitted
  planning/account work. No commit/push, container lifecycle or normal-volume
  mutation by the agent. User started the dedicated test database and ran the
  isolated image verifier.
- Added owned migration `0002_datasets.sql`; preserved `0001_accounts.sql` and
  Python revisions. Runtime has no update/delete on immutable rows/columns/versions
  and no access to peer schemas. A populated Checkpoint 1 upgrade is tested.
- Guided CSV imports, full-file validation/report, permanent receipts, temporary
  staging cleanup, idempotent atomic publication, private versions, metadata,
  archive/restore and guarded deletion now work through Express and React.
- Full-dataset search/typed AND filters with selected-value OR, typed stable sort,
  pagination, original cells and full-version column/completeness profiles work.
  Analyses, advanced quality/comparison, dashboards and sharing remain future work.
- Added an offline explicit source-to-CSV exporter and 28-record attributed sample;
  no private Python table access or automatic import. Maintained backup retains
  dataset data/receipts and excludes staging, sessions and temporary patient state.
- Evidence: 8 unit tests; 9 dataset PostgreSQL scenario groups (10 test results),
  7 retained account PostgreSQL groups (8 results), 2 real dataset browser workflows,
  1 real account browser workflow, 26 offline browser passes/1 deployment-only skip,
  247 offline Python passes/18 deliberately skipped PostgreSQL checks. Focused
  operations/architecture recheck: 12 passes. Builds/lint pass, with two existing
  UI fast-refresh warnings. Final rebuilt images passed all 14 container checks
  and all 18 assistant PostgreSQL tests, zero skips. The preview-edit race found
  by the first production browser attempt was fixed and verified with a held
  response regression. [Evidence and measurement limits](docs/validation/platform-checkpoint-2.md).
- The final production verifier also exercises dataset browser accessibility,
  versions, ownership, archive/delete and validation recovery through Nginx.
  [Container evidence](docs/validation/platform-checkpoint-2-container.json)
  confirms isolated cleanup, no inference and no application-volume modification.
  Normal-volume upgrade and user review remain pending. Stop before Checkpoint 3.
- Follow-up confidence review found that editing/resetting metadata during a
  pending save could discard the newer edit. Fields/reset now disable until the
  operation completes, and failure preserves the draft. Added a held-response
  offline regression and extended the real dataset browser workflow. All five
  focused offline browser checks plus frontend build/lint pass. The user rebuilt
  web and reran the full verifier: all 14 checks and 18 assistant PostgreSQL tests
  passed, zero skips; cleanup/no inference/no application-volume modification
  confirmed. [Latest container evidence](docs/validation/platform-checkpoint-2-review-container.json)
  validates this fix; the earlier passing report is retained separately.

## Checkpoint 3 implementation record — 2026-10-23

- Continued on `feat/pharmaceutical-analytics` after the user's authorization,
  preserving uncommitted planning/foundation/dataset work. No branch, commit,
  push, hosted inference, catalogue-data changes or application-volume mutation by the
  agent. The user controls test-container startup/shutdown and production checks.
- Added owned migration `0003_analyses.sql`, private saved definitions and
  restrictive source/version relationships, real dependency registrations and
  extended runtime grants/activity/backup coverage. Prior SQL/Alembic revisions,
  immutable source cells and Python schema ownership remain intact. A populated
  Checkpoint 2 upgrade and maintained real backup/restore pass.
- Parameterized full-version aggregates, typed rankings/grouping, templates and
  all four advanced features work through Express and React. Results explain
  denominators, limits, missingness and statistical rules. Recommendations create
  editable definitions; comparison requires explicit mappings and complete unique
  row keys when matching rows. Neither infers medication equivalence.
- Added standalone KPI/bar/temporal-line/pie/histogram/scatter views with exact
  table alternatives, explicit save/reopen/recalculate, immutable version pinning,
  revisions, active-account/source ownership checks and pending-edit protection.
  Dashboards, interactive dashboard filters, sharing and administrative workflows
  remain later checkpoints.
- Correctness evidence: 8 retained unit tests; 11 analytics PostgreSQL groups
  (12 test results), 9 dataset groups (10 results) and 7 account groups (8 results),
  all passing with zero skips. Both final analytics browser workflows pass,
  including desktop/mobile axe, held-save locking and all chart types; both
  dataset workflows and the account workflow pass. Offline browser: 28 passes,
  one deployment-only skip. Final operations/architecture: 23 passes. Service/
  frontend builds and lint pass, with two preexisting UI fast-refresh warnings.
- Known-input checks include large close-decimal statistics, exact type-7
  quartiles, all-missing/constant/zero-IQR cases, strict fences, source privacy,
  complete unique keys and real source dependency changes. New means use
  numeric(80,24); old immutable profiles are not backfilled. Catalogue (9,936
  rows), 25,000-row and 25,000-group measurements are recorded with their local
  evidence limits in [Checkpoint 3 evidence](docs/validation/platform-checkpoint-3.md).
- All images built successfully. The first production verifier passed its
  analytics API probes, then crashed recording them: an HTTP response variable
  overwrote the report dictionary. The helper-only correction passes a mocked
  orchestration/reporting/cleanup regression. Read-only Docker inspection found
  no containers, volumes or networks left for the failed isolated project.
  The user reran the verifier without rebuilding: all 16 named checks and all
  18 assistant PostgreSQL tests passed, zero skips. The real analytics workflow
  ran through production Nginx; saved source persistence survived whole-stack
  replacement. The report confirms no inference, no application-volume changes
  and complete isolated cleanup. [Retained container evidence](docs/validation/platform-checkpoint-3-container.json).
- Normal-volume upgrade and user workflow/layout review remain separate. Stop
  for review before Checkpoint 4; no authorization to start it has been given.

## Approved implementation checkpoints

Approved by the user on 2026-10-23. Checkpoint 1 is **implemented and verified**;
the user authorized continuation. Checkpoint 2 is **implemented and verified in
host and isolated production-image checks, including the follow-up metadata fix;
the user authorized continuation**. Normal-volume upgrade remains a user-run
operation. Checkpoint 3 is **implemented and verified in host/browser and isolated
production-image checks, awaiting user review**. Checkpoints 4–6 are **not started**.

| Checkpoint | Working result | Completion evidence |
| --- | --- | --- |
| 1 — Foundation and accounts | Implemented: Express service, account schema/migrations, Router, registration/login/logout/profile, role/ownership guards | PostgreSQL/API/browser and 12 full-stack checks passed; user authorized continuation. Normal-volume upgrade pending. [Evidence](docs/validation/platform-checkpoint-1.md) |
| 2 — Dataset lifecycle | Implemented: CSV preview/validation/import, private versions, exploration, metadata/archive/deletion | All 14 rebuilt-image checks/18 assistant PostgreSQL tests passed; user authorized continuation. Normal-volume upgrade pending. [Evidence](docs/validation/platform-checkpoint-2.md) |
| 3 — Analytics | Implemented: aggregations, pharmaceutical templates, all four advanced features, charts/private saved definitions | Final host checks, all 16 full-stack checks and 18 assistant PostgreSQL tests pass; awaiting user review. Normal-volume upgrade separate. [Evidence](docs/validation/platform-checkpoint-3.md) |
| 4 — Dashboards and collaboration | Adjustable builder, persistence, filters, sharing/revocation | Browser workflow and adversarial permission checks |
| 5 — Administration and integration | User controls, suspension, activity, assistant integration, backup/restore | Lifecycle, last-admin protection and regression checks |
| 6 — Delivery | Clean setup, complete demonstration, documentation, presentation | CdC coverage checklist, final verification and rehearsal |

At each completed checkpoint, provide changes, validation evidence and remaining
issues for user review before proceeding to the next. Security and verification
are part of each checkpoint. The user retains container lifecycle and Git publication
control. Plan approval does not mean any checkpoint has been implemented.

Security and focused checks accompany each stage. All mandatory requirements need
complete workflows and verification. Evaluate optional formats, forecasting,
public publishing and layout features on their value; do not silently cut important
behavior or quality because of the submission date.
