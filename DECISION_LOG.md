# Final improvement decisions

This file records only finalized decisions about project improvements that the
user has explicitly approved. Each entry will state the improvement, the chosen
approach or technology, and why it was chosen.

## D001 — Separate frontend, core backend, and language service

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use a separate frontend and two independently runnable backend
  services with explicit communication contracts.
- **Responsibilities:**
  - Frontend: patient interface.
  - Core backend: conversation flow, clarification, medication matching,
    pharmacy lookup, and pricing, organized into separate internal modules.
  - Language service: hosted model calls, extraction validation, provider
    adapters, and inference quota handling.
- **Reason:** Balance a polished laptop demo with practical learning about
  service communication, timeouts, errors, and independent containers. Language
  extraction already has a clear boundary from local factual answers. Keeping
  medication and pharmacy logic in the core backend limits network dependencies
  and operational complexity.
- **Alternatives considered:** One modular backend offers simpler operation but
  less distributed-service practice. Separate medication and pharmacy services
  add complexity without an established need for independent scaling or deployment.
- **Conditions:** Medication and pharmacy services remain possible later
  extractions, not part of this initial split. Define and test behavior during
  language-service failures; separation alone does not guarantee resilience.
- **Still open:** Frontend technology, exact service contracts,
  database design, container tooling, and orchestration. This decision does not
  finalize those choices or authorize implementation of the migration.
  Backend technology is finalized separately in D002.

## D002 — Keep Python and FastAPI for both backend services

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use Python and FastAPI for both the core backend and the language
  service. They remain independently runnable applications as agreed in D001.
- **Reason:** Preserve tested Python behavior and existing Pydantic validation
  while focusing migration effort on service architecture, maintainability, and
  the patient interface. FastAPI meets the identified API needs and supports the
  intended separation without a framework or language rewrite.
- **Alternatives considered:** NestJS for the core backend or both services would
  provide TypeScript backend learning but require substantial porting and
  regression verification. No current requirement justifies that additional work.
- **Implementation direction:** Keep business logic separate from HTTP handling;
  translate application errors into HTTP responses at the API boundary. Reuse
  existing domain logic and validation while defining explicit service contracts.
- **Still open:** Database access and migration libraries,
  frontend technology, and exact service contracts. This records the technology
  choice; implementation of the migration has not started.
  Database engine choice is finalized separately in D003.

## D003 — Use PostgreSQL as the runtime database engine

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use PostgreSQL for the planned runtime database. Do not add
  MongoDB or another NoSQL database for the currently identified requirements.
- **Reason:** The application has structured, related medication, presentation,
  price, pharmacy, and provenance data. PostgreSQL also supports queryable JSONB
  for flexible data where appropriate, so JSON inputs or model outputs do not
  require a separate document database. It supports the database-backed service
  architecture and learning goals without introducing a second database system.
- **Alternatives considered:** Keeping file-based storage minimizes migration;
  SQLite provides simpler local SQL persistence. PostgreSQL provides practice
  operating a database server and connecting independent services. No identified
  requirement calls for MongoDB or another NoSQL database.
- **Still open:** Exact migration scope and table design,
  persistence and retention rules, database access and migration libraries,
  database version, and deployment tooling. JSONB support is a capability, not
  a finalized schema choice. Existing source files and evaluation evidence are
  not authorized for deletion by this decision.
  Database topology and service ownership are finalized separately in D004.

## D004 — One PostgreSQL database with service-owned schemas

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Start with one PostgreSQL server and one database containing two
  schemas, each owned by its corresponding backend service.
- **Ownership:**
  - `core`: core backend; medications, presentations, prices, pharmacies,
    provenance, and conversation/clarification state.
  - `language`: language service; runtime inference quota counters, reservations,
    and cooldowns.
- **Access boundaries:** Each service uses separate runtime credentials with
  permissions restricted to its own schema. Services communicate through their
  APIs rather than accessing each other's tables. The frontend accesses data
  through the core API, without direct database access.
- **Reason:** Practice explicit data ownership and permissions while keeping
  local operation manageable. Both services still share the database server as
  a dependency; separate schemas do not provide independent availability.
- **Alternatives considered:** Shared tables accessible to both services risk
  coupling their internal storage. Separate databases or servers add operational
  work that is not currently justified; later separation remains possible.
- **Still open:** Detailed tables,
  migration/import tooling, administrative and migration credentials, and the
  treatment of existing offline evaluation ledgers.
  Temporary conversation behavior is finalized separately in D005.

## D005 — Temporary conversations with persistent, expiring context

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use temporary conversations for the first version, without
  permanent reopenable chat history or account-based history.
- **Behavior:**
  - Store conversation context and pending clarification choices in the `core`
    schema so follow-ups retain the selected medicine, presentation, quantities,
    and outstanding choices.
  - Preserve active context across backend restarts and page refreshes while
    its token remains available and valid.
  - Expire context after 30 minutes without a successful interaction.
  - Provide a New conversation action that clears the current conversation from
    the interface and invalidates its active server state.
  - Reject expired tokens immediately and periodically delete expired state.
- **Reason:** Support a polished conversational demo and learn persistent state
  handling without adding user accounts or a chat-history feature.
- **Alternatives considered:** Reopenable history on the same browser or across
  signed-in devices would require additional message storage, ownership, and UI.
- **Still open:** Browser token storage, exact cleanup scheduling, and detailed
  state/token mechanics. Temporary transcript restoration is finalized in D006.

## D006 — Restore the active temporary transcript after refresh

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Restore the active conversation's visible messages after a page
  refresh while the conversation remains valid.
- **Lifetime:** The transcript shares the context's 30-minute inactivity expiry.
  It is no longer available when that conversation expires or the user starts a
  new conversation. This adds no permanent history or list of previous chats.
- **Reason:** Keep the displayed conversation consistent with the context the
  backend remembers, making refreshes less disruptive to the demo.
- **Still open:** Transcript storage and retrieval details, browser token storage,
  and cleanup scheduling. These must respect the temporary lifetime above.

## D007 — SQLAlchemy for database access and Alembic for migrations

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use SQLAlchemy for database access and transaction handling in
  both backend services, and Alembic for versioned database schema migrations.
  Retain Pydantic for API request and response validation. Keep database models
  separate from API models.
- **Reason:** Reuse existing API contracts while allowing storage structures to
  evolve independently. SQLAlchemy provides object mapping and explicit query
  tools; Alembic makes database structure changes tracked and repeatable.
- **Alternatives considered:** Direct SQL through a driver requires more manual
  row mapping. SQLModel reduces some repetitive definitions but adds an
  abstraction over SQLAlchemy and Pydantic; explicit model separation better
  fits the existing contracts and planned storage changes.
- **Implementation direction:** Review generated migrations before applying them.
  Use SQLAlchemy ORM or Core queries where appropriate without exposing database
  models directly as the public API contract.
- **Still open:** PostgreSQL driver, exact dependency versions, synchronous versus
  asynchronous access, and migration organization for the service-owned schemas.
  This resolves the database access and migration library choices left open in
  D002 and D003; migration execution and imports remain to be designed.

## D008 — React, TypeScript, and Vite for the frontend

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Build the separate frontend with React for interface components,
  TypeScript for development-time type checking, and Vite for development and
  production builds. The browser interface calls the FastAPI core backend.
- **Reason:** Fits the interactive chat, clarification choices, medication cards,
  and temporary conversation restoration while providing practical frontend
  learning. No current requirement calls for server-rendered public pages.
- **Alternatives considered:** Vue with TypeScript and Vite is viable, but the
  user has no framework preference. Next.js adds routing and server-rendering
  capabilities whose additional concepts are not currently needed.
- **Still open:** Visual design, routing and
  data-fetching tools, runtime response validation, exact versions, and frontend
  serving configuration. Arabic and mixed-direction layout require deliberate
  implementation and testing regardless of this stack choice.
- **Relationship:** Resolves the frontend technology choice left open in D001
  and D002. This records the choice; frontend implementation has not started.
  Styling and component choices are finalized separately in D009.

## D009 — Tailwind CSS and shadcn/ui for styling and common controls

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use Tailwind CSS for layout, typography, colors, spacing, and
  responsive styling, with shadcn/ui for common controls such as buttons,
  dialogs, and selection controls. Build application-specific chat messages,
  medication cards, and pharmacy results using these tools.
- **Reason:** Combine customizable components with control over the pharmacy
  assistant's design, while providing inspectable component code for learning.
- **Alternatives considered:** Plain CSS with entirely custom controls requires
  more interaction and consistency work. Material UI provides a more complete
  default appearance but may require more overrides for a custom design.
- **Implementation direction:** Maintain added shadcn/ui component source as
  project code. Verify keyboard navigation, focus behavior, contrast, responsive
  layouts, and Arabic/RTL including mixed Latin names, numbers, and prices.
- **Still open:** Visual direction, colors, fonts, page layout, exact component
  selection, and dependency versions. This choice does not finalize a design.

## D010 — Focus the first frontend version on chat

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Make the first version a chat-focused interface. Show medication
  and pharmacy results, clarification choices, and price summaries within the
  conversation. Do not add separate medication or pharmacy browsing views or a
  permanent results panel in this version.
- **Reason:** Keep the initial interface and implementation focused on the
  conversational experience.
- **Alternatives considered:** Separate browsing views provide direct lookup
  without inference but add screens and API work. A permanent results panel adds
  layout and state complexity, especially on mobile.
- **Relationship:** Retain the New conversation action and temporary transcript
  behavior agreed in D005 and D006. This UI scope choice does not remove existing
  backend search APIs or change the service boundaries in D001.
- **Still open:** Detailed chat layout and
  presentation of sources, limitations, loading states, and errors.
  Visual direction is finalized separately in D011.
  Interface language scope is finalized in D012.

## D011 — Calm healthcare visual style without gradients or card side strips

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use a light, calm healthcare-oriented interface with an off-white
  background, restrained teal accents, readable text, and clearly labelled
  result cards.
- **Explicit constraints:** Do not use gradients or decorative side strips on
  cards, including colored accent bars along card edges.
- **Reason:** Reflect the user's preferred healthcare aesthetic while avoiding
  the decorative patterns they explicitly dislike.
- **Still open:** Exact color values, fonts, spacing, and detailed component
  layouts. These must follow this visual direction and the constraints above.

## D012 — French-only interface for the first version

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use French for interface labels, buttons, navigation, and notices
  in the first version. Do not add a language switcher. Defer Arabic interface
  translation and full right-to-left application layout to a later phase.
- **Reason:** Keep the initial interface scope focused; the user prefers to
  address Arabic interface support later.
- **Boundary:** This decision concerns interface localization, not removal of
  existing multilingual interpretation or reply behavior. Preserve existing
  chat capabilities and readable message content.
- **Relationship:** Defers the full Arabic/RTL interface work discussed in D008
  and D009. Other accessibility and responsive-layout requirements remain.

## D013 — Short conversational answers with structured result cards

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Present a short conversational answer followed by structured
  cards when useful. Avoid repeating full breakdowns in both prose and cards.
- **Presentation:**
  - Medication cards show identity, strength, presentation, stored price,
    explicit quantity and calculated total where available. Show stored
    commercialization status separately from stock availability.
  - Offer clearly labelled buttons or selectable cards for clarification.
  - For multiple medications, show one card per medication and an order total
    only when every line is calculable.
  - Pharmacy results show name, address, phone, and source where available,
    with relevant coverage limitations.
  - Describe missing prices and unknown stock plainly; never imply live stock
    or current retail price verification from stored records.
  - Make source links and collection dates easy to find. Put longer readable
    provenance under Sources et détails, without raw extraction JSON or
    internal diagnostics anywhere in the patient interface.
  - Show a simple loading indicator and prevent duplicate submission while
    a request is in progress. Explain errors and expiry briefly in French,
    with an appropriate next action.
- **Reason:** Keep answers readable while preserving factual limits, provenance,
  and the existing matching and pricing rules.
- **Still open:** Exact component layouts and wording, response-to-card mapping,
  and implementation of error recovery. Follow D011's visual constraints.

## D014 — Docker containers managed with Docker Compose

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Run four long-running containers through Docker Compose:
  web (React assets and forwarding to the core API), core API, language service,
  and PostgreSQL. Keep inference hosted by the existing provider.
- **Operating rules:**
  - Provide one localhost browser entry point. Keep the language service and
    database internal; configure any additional debugging access separately.
  - Store PostgreSQL data in a persistent volume that survives normal shutdown
    and container replacement. Backups are a separate concern.
  - The user controls startup and shutdown using provided commands, with
    service-specific logs available.
  - Supply credentials at runtime; exclude them from source control, frontend
    assets, and built images.
  - Run migrations and imports as explicit setup steps, not automatic data
    rebuilds on application startup.
  - Use readiness health checks and application-level dependency failure handling.
- **Local environment:** Use Docker Desktop with the WSL 2 backend on Windows,
  subject to checking machine prerequisites before installation.
- **Reason:** Reproducible local operation and practical container/service
  learning without the overhead of cluster management.
- **Alternatives considered:** Manual processes require more environment and
  lifecycle management. Kubernetes is deferred without a cluster requirement.
- **Deferred to implementation:** Ports, image versions, web-serving software,
  exact Compose configuration, and development/debugging configuration. This
  decision does not authorize installing software or starting services now.

## D015 — HTTP/JSON service communication and explicit failure handling

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Use HTTP requests with JSON responses between the core backend
  and language service for the interactive request-response flow. Do not add a
  message broker or background-job system for this flow.
- **Responsibilities:** The core sends the current typed message for validated
  extraction; it retains context merging, matching, pricing, and factual answer
  generation. Clarification buttons use the core without another inference call.
- **Failure behavior:**
  - On language/provider unavailability, show a clear French error and allow
    retry while preserving the conversation. Inference-free choices remain
    usable when the core and database are healthy.
  - On core/database unavailability, explain that the operation cannot complete;
    do not fabricate a successful result.
  - Bound waiting times, respect quota cooldowns, and avoid retries at multiple
    layers multiplying inference requests.
  - Preserve failed user messages so they do not need to be typed again.
- **Reason:** Keep service communication understandable and preserve existing
  inference-free behavior while making dependency failures visible and recoverable.
- **Deferred to implementation:** Endpoint names, exact contracts, timeout values,
  retry mechanics, and handling of uncertain completion after connection loss.

## D016 — Relational database design with a validated data migration

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Design proper relational tables within the service-owned schemas,
  with primary/foreign keys, uniqueness constraints, appropriate numeric price
  types, and indexes. Use JSONB only where flexible structures warrant it, not
  as a replacement for relational catalogue design.
- **Migration:** Import the active medication catalogue and Rabat pharmacy
  directory while preserving record identities, distinct presentations, prices,
  missing values, source observations and dates, and conflicts. Imports must be
  repeatable without duplicates. Do not merge products solely by brand name.
- **Validation:** Review the concrete schema before creating tables and importing
  data. Compare counts and field values, and verify existing matching,
  clarification, and pricing behavior before switching runtime storage.
- **Preservation:** Retain source snapshots, reproducible import inputs, and
  original evaluation evidence as files. Keep historical evaluation ledgers
  intact; migrate runtime quota state separately without silently resetting
  cooldowns or accounting.
- **Recovery:** Provide and verify a database backup-and-restore procedure before
  relying on the migrated database.
- **Reason:** Improve storage structure and integrity while preserving data
  meaning, provenance, and tested behavior.
- **Deferred to implementation:** Exact tables and relationships, medication
  grouping rules, indexes, import commands, and backup tooling. Example tables
  discussed are illustrative, not a finalized schema.

## D017 — Keep the existing repository as a monorepo

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Organize the existing repository as a monorepo with clear areas
  for the frontend, core service, language service, deployment configuration,
  data/import tools, evaluation evidence, and documentation. Keep service code,
  database models, migrations, and tests clearly owned by their service.
- **Boundaries:** Each service builds and runs independently. Sharing a repository
  does not permit imports of another service's internals or access to its tables.
- **Reason:** Simplify coordinated contract, test, and deployment changes for a
  solo learning project while retaining explicit service boundaries.
- **Alternatives considered:** Separate repositories add coordination overhead
  without a current need for independent repository management.
- **Existing setup:** The user has already created the improvement branch;
  verified current branch is `refactor/web-architecture`. Continue within this
  repository and branch; no new repository or branch is needed for this decision.
- **Deferred to implementation:** Exact folder names and any shared contract
  package. Repository cleanup must not automatically delete data or evidence.

## D018 — Implement in reviewed checkpoints

- **Date:** 2026-10-19
- **Status:** Finalized by the user
- **Decision:** Follow this implementation sequence, reviewing each completed
  checkpoint with the user before proceeding to the next:
  1. Establish the baseline and code boundaries: verify existing tests, organize
     service-owned code, and separate business errors from HTTP handling.
  2. Design and introduce PostgreSQL storage: review the relational schema,
     implement migrations/imports, validate data, and add temporary conversation
     persistence.
  3. Extract the language service: connect through HTTP/JSON and verify inference
     failures, quotas, and inference-free choices.
  4. Complete Docker Compose integration: verify startup, persistent storage,
     readiness, and failure handling. Container setup may begin earlier when
     needed for PostgreSQL.
  5. Build and integrate the frontend: implement the agreed chat experience,
     result cards, temporary transcript restoration, and French healthcare style.
  6. Validate the complete demo and retire Streamlit: check representative
     conversations, refresh/expiry, error recovery, and setup documentation before
     removing the old interface.
- **Reason:** Keep changes reviewable and preserve working behavior throughout
  the migration, with user validation at each checkpoint.
- **Deferred to implementation:** Resolve detailed implementation choices when
  needed within the agreed architecture and scope. Approval of this sequence
  records the plan; implementation has not started.

## D019 — Approve the checkpoint 2 relational schema direction

- **Date:** 2026-10-20
- **Status:** Finalized by the user
- **Decision:** Proceed with the relational schema described in
  `docs/architecture-checkpoint-2-schema.md`, following its review under D016.
  Group medications by the exact source brand/substance/EPI/strength/form tuple
  while preserving each presentation's original public ID. Store prices,
  observations, conflicts, pharmacies, aliases, and temporary conversations in
  related service-owned tables; use versioned JSONB for flexible temporary state.
- **Reason:** Preserve existing facts and behavior while improving data integrity,
  provenance, and restart-safe temporary conversations.
- **Validation:** Complete round-trip, constraints, quota, and conversation
  lifecycle checks against PostgreSQL before relying on the migrated runtime.
- **Implementation boundary:** Resolve routine driver, migration, and connection
  details as needed. The user controls starting/stopping database and demo services.

## D020 — Production-style monorepo cleanup in reviewed checkpoints

- **Date:** 2026-10-20
- **Status:** Finalized by the user
- **Decision:** Reorganize core and language as separately installable Python
  packages within this monorepo, with owned dependencies, settings, migrations
  and tests. Keep React in its own app area; use small contracts/infrastructure
  packages and the existing uv tooling with one workspace lockfile.
- **Runtime:** Both running services require PostgreSQL. Remove the old
  file/in-memory startup option and SQLite runtime quota backend. Keep JSONL for
  explicit imports and fixtures for offline tests; do not remove raw data.
- **Maintained tools:** Keep database setup/import/backup, isolated deployment
  verification and current evaluation/scoring/evidence tools. Retire collection,
  scraping, expansion/enrichment workflows, Streamlit, compatibility forwarding
  modules and obsolete commands after useful coverage is migrated.
- **Preservation:** Isolate raw snapshots, historical secondary data, reports and
  superseded documents in a hash-verified archive. Keep active import/evaluation
  inputs and preserve historical evidence contents. Private credentials, ledgers,
  backups and existing application volumes remain untouched. This clarifies the
  preservation rules in D016/D017; it does not authorize discarding raw data.
- **Sequence:** Execute R1–R7 in `docs/development/cleanup-plan.md`, stopping after
  each completed checkpoint for user review. R1 establishes the baseline and
  inventory only. The remaining final validation/Streamlit retirement from D018
  is still required; do not skip it or treat R1 authorization as approval for R2.
- **Boundaries:** Preserve HTTP and factual behavior, supported provider adapters,
  prompts and the accepted laptop/phone interface. The user controls service
  lifecycle. No automatic hosted inference, scraping, network changes or Git
  publication. This improves structure without claiming production readiness.
