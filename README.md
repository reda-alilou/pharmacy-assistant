# Multilingual Patient-Pharmacy Assistant

A local Challenge 1 prototype for Moroccan pharmacy requests in French, Arabic,
Darija (Arabic or Latin script), and mixed language. A French React chat talks to
a core FastAPI service, with inference in a separate FastAPI service. Hosted Qwen extracts structured intents and entities; local code resolves
medications, manages clarification and conversation context, calculates prices,
and constructs answers from recorded source facts.

## Run the demo

The current four-container demo uses Docker Desktop and the existing migrated
PostgreSQL volume. Checkpoints 1–5 have been reviewed, including the React interface
on laptop and phone. Final validation and Streamlit retirement remain checkpoint 6.

For this already-configured workspace:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>. The web image has been rebuilt with the React chat.
For future frontend changes, run the same Compose command with `build web` first.
Stop with `down` instead of `up -d --wait`; omit `--volumes` to preserve data.
Startup does not migrate or re-import. Do not run the full stack and database-only
Compose configurations concurrently for the same project.

Fresh setup, explicit imports and runtime credentials are described in the
[Compose guide](docs/architecture-checkpoint-4.md); the new interface and browser
checks are described in [checkpoint 5](docs/architecture-checkpoint-5.md).
New typed questions need internet access and available hosted inference quota;
valid offered choices do not. Never commit `.runtime` or `.env`.

### Retained Streamlit launcher

Streamlit remains available until checkpoint 6. The following is the earlier
host-process workflow, rather than the new React entry point.

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Internet access and an
available Groq API allowance are required for new natural-language messages.

```powershell
git clone https://github.com/reda-alilou/pharmacy-assistant.git
cd pharmacy-assistant
uv sync --frozen
Copy-Item .env.example .env
```

Edit `.env` locally and set `GROQ_API_KEY` to your own key. The example selects:

```dotenv
INFERENCE_PROVIDER=groq
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_OUTPUT_MODE=json_object
INFERENCE_MIN_INTERVAL_SECONDS=0
```

Start the language API, core API, and retained Streamlit interface with one command:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501>. API documentation is at
<http://127.0.0.1:8000/docs>. Ctrl+C stops the services started by the launcher;
existing compatible APIs reused by the launcher are left running.
Use `--api-port`, `--language-port`, and `--ui-port` if the default ports are occupied.
The language API listens on localhost:8001 by default; its docs are at
<http://127.0.0.1:8001/docs>. Stop the earlier demo with Ctrl+C before restarting
after the checkpoint 3 changes; the launcher refuses to reuse an older core API.
The application does not start merely by cloning or importing the project.

Keep `.env` private. Credentials stay on the server and are excluded from Git.
Provider/model switching is explicit; there is no automatic paid fallback or
saved-answer substitution. Optional Gemini and OpenCode adapters are retained,
but historical checks for those providers do not establish current availability.

## Implemented behavior

- Structured language, intent, medication name, strength, form, presentation,
  quantity, pharmacy, location and time extraction with Pydantic validation.
- Multiple intents and medication mentions, exact/reviewed-name normalization,
  substance lookup, and explicit spelling suggestions requiring confirmation.
- Clarification for ambiguous identities, strengths and presentations; offered
  selections are validated server-side rather than accepting arbitrary IDs.
- Follow-ups that retain confirmed medications and presentations. The patient
  interface displays factual results and sources without raw extraction JSON.
- Decimal-based totals for explicit complete-package quantities, with an order
  total only when all medication lines can be calculated.
- Medication cards, source links, recorded prices and commercialization status.
- Partial Rabat pharmacy directory search by name/area, with available phone and
  address details. Unspecified city defaults visibly to Rabat.
- Visible errors for missing credentials, invalid model responses, provider
  failures and quota limits. Artificial message spacing is disabled; actual
  provider cooldowns are respected.

Try a new conversation:

1. `Quel est le prix de ABIP ?`
2. `Lboita dyal 30 3afak`
3. `Et pour deux boîtes ?`

The selected 30-tablet presentation has a recorded unit price of 372.00 MAD;
two complete packages total 744.00 MAD. These are stored observations, not a
live offer. More multilingual checks are in the [manual test guide](docs/arabic-package-fix.md).

## Architecture

Checkpoint 4 Docker Compose integration passed verification and user review.
Checkpoint 5 replaces the placeholder with the React patient chat. The four-container
setup, explicit database tools, isolated failure/restart checks, and debug overlay
are described in [the checkpoint 4 guide](docs/architecture-checkpoint-4.md).
See [checkpoint 5](docs/architecture-checkpoint-5.md) for frontend behavior and evidence.
Do not run full-stack and database-only Compose configurations concurrently for
the same project; both intentionally reuse the checkpoint 2 database volume.

Checkpoint 1 established core, language, and interpretation contract boundaries.
Checkpoint 2's PostgreSQL implementation passed automated checks and user review.
Checkpoint 3 extracts inference into its own HTTP service; see its
[setup and validation](docs/architecture-checkpoint-3.md). File mode remains
available for the legacy fixtures. To use the existing migrated PostgreSQL data:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
$env:STORAGE_BACKEND = "postgres"
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

The user starts/stops PostgreSQL separately. See [checkpoint 2 setup/status](docs/architecture-checkpoint-2.md) and
[checkpoint 1](docs/architecture-checkpoint-1.md) for changes and validation,
and the root [decision log](DECISION_LOG.md) for the agreed target and checkpoints.

```text
React -> Nginx /api -> core FastAPI /chat
          -> HTTP/JSON -> language FastAPI /v1/interpret
                        -> quota reservation -> hosted Qwen extraction
                        -> strict schema and source-span validation
          -> conversation context, catalogue / Rabat directory lookup
          -> deterministic pricing and multilingual answer templates
          -> answer + medication/pharmacy cards + choices + sources
Core and language use separate schemas/credentials in PostgreSQL.
Streamlit remains a separate legacy host-process option until checkpoint 6.
```

New text normally needs one inference request, with at most one bounded retry
for eligible transient failures. Presentation/refinement/reference buttons use
saved server-side state without another model call. Conversation and
clarification state in file mode expires after 15 minutes and is lost on core
restart. PostgreSQL mode persists temporary conversations with a 30-minute
inactivity expiry, restore/reset APIs, and retained failed messages. React restores
the active transcript after refresh and invalidates it on New conversation. Prices and directory
facts come from stored data, not model memory. Core never retries the language
HTTP request or falls back to local inference; offered buttons remain usable
during a language outage when core/database are healthy.

Main API routes:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Loaded catalogue and public inference configuration |
| GET | `/ready` | Core storage readiness without inference |
| POST / GET / DELETE | `/conversation` | Create, restore, or invalidate temporary state |
| POST | `/interpret` | Validated current-message interpretation and metadata |
| POST | `/chat` | Grounded answers, clarification and conversational follow-ups |
| GET | `/medications/search` | Name/substance query with separate filters |
| GET | `/medications/{record_id}` | Stored record and provenance |

The web gateway exposes these routes under `/api`, including `/api/docs`.
Use the generated API documentation for request/response schemas. Run legacy host services
separately if needed:

```powershell
# In separate terminals with the same storage-mode environment:
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.language.api:app --host 127.0.0.1 --port 8001
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m streamlit run src/pharmacy_assistant/demo.py
```

## Data and limitations

| Active local data | Count |
| --- | ---: |
| AMMPS medication presentations | 9,936 |
| Presentations with matched secondary-source observations | 2,700 |
| Medicament.ma observations | 1,008 |
| Saydalia observations | 5,299 |
| Rabat pharmacy records | 327 |

Secondary observation counts are not additional unique medication counts.
Joins require a unique normalized name, strength, form and presentation match;
conflicts retain the AMMPS reference value and preserve source observations.
Of the medication records, 1,126 have no recorded public price. Missing prices
remain unknown. See the [data checkpoint](docs/data-checkpoint.md) and
[accepted collection cutoff](docs/demo-enrichment-cutoff.md).

Collection remains stopped. Runtime lookup does not scrape source sites.
Processed data, parsed AMMPS snapshot JSON and test fixtures are included;
new bulk HTML caches, staging copies, local archives and scratch tools are
excluded from Git. Previously tracked historical raw samples remain available.
Source links and timestamps identify historical observations; including source
material does not imply ownership or a blanket license over third-party data.

This prototype does **not** verify pharmacy stock, opening hours or duty
schedules. Commercialization is not stock availability. Pharmacy coverage is
limited to a partial Rabat directory; geographic distance ranking is not
implemented. Voice input, public deployment and independent real-user validation
are not implemented. It provides no diagnosis or treatment recommendations.

Qwen is accessed through Groq, not self-hosted or trained by this project.
Free hosted inference can be interrupted by quota or service availability.
The extraction model still makes errors; validation and context rules reduce
specific failures but do not establish universal correctness.

## Tests and measured results

Run the offline suite without an API key or live inference:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The GitHub checkpoint verification passed **236 tests**. Coverage includes
lookup, ambiguity, API validation, context, pricing, source parsing, mocked
provider failures, quota handling and the Streamlit client. See the
[verification log](reports/github_checkpoint_tests_verified.log). A clean export
of the staged files, without `.env` or ignored caches, also passed all 236 tests;
see the [checkout log](reports/github_clean_checkout_tests_verified.log) and
[publishing checkpoint](reports/github_checkpoint.json).

Migration evidence is separate from that historical baseline. The checkpoint 4
full suite passed 280 tests; its final offline run passed 270 with ten opt-in
PostgreSQL checks skipped. Checkpoint 5 adds browser and contract checks; see its
[current evidence](docs/architecture-checkpoint-5.md). From `frontend/`, run
`npm ci`, `npm run build`, `npm run lint`, and `npm test` for offline browser checks.
The explicit real-stack verification command is
`.\.venv\Scripts\python.exe -m pharmacy_assistant.compose_verify --run-isolated --frontend`.

The evaluation fixture contains 80 synthetic annotated examples: 40 development
and 40 originally held-out, balanced across four language groups. Annotations
were assistant-authored/reviewed; independent native-speaker review is not claimed.

| Evidence | Result | Interpretation |
| --- | --- | --- |
| Historical frozen held-out run | 34/40 backend scenarios; intent F1 92.86%; entity slot F1 95.91%; 48/48 schema-valid completions | Measured on the earlier frozen version, before the latest corrections |
| Later correction regression | 14/14 backend scenarios; 20/20 schema-valid completions; raw slot F1 85.71% | Six seen failures plus eight fresh variations; not a new independent benchmark |

The corrected backend uses the recorded live model outputs; replay provenance
and earlier failures are retained. Do not describe the targeted 14/14 result as
100% overall accuracy. See the [frozen evaluation](docs/evaluation-checkpoint.md),
[correction report](docs/arabic-package-fix.md) and
[complete regression metrics](reports/matching_package_metrics_complete.json).

Live evaluation is separate, spends quota and requires an explicit request
budget. Existing completed reports must not be overwritten:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_development --output reports/development_new.json --max-requests 4 --interval 20
```

Resume an interrupted run using the same command plus `--resume`. Configuration,
code/data changes or missing request-ledger state reject incompatible resumes.
Saved evaluation reports are evidence, never a demo fallback.

## Challenge deliverables and remaining work

The [requirements audit](docs/challenge-1-requirements-audit.md) maps the written
brief to implementation and evidence. Text-only input meets its text-and/or-voice
wording. The main remaining submission work is a cited related-work study and a
consolidated final project explanation. A five-minute presentation script and
backup screenshots remain presentation preparation work. Historical checkpoint
documents describe their respective versions; this README describes the current
prototype. Further improvements should preserve source provenance, raw model
outputs and honest evaluation boundaries.
