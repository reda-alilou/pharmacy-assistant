# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

The application in `apps/web/` is a French-language pharmaceutical data-analysis platform with a separate pharmacy assistant. The platform supports the complete workflow **import → exploration → analysis → visualization → sharing**. It extends the earlier Moroccan pharmacy assistant for the Full Stack learning project; the assistant remains an additional feature rather than the main analytical workspace.

Success means an authenticated analyst can import a new CSV, verify its interpretation, explore the complete dataset, calculate understandable results, save reproducible analyses, construct an interactive dashboard, and deliberately share the appropriate access. The assistant helps visitors resolve recorded medication presentations, historical prices and pharmacy contact information through temporary conversations.

This is a local challenge/demo and learning project. Public production hosting, commercial adoption and clinical use are not established product facts.

## Users

The user confirmed on 2026-10-25 that the documented roles should be retained and precise analyst personas should remain open.

| Audience | Situation and job | Access boundary |
| --- | --- | --- |
| Analyst | Work with uploaded pharmaceutical datasets: import, explore, analyze, save visualizations and share selected resources. | Own resources and resources explicitly shared with their account. Public registration creates an analyst account. |
| Read-only recipient | Consult a dataset, saved analysis or dashboard another account has shared. This is a resource permission, not a separate account role. | Dataset grants and result grants are distinct; seeing results does not itself permit raw-row exploration or editing. |
| Administrator | Supervise accounts, datasets and recorded platform activity; inspect or suspend datasets when needed. | Administrative supervision does not confer ordinary unrestricted access to another owner's data. Content inspection is explicit and logged. |
| Visitor / assistant user | Read the introduction, register or sign in, or ask the independent pharmacy assistant about recorded medication information and the partial Rabat directory. | The assistant is available without a platform account. Its conversations do not become account-based patient history. |

No specific analyst employer, profession, skill level, organizational setting or frequency of use has been confirmed. Do not turn the generic company/client scenario in the assignment into a claim about actual customers.

## Positioning

The implemented product combines pharmaceutical CSV analysis with a retained Moroccan medication/pharmacy lookup assistant. Its concrete mechanisms are source-aware information, explicit immutable dataset versions, reproducible analytical definitions, and separate permissions for underlying datasets and derived results.

The two areas have distinct responsibilities: analysts operate on their uploaded datasets; the assistant resolves requests against its recorded catalogue and directory. Uploading a platform CSV does not update the assistant catalogue. Hosted language extraction identifies requests and entities; deterministic backend code performs matching, price calculations and factual answer construction.

## Operating Context

The existing application is a responsive browser interface used locally. The integrated installation is served through Nginx at `http://127.0.0.1:8080`; the assistant has its own `/assistant` screen. Desktop and mobile layouts exist. The optional phone/LAN overlay is for assistant testing; authenticated LAN use requires HTTPS configuration.

The established implementation is React, TypeScript, Vite, React Router, Tailwind CSS and project-owned UI controls. Express owns platform accounts, datasets, analytics, dashboards, sharing and administration. Separate Python/FastAPI core and language services support the assistant. PostgreSQL persistence and service-owned schemas keep those domains separate. See [architecture](docs/architecture/overview.md) for technical ownership.

The frontend development entry is `npm run dev` from `apps/web/`; backend startup remains a separate, user-controlled operation. Do not start or stop application containers, run hosted inference, alter private runtime settings or publish Git changes as a side effect of design work.

### Main workflows

| Workflow | Existing entry points | Required behavior |
| --- | --- | --- |
| Enter and manage an account | `/`, `/inscription`, `/connexion`, `/espace`, `/profil` | Register/sign in, return to protected local destinations, manage the displayed name/password and sign out. Assistant conversations remain separate. |
| Import and publish data | `/donnees`, `/donnees/importer`, `/donnees/imports/:id` | Upload privately; review delimiter, encoding, types, decimal/date conventions and missing markers; enter metadata; validate the complete CSV; explicitly publish or cancel. Publication creates a new dataset or immutable version atomically. |
| Explore and manage a dataset | `/donnees/:id` | Choose a version; inspect overview, rows, original values, columns, completeness and history; search/filter/sort the full version with pagination. Owners can edit metadata, add versions, archive/restore, and review dependencies before guarded deletion. |
| Build and save an analysis | `/analyses`, `/analyses/nouvelle`, `/analyses/:id`; dataset analysis entry | Select explicit source versions and filters, configure calculations or applicable pharmaceutical templates, calculate, inspect results and explicitly save. Reopening preserves source versions and rules; results are recalculated rather than stored as permanent snapshots. |
| Assemble and use a dashboard | `/tableaux`, `/tableaux/nouveau`, `/tableaux/:id` | Configure multiple widgets, arrange/resize them, explicitly map interactive filters to compatible source columns, and save or discard edits. Readers can use permitted filters on the saved configuration. |
| Share or revoke access | Dataset, analysis and dashboard sharing panels | Grant read access to an existing account by exact email; review and revoke grants. Result sharing does not expose raw datasets. Onward sharing of results derived from another owner's dataset requires that owner's authorization for the particular resource revision. |
| Supervise the platform | `/administration` | Review global indicators, users, datasets and activity; confirm role/status changes; explicitly inspect content with a reason; suspend or restore dataset use. |
| Ask the assistant | `/assistant` | Type a question, resolve ambiguous products through offered choices, ask contextual follow-ups, inspect sources and recorded-price totals, restore the temporary conversation after refresh, or explicitly reset/retry. |

## Capabilities and Constraints

### Data interpretation and reproducibility

- CSV is the implemented upload format. Current bounds are 10 MiB, 25,000 data rows, 100 columns and 1,000,000 cells, applied together. UTF-8 and Windows-1252 are supported; staging uploads expire after one hour. Preserve corrective validation and explicit publication rather than implying every uploaded file is already usable.
- Published versions retain original cells, interpreted values, import configuration and provenance. Published rows and versions are immutable. Identifiers can remain text so leading zeros survive. Missing values remain distinct from zero; invalid typed values must not silently become missing values.
- Search, typed filters, sorting and counts apply to the entire selected version. Pagination is a view of those results, not the scope of calculation.
- Analytics includes aggregations, pharmaceutical templates, KPI/bar/line/pie/histogram/scatter views and four advanced features: missing-value analysis, IQR outliers, editable chart recommendations and explicit dataset/version comparison. Templates depend on available fields; IQR flags are statistical signals, not clinical conclusions.
- Saved definitions pin dataset/version references, filters, calculation rules and chart settings. A newer import must not silently replace a saved source. Changing datasets resets incompatible settings; column equivalence and filter mappings are not inferred from matching names.
- Exact server numeric values and declared calculation conventions remain authoritative. Preserve missing-value denominators, source/version context, chart omissions and exact table alternatives. Pie charts require supported additive counts; arbitrary price sums or means are not valid pie inputs under the current contract.
- Calculation, publication and saving are deliberate actions. Configuration changes or failures clear obsolete results. Errors, empty states, pending operations, unavailable sources and uncertain saves must remain understandable and recoverable without automatic POST replay.

### Privacy, permissions and lifecycle

- New datasets, analyses and dashboards are private. Sharing is explicit and read-only; saving does not create a grant. Copies require the relevant dataset permissions. Current backend authorization is authoritative, including on direct URLs and subsequent result requests.
- Dataset suspension blocks use while preserving data, saved configurations and recorded grants. Restoration does not revive a revoked grant. Archiving, administrative suspension, revocation and permanent deletion have different effects and must remain distinct.
- Administrative account changes invalidate affected sessions; the last active administrator is protected. Account disablement does not mean the user's stored resources are deleted. Content inspection remains explicit and logged.
- Preserve existing authentication/session protections, service ownership, migrations, source evidence and database volumes. Credentials and provider keys do not belong in frontend assets or documentation. Container lifecycle and Git publication remain under the user's control.

### Assistant facts and limits

- The interface is French. Backend interpretation and answer templates support French, Arabic, Darija and mixed-language requests; complete Arabic UI localization and an RTL interface are deferred.
- Matching distinguishes medication identity, strength, form and presentation. Ambiguity requires clarification; aliases and spelling suggestions must not silently select an uncertain product. Complete-package totals use recorded prices and backend decimal rules. Unknown prices stay unknown.
- Prices and pharmacy contacts are dated observations. The directory is partial and limited to Rabat. The app does not verify stock, opening hours or duty schedules, calculate geographic proximity, diagnose conditions or recommend treatment. Dataset statistics do not establish therapeutic value.
- Conversations expire after 30 minutes of inactivity. Refresh restores through a read-only request without repeating the question or renewing expiry. Failed questions support explicit recovery/retry, and reset clears local state only after server invalidation or expiry.
- New typed requests depend on hosted inference, internet availability and quotas. Valid offered choices may work without another model call. There is no automatic provider switch, paid fallback or saved-answer fallback.
- Voice, durable patient history, public dashboards, JSON/Excel/API imports, forecasting and additional machine-learning features are outside the implemented scope. Do not present assignment options or historical proposals as working features.

## Brand Commitments

The platform currently identifies itself as **Pharma Analyse** in its navigation and page title; the separate chat is **Assistant pharmacie**. Preserve these existing labels unless the user requests a change. The decision log still leaves the final product name open, so current UI naming does not establish a finalized brand.

French copy and source-aware, factual explanations are established. Preserve the explicit distinction between recorded observations and current guarantees, and between statistical findings and clinical interpretation. Existing approved presentation constraints include solid colors, no gradients and no decorative card side strips; this initialization does not define a palette, typography system or replacement visual direction.

## Evidence on Hand

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) explains the implemented system, operating boundaries and current checkpoint evidence. [DECISION_LOG.md](DECISION_LOG.md) records approved choices and open decisions. Use them together; approval alone is not implementation evidence.
- [Full Stack requirements](CdC_Application_Full_Stack.md) and the [implemented coverage map](docs/project/full-stack-coverage.md) distinguish assignment requirements, delivered workflows and optional features.
- [Frontend documentation](apps/web/README.md), [route composition](apps/web/src/app/App.tsx) and `apps/web/src/features/` show the incumbent interface and functionality. Existing code is evidence of the current implementation, not blanket approval to redesign it.
- The assistant's preserved inputs are `data/imports/ammps_medications_enriched.jsonl` and `data/imports/pharmacies_rabat.jsonl`: 9,936 presentations and 327 pharmacy records. The [data guide](docs/project/data-and-evidence.md) records provenance, missing prices and evidence limits. These inputs are separate from users' private platform datasets.
- [The downloadable pharmaceutical sample](apps/web/public/samples/README.md) documents attributed, dated observations and retained unknown prices. Attribution does not establish a blanket third-party redistribution license.
- [Functional-review fixtures](apps/web/tests/fixtures/functional-review/README.md), including `cp6-v1.csv` and `cp6-v2.csv`, are explicitly synthetic and have known expected results. They are not real medication observations or patient data.
- [Checkpoint 6 evidence](docs/validation/platform-checkpoint-6.md) and the [installed functional review](docs/validation/platform-checkpoint-6-functional-review.md) distinguish automated checks from user-reported manual observations. Historical assistant evaluation results remain tied to their frozen implementations; they do not establish current universal model accuracy.
- Actual customers, testimonials, clinical validation, independent native-speaker evaluation and public production deployment are not established by the repository. Do not fabricate proof, licensing or adoption claims.

## Product Principles

1. **Keep facts traceable.** Preserve source attribution, observation dates, original values, missingness and uncertainty throughout import, calculation and assistant answers.
2. **Make analysis reproducible.** Keep immutable versions and explicit rules; never silently change the source or imply an unsupported equivalence.
3. **Make access deliberate.** Separate dataset access from result access, respect original ownership, and make revocation and suspension effective.
4. **Keep actions and recovery understandable.** Explicit publication, calculation, saving, sharing and retry must communicate their state and consequences without showing stale success.
5. **Preserve the two workflows.** Keep authenticated analytical work separate from visitor-accessible temporary pharmacy conversations and their distinct data and limitations.

## Accessibility & Inclusion

Preserve the implemented responsive desktop/mobile workflows, keyboard-operable forms and dashboard arrangement/resizing, visible focus, labeled controls, skip links, status/error announcements, and reduced-motion behavior. Charts retain descriptions and exact table alternatives so color and geometry are not the only means of understanding results.

The repository includes Playwright/axe accessibility checks and responsive evidence. Those checks do not establish a formal accessibility certification. No particular disability cohort or additional required conformance standard has been confirmed. French UI and multilingual request support must not be described as a fully localized Arabic/RTL experience.

## Open Decisions

- Precise analyst personas, their work settings and experience levels remain deliberately unspecified, as confirmed by the user.
- The final product name remains open; **Pharma Analyse** is the implemented UI name.
- No public deployment plan, commercial model, additional import format, full Arabic UI or further analytical feature is established by this initialization. Such changes require their own product decisions.

This file captures durable product context for future work on `apps/web/`. It does not authorize application changes or a redesign, replace the technical references, or expand the previously agreed project scope.
