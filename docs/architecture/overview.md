# Processing and service ownership

The patient interface is a French React/TypeScript chat. Nginx serves its static
assets and forwards same-origin `/api` requests to core. Core and language are
separate FastAPI services. A single PostgreSQL instance stores their independent
schemas with separate credentials; neither running service accesses the other's
tables or imports its implementation.

```mermaid
flowchart LR
    Browser[React chat] --> Gateway[Nginx /api]
    Gateway --> Core[Core FastAPI]
    Core -->|HTTP/JSON interpretation| Language[Language FastAPI]
    Language -->|Budgeted extraction| Hosted[Hosted provider]
    Core --> CoreSchema[(PostgreSQL core schema)]
    Language --> LanguageSchema[(PostgreSQL language schema)]
```

## One question

1. The browser sends text, its temporary conversation token and a unique request
   ID to core. The token stays in tab session storage; conversation content is
   restored from the server through a read-only request.
2. Core obtains a validated interpretation from language over HTTP. Core has no
   provider SDK, in-process inference fallback or automatic HTTP retry.
3. Language reserves an attempt in PostgreSQL before contacting the configured
   provider. It applies shared spacing/cooldowns, permits only bounded eligible
   transient retries and validates schema plus source-span evidence. Provider
   errors are sanitized before crossing service boundaries.
4. Core separates extracted current-message spans from inherited context. It
   resolves medication identity, strength, form and presentation against recorded
   facts, or produces explicit clarification choices. Partial pharmacy matching
   uses the local Rabat directory. It does not scrape during a request.
5. Deterministic code calculates complete-package totals from stored prices using
   decimal rules, builds source-aware answers and saves temporary state. The
   model is not the authority for prices, pharmacy contacts or stock claims.
6. React displays the response, medication/pharmacy cards, sources and current
   choices. It formats server amounts without doing price arithmetic.

Offered choices use validated saved state and can avoid inference entirely.
Missing prices remain unknown. Ambiguous products are never silently substituted.
Provider/model selection is explicit, with no paid or automatic provider fallback.

## Temporary state and failures

PostgreSQL stores conversation state and transcript with a 30-minute inactivity
expiry. Refresh and read-only restoration never renew expiry or resend a question.
The browser never automatically repeats a POST. An uncertain result triggers a
read-only status check; pending work requires explicit verification. Failed text
remains visible with explicit retry/edit controls. Reset clears local state only
after server invalidation succeeds or the conversation has already expired.

Core's readiness checks its own storage independently of inference availability.
Language outages prevent new text interpretation but valid offered choices can
remain usable. Missing/unavailable PostgreSQL fails startup/readiness clearly;
neither service selects a file or SQLite fallback. Temporary memory resources
are available only through explicit offline tooling/test injection.

## Code boundaries

Core owns `api/`, `conversation/`, `medications/`, `pharmacies/`, `clients/` and
`storage/postgres/`. Language owns `api/`, `extraction/`, `providers/`, `quota/`
and `storage/postgres/`. Each service owns its settings, tables, migration history,
dependency manifest, image and tests.

`pharmacy-contracts` contains schemas, protocols and errors. Shared infrastructure
contains environment/connection/path helpers and read-only archive resolution;
it owns no business rules or tables. Maintenance and evaluation packages may
depend explicitly on both services, but services do not depend on those tools.

The virtual uv root coordinates six installable members and one lockfile. The
four normal containers are web, core, language and PostgreSQL. The operations
image runs only explicit setup jobs. Only web is exposed by default; phone/debug
overlays are explicit opt-ins. See [setup](../operations/setup.md),
[administration](../operations/tooling.md), [evaluation](../development/evaluation-tools.md)
and [finalized decisions](../../DECISION_LOG.md).
