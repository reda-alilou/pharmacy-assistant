# Multilingual Patient-Pharmacy Assistant

A local Challenge 1 prototype for Moroccan pharmacy requests in French, Arabic,
Darija (Arabic or Latin script), and mixed language. A Streamlit client talks to
FastAPI. Hosted Qwen extracts structured intents and entities; local code resolves
medications, manages clarification and conversation context, calculates prices,
and constructs answers from recorded source facts.

## Run the demo

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

Start both local services with one command:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501>. API documentation is at
<http://127.0.0.1:8000/docs>. Ctrl+C stops the services started by the launcher;
an existing compatible API reused by the launcher is left running.
Use `--api-port` and `--ui-port` if the default ports are occupied.
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
- Follow-ups that retain confirmed medications and presentations. Raw extraction,
  inherited fields and bounded context corrections are displayed separately.
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

```text
Streamlit -> FastAPI /chat
          -> hosted Qwen intent/entity extraction
          -> local schema and source-span validation
          -> conversation context and medication resolution
          -> local catalogue / Rabat directory lookup
          -> deterministic pricing and multilingual answer templates
          -> answer + raw JSON + effective context + sources
```

New text normally needs one inference request, with at most one bounded retry
for eligible transient failures. Presentation/refinement/reference buttons use
saved server-side state without another model call. Conversation and
clarification state expires after 15 minutes and is lost on API restart.
Prices and directory facts come from local data, not model memory.

Main API routes:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Loaded catalogue and public inference configuration |
| POST | `/interpret` | Validated current-message interpretation and metadata |
| POST | `/chat` | Grounded answers, clarification and conversational follow-ups |
| GET | `/medications/search` | Name/substance query with separate filters |
| GET | `/medications/{record_id}` | Stored record and provenance |

Use the generated API documentation for request/response schemas. Run services
separately if needed:

```powershell
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
