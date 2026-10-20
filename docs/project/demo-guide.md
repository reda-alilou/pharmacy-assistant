# Demo guide and spoken presentation

Prepared 2026-10-20 for the current four-container laptop demo. The narration is
in English; patient prompts are in French, matching the interface. Suggested
length: 7–9 minutes. The presenter runs all lifecycle commands.

## 1. Prepare before presenting

Open Docker Desktop and wait until its engine is running. In PowerShell, from
the project root, run:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml ps
```

The four normal services should be healthy: `web`, `core`, `language`, `postgres`.
Open these pages:

- Patient interface: <http://127.0.0.1:8080>
- Core API documentation: <http://127.0.0.1:8080/api/docs>
- Architecture diagram: `PROJECT_CONTEXT.md`, section 2, in Markdown preview.
- Database relationships/table descriptions: the same file, section 6.

The existing images and database are already prepared. Documentation-only
changes do not require rebuilding, migrating or importing. New typed questions
use the configured hosted provider and require its availability/internet access.
Rehearse the exact prompts once beforehand, then use “Nouvelle conversation”
to begin the presentation with an empty chat. Keep private `.env` and runtime
credential files closed while sharing your screen.

Optional read-only health summary, without model inference:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/health | Format-List
```

This shows configuration/availability information, not a guarantee that the next
provider request will succeed. Do not run full verification or collect fresh data
as part of the presentation.

## 2. Live demonstration: exactly what to ask

Perform the essential medication flow first. Pharmacy/limits examples can be
skipped if time is short. Wording may vary because extraction is hosted; the
listed prices and contacts are verified saved facts, not newly checked live facts.

| Step | Type or click | Expected behavior and what to point out |
| --- | --- | --- |
| 1 | Type **`Quel est le prix de ABIP 15 mg ?`** | The catalogue contains two presentations. Point out that the app asks which package the patient means rather than silently picking one |
| 2 | Click the offered **box of 30 tablets** (`BOITE DE 30 COMPRIMES PELLICULES`) | Selected presentation is record `9080`, recorded public price **372.00 MAD**. A button selection reuses saved interpretation and makes no new model call |
| 3 | Type **`Et pour deux boîtes ?`** | Core inherits the selected medication; expected total **744.00 MAD**. New typed text does use extraction; multiplication uses local Decimal arithmetic |
| 4 | Open **Sources et détails** | Show source attribution and collection dates. Explain that source dates qualify the information; prices are recorded observations |
| 5 | Refresh the page | Transcript, selected context and total return. Refresh restores server state; it does not repeat the question or call the model |
| 6 | Click **Nouvelle conversation** and confirm if prompted | Previous conversation is invalidated on the server; the interface clears only after reset succeeds |
| 7 | Type **`Quel est le numéro de téléphone de la pharmacie Ibn Nafis à Rabat ?`** | Show the matching pharmacy/contact card. Saved source phone: **0537720657** (`saydalia:5256`). This is a recorded contact, not a reachability guarantee |
| 8, optional | Type **`Est-ce que la pharmacie Ibn Nafis à Rabat est ouverte maintenant ?`** | Show that current opening hours are unknown/unverified rather than an invented answer |

If you select the box of **20** instead, its recorded price is **268.00 MAD** and
two boxes total **536.00 MAD**. Select the box of 30 consistently if following
the narration below.

If the provider is unavailable or rate-limited, explain the displayed error and
cooldown. Do not repeatedly submit the same text. Use the recorded test evidence
to discuss verified behavior, clearly separating it from what ran live. A saved
offered choice may still work without language inference while core/database are
healthy; that does not make arbitrary new typed questions work offline.

## 3. Spoken script with screen cues

The quoted paragraphs are the words to say. The action lines are presenter cues.
Adjust the phrasing to your own voice; the technical claims match the current
implementation.

### Opening — show the empty patient chat

> “This project is a patient–pharmacy assistant for Moroccan medication requests.
> It is a local challenge demo and a learning project where I practiced separate
> services, Docker and a relational database.
>
> The interface is a French chat. The patient can ask about recorded medication
> prices and product details, clarify a presentation, calculate a package total,
> or look up a pharmacy in our partial Rabat directory.
>
> The key design choice is that the language model interprets the question, while
> the application retrieves facts and builds the answer. The model is not our
> source of prices or pharmacy contacts.”

### Medication flow — perform steps 1–3

> “I’ll ask for the price of ABIP 15 milligrams. Here, the name and strength are
> not enough: there are two different package sizes. The application asks me to
> choose instead of assuming which one I want.
>
> I’ll select the box of 30. Its recorded price is 372 dirhams. This selection
> uses an option already offered by the server, so it does not need another
> language-model request.
>
> Now I’ll ask, ‘And for two boxes?’ The new message is interpreted, and the core
> service combines it with the selected medication from the conversation.
> It calculates 372 times two locally, giving 744 dirhams. That calculation is
> deterministic code, not arithmetic delegated to the model.”

### Sources and temporary state — perform steps 4–6

> “Each result includes its sources and available collection dates. These are
> stored observations, so I don’t present the price as a live offer or claim that
> the medication is in stock.
>
> I can refresh and recover the transcript and current context from PostgreSQL.
> Refresh does not resend my question or spend another model request.
> Conversations are temporary: they expire after 30 minutes without a successful
> turn. Starting a new conversation invalidates the old one on the server.”

### Pharmacy and limits — perform steps 7–8 if time permits

> “The same interface can retrieve a recorded pharmacy contact in Rabat. Here is
> Ibn Nafis with the phone number stored in our directory.
>
> However, having its contact details does not tell us whether it is open now,
> on duty today, or holding a particular medication in stock. The application
> keeps those limits explicit. It also does not diagnose conditions or recommend
> treatment.”

### Architecture — show PROJECT_CONTEXT section 2 and optionally Compose services

> “The application runs as four normal containers: web, core, language and
> PostgreSQL.
>
> The web container serves the built React and TypeScript interface through
> Nginx. The browser sends requests to the same web address under `/api`, and
> Nginx forwards them to the core FastAPI service. The browser never connects
> directly to the database or receives a provider API key.
>
> Core owns the conversation, matching, pharmacy lookup, pricing and final
> answer templates. For a new typed message, it calls the separate language
> FastAPI service over HTTP using a defined JSON contract.
>
> Language calls the configured hosted provider—our selected setup uses Qwen
> through Groq—and validates the structured output. It checks both the schema
> and whether extracted entity values actually appear in the message. It returns
> an interpretation, not a generated factual answer.
>
> Core then merges valid conversation context, searches its loaded records,
> calculates any totals and saves the result. Keeping language separate gives
> us a clear place for provider adapters, timeouts and quota handling, while
> medication and pharmacy logic stay together in core.”

### Database — show section 6's relationship diagram/table overview

> “We use one PostgreSQL database with two service-owned schemas, called core
> and language. Each service has separate runtime credentials restricted to its
> own schema. They communicate through the language API instead of reading each
> other’s tables. They still share one database server, so this is not independent
> database availability.
>
> The core schema separates medication identities from presentations. One
> medication group can have multiple package presentations, and each presentation
> keeps its original source ID. Related tables store price types, source
> observations and disagreements. Pharmacies have their own table, and temporary
> conversations have related messages, session state and pending choices.
>
> Language stores shared attempt counters, cooldowns and evaluation budgets.
> It reserves an attempt before calling the provider so concurrent processes
> cannot independently ignore the same quota state.
>
> SQLAlchemy handles the tables and queries, psycopg connects to PostgreSQL,
> and each service has its own Alembic migration history. Migrations and imports
> are explicit setup steps; restarting the application does not recreate or
> re-import the database.”

### Data pipeline — show section 7

> “The data was collected before runtime. AMMPS supplied the reference snapshot
> of 9,936 medication presentations. Medicament.ma and Saydalia supplied secondary
> observations, and Saydalia supplied our 327-record Rabat pharmacy directory.
>
> We saved source responses, URLs, timestamps and hashes, then parsed and
> validated the records. Secondary medication observations were linked only
> when normalized name, strength, form and package identified exactly one
> reference presentation. Ambiguous or unmatched observations were kept separate.
>
> AMMPS prices and statuses were preserved. Differing secondary values became
> recorded disagreements rather than silently replacing the reference. Missing
> prices remain unknown, not zero.
>
> The two validated JSONL inputs are imported into related PostgreSQL tables.
> The importer reconstructs the records and checks that their facts are
> preserved before committing. At startup, core loads the catalogue and directory
> from PostgreSQL and builds in-memory matching indexes. Conversations and quotas
> continue to use database transactions during requests. There is no scraping
> during a chat.”

### Repository structure — show the root folders, then the two service packages

> “The repository is organized around ownership. `apps/web` contains the
> frontend. Its source separates the application shell, chat and result features,
> and shared API and UI code.
>
> `services/core` and `services/language` are independently installable Python
> packages, each with its own settings, dependencies, tests, Dockerfile and
> migrations. Inside core, HTTP routes are separate from conversations,
> medication logic, pharmacy lookup and PostgreSQL storage. Language separates
> extraction, provider adapters, quota control and storage.
>
> `packages` contains the small shared contracts and infrastructure libraries.
> `tools` contains explicit operations and evaluation commands. `deploy` contains
> Compose and Nginx configuration. `data` contains active import and evaluation
> inputs; `archive` preserves historical evidence. Current generated outputs go
> into ignored artifacts, and private configuration stays outside Git.
>
> One uv lockfile coordinates the six Python packages, while the frontend has
> its own npm lockfile. The root PROJECT_CONTEXT file documents the whole system
> so another developer or AI agent can understand it without scanning everything.”

### Verification and close — show docs/validation/cleanup-r7.md if needed

> “The final engineering validation passed 247 offline Python tests, 22 browser
> tests, ten full-stack verification scenarios and 18 real PostgreSQL tests.
> These cover behavior such as clarification, refresh and reset, concurrent
> quotas, service outages, persistent container replacement and backup restore.
>
> Those automated checks mock model inference. They establish application
> behavior, not perfect language-model accuracy. Earlier live model evaluations
> are preserved separately with their version and dataset limits.
>
> The result is a working local demonstration with clear service boundaries,
> traceable data and tested failure behavior. It remains a learning project,
> not a production or clinically validated service.”

## 4. File-opening order for the technical walkthrough

You do not need to open every implementation file. Use this small sequence:

| Open | Show/explain |
| --- | --- |
| `PROJECT_CONTEXT.md`, section 2 | Full architecture diagram and ownership |
| `deploy/compose.yaml` | Four normal services; only web published by default; persistent volume |
| `services/core/src/pharmacy_core/api/routes/chat.py` | Thin HTTP entry point |
| `services/core/src/pharmacy_core/clients/language.py` | HTTP contract boundary and no core-side replay |
| `services/language/src/pharmacy_language/extraction/prompt.py` | Extraction instructions, not final-answer generation |
| `PROJECT_CONTEXT.md`, section 6 | Schema relationships and tables |
| `services/core/src/pharmacy_core/storage/postgres/models.py` | Concrete relational constraints if questioned |
| `PROJECT_CONTEXT.md`, sections 7–8 | Data lineage and complete structure |
| `docs/validation/cleanup-r7.md` | Verification results and their limits |

If asked why these technologies: FastAPI preserves the tested Python/Pydantic
logic; PostgreSQL suits related catalogue/provenance/state data; React/TypeScript
supports the structured chat; Docker Compose provides reproducible local service
operation. The language split is also a deliberate learning investment, not a
claim that current traffic needs independently scaled microservices.

## 5. Stop after the presentation

From the project root, run:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml down
```

This removes the containers/network while preserving the named database volume.
Do not add `--volumes` when keeping the current database.
