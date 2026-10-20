# Pharmacy Assistant: current implemented state

Verified 2026-10-20. Read this before exploring the repository. Paths below are
relative to the repo; Python module names are relative to
`src/pharmacy_assistant/`. This is a state snapshot, not authorization to execute
its example commands. Verify current Git/config state before acting.

## Architecture migration progress

Checkpoints 1–5 of `DECISION_LOG.md` D018 are implemented and reviewed.
The user tested the PostgreSQL-backed demo, reported it worked seamlessly, and
explicitly authorized checkpoint 3. The user then tested checkpoint 3, reported
it works, and authorized checkpoint 4. Checkpoint 4 Docker/Compose implementation and
real container verification passed. The user started four healthy containers,
confirmed the placeholder in the browser, and authorized checkpoint 5. React is
now implemented and verified, including the user-run isolated real-stack test.
The user confirmed it works and the interface is clean on both laptop and phone.
Checkpoint 6 has not started; await authorization to continue. Current guide:
`docs/architecture-checkpoint-5.md`;
container setup: `docs/architecture-checkpoint-4.md`; checkpoint 3:
`docs/architecture-checkpoint-3.md`; earlier implementation/evidence:
`docs/architecture-checkpoint-1.md`, `docs/architecture-checkpoint-2.md`.
Final decisions in `DECISION_LOG.md` supersede the earlier architecture draft.

- Implementations now live in `src/pharmacy_assistant/core/`, `language/`, and
  `contracts/`. Existing root module names are compatibility imports; the module
  map below still identifies responsibilities but new code uses these packages.
- Core conversation logic raises framework-independent `ChatError`; `api.py`
  translates it to the existing 410/422 HTTP responses. Core imports no provider
  adapters, FastAPI, or collection code. `Interpreter` lives in `contracts/`.
- `PharmacyRecord` now lives in `core/pharmacy_models.py`, imported by the collector.
  Repository paths are centralized in `paths.py`; settings/data locations persist.
- Evaluation guards now include nested Python implementation files. Historical
  data, annotations, reports, and frozen evidence are preserved.
- Inference now runs in its own FastAPI language service over HTTP/JSON.
  Core has no provider SDK or in-process fallback. React is now the patient UI;
  Streamlit remains available until checkpoint 6. File mode retains JSONL and 15-minute memory-only state for the
  original demo/fixtures. Explicit PostgreSQL mode loads relational catalogue
  records and provides the approved 30-minute persistent conversations.
- Fresh offline baseline: 236 tests passed; six architecture checks were added.
  Full post-change suite: 242 passed / 39.807s,
  `reports/architecture_checkpoint1_tests.log`. Offline lock check and package
  build passed. Normal Windows permissions were needed for temp/SQLite tests.
- Checkpoint 2 offline data profile: `reports/architecture_checkpoint2_data_profile.json`.
  Proposed exact formulation grouping yields 7,302 groups for 9,936 presentations;
  3,128 linked secondary observations and 1,260 conflicts remain distinct rows.
  Schema approval is recorded in D019; the database has now been imported and
  all public medication/pharmacy records passed full round-trip validation.
- Checkpoint 2 adds service-owned SQLAlchemy models, independent Alembic histories,
  transactional import/reconstruction, PostgreSQL quota storage, temporary
  conversation persistence/resume/reset, and explicit setup/backup tools. Driver
  is Psycopg; request-side synchronous operations use worker threads.
- Existing `.env` is unchanged. File mode remains the default for the retained
  demo/fixtures. An ignored `.runtime/postgres.env` supplies credentials and selects
  PostgreSQL when explicitly loaded through `DATABASE_ENV_FILE`. Do not print it.
  The isolated database uses port 55432; the unrelated native PostgreSQL service
  is untouched. The user controls database/demo startup and shutdown.
- Checkpoint 2 final complete suite: 260 passed / 50.402s, no skips,
  `reports/architecture_checkpoint2_final_verified.log`, including nine real
  PostgreSQL checks. Lock/build and offline SQL checks passed. Actual application
  import, repeat import, permissions, source hashes, conservative two-scope quota
  import, and backup/restore passed. See `reports/architecture_checkpoint2_validation.json`
  and `reports/architecture_checkpoint2_application_smoke.json` (mocked inference,
  no hosted calls). No demo API/UI was started; the user owns database shutdown.
  The user subsequently reviewed and accepted checkpoint 2.

- Checkpoint 3 adds `language/api.py` (`/health`, `/ready`, `/v1/interpret`) and
  `transport/language.py` (core's only inference adapter). Core forwards current
  text only; language owns strict validation, provider retries, and quotas. Both
  APIs run independently. Existing root provider imports remain for explicit tools.
- Runtime configuration is now separate: `CoreSettings` has only core storage and
  language URL/deadline; `LanguageSettings` has its provider/quota settings and
  language storage. Neither contains the other service's database credential.
  Legacy combined `Settings` remains for import/evaluation tools and fixtures.
- Core performs no HTTP retries and no fallback. Language retains the existing
  at-most-two provider-attempt policy. HTTP errors are sanitized French contracts;
  cooldowns survive the boundary. Failed PostgreSQL turns remain restorable, and
  existing valid offered choices work during language outages without inference.
- `run_demo` now starts language :8001, core :8000, and Streamlit :8501, reuses
  compatible APIs without stopping them, and refuses the earlier in-process core.
  The user must stop the earlier demo and rerun; the agent does not restart it.
  Database startup/shutdown remains user-controlled. Containers are checkpoint 4.
- Checkpoint 3 final suite: 275 passed / 55.099s, no skips, including ten real
  PostgreSQL checks and an ephemeral loopback HTTP check. Offline lock/build pass.
  See `reports/architecture_checkpoint3_status.json` and
  `reports/architecture_checkpoint3_final_verified.log` for final suite evidence.
  Hosted inference is mocked, including HTTP/JSON and PostgreSQL recovery checks.
  No provider/model/prompt or catalogue changes. The user reviewed and accepted it.

- Checkpoint 4 adds `deploy/compose.yaml` (web/core/language/postgres), separate
  runtime image targets and dependency groups, an allowlist `.dockerignore`,
  internal default API/database ports, optional `compose.debug.yaml` host access,
  and an explicit short-lived database-setup profile. It reuses the existing
  `pharmacy-assistant-architecture_postgres_data` volume; startup never migrates
  or imports automatically. Checkpoint 5 replaces its original placeholder with React.
- Core `/ready` now checks its own database tables without language/inference or
  expiry renewal. Nginx forwards `/api/*`, preserves application errors/cooldowns,
  disables retries, and resolves Docker DNS again after core replacement.
- `compose_setup` created ignored `.runtime/compose.env` from the existing
  credentials/provider settings without overwriting passwords or resetting quota
  scopes. Runtime credentials are service-specific. Never print either ignored
  env file or expanded Compose `config`; use `config --quiet`.
- The user must explicitly run `compose_verify --run-isolated` after image builds
  to control a temporary test stack's startup/replacement/shutdown. That utility
  uses only generated credentials, disables language internet egress, seeds one
  synthetic clarification offline, tests outages/persistence/proxy behavior, and
  removes only its own unique project/volume. It never touches the application
  volume, calls hosted inference, or adds a runtime fixture/fallback.
- The agent has not started/stopped the application stack. The user restarted
  Docker Desktop once during image-download troubleshooting. Downloads partially
  progressed, but Docker/GitHub CDN addresses in 198.18.x.x still timed out.
  Read-only diagnosis found inconsistent router DNS answers. The user approved
  a temporary Wi-Fi DNS change to public DNS; all image builds then passed and
  the original automatic DNS setting was restored. Core/language/tools offline
  image smoke checks passed. No application stack was started by the agent.
- Checkpoint 4 verification passed: 280 full regression tests before the Docker
  restart; final offline run 270 passed / ten opt-in PostgreSQL tests skipped
  because the host database was stopped. An initial isolated startup check found
  an incorrect readiness column reference; corrected to `source_record_id` and
  images rebuilt. The final user-run isolated stack passed all eight checks,
  including gateway/OpenAPI routing, service/credential/network isolation,
  language/core/database outages, inference-free choice, failed-message restore,
  cooldown headers, Docker DNS recovery, and volume persistence after replacement.
  It removed its own containers/networks/volume; application data was untouched.
- Checkpoint 4 is implemented/verified and subsequently reviewed. Historical evidence:
  `reports/architecture_checkpoint4_status.json` and
  `reports/architecture_checkpoint4_container_validation.json`. Its status report
  predates the user's successful startup and acceptance.

- Checkpoint 5 adds React/TypeScript/Vite, Tailwind and shadcn/ui controls in
  `frontend/`. It implements French chat, inline medication/pharmacy cards,
  sources/dates, server-computed totals, offered choices, safe errors, and a
  confirmed New conversation action. Off-white/teal styling has no gradients or
  decorative card side strips. No sidebar, permanent history or language switch.
- Only the active token/expiry and a separate cooldown deadline use sessionStorage;
  transcript/context remain in PostgreSQL with the same 30-minute inactivity
  expiry. Refresh restores without inference or expiry renewal. No automatic POST
  retry: uncertain completion gets one GET reconciliation, then manual recovery.
  Failed text remains visible; offered choices remain usable during cooldowns.
- Generated OpenAPI request types and runtime patient-response validation align
  the browser with core, without loading runtime credentials into frontend assets.
  The web image now builds static React assets through a frozen npm install and
  serves them via the same Nginx `/api` gateway. The web image is rebuilt.
- Twenty offline browser tests pass, including responsive checks and zero Axe
  violations for tested views. Production build/lint pass (two nonfatal shadcn
  hot-refresh warnings). Offline Python lock and package builds pass. The final
  Python regressions passed 270 with ten opt-in host PostgreSQL skips; both new
  contract/fixture tests passed separately (272 passes across the two runs). The
  user-run isolated stack passed all nine checks, including React against real
  core/PostgreSQL, then removed its temporary resources. See
  `reports/architecture_checkpoint5_status.json`. The user controls
  `compose_verify --run-isolated --frontend` and
  application startup. No hosted inference, scraping or application data changes.
- The user confirmed the React UI works, then requested phone testing. Optional
  `deploy/compose.phone.yaml` binds only web to `PHONE_HOST_IP` (Wi-Fi IPv4), with
  localhost still the default when omitted. HTTP LAN-compatible cryptographic
  request IDs are covered by an added browser regression. See `frontend/README.md`
  for enable/restore commands. The user controls rebinding web; no application
  service, firewall or network setting was changed by the agent for phone testing.
  The user subsequently confirmed phone access works and the interface is clean
  on both devices, completing checkpoint 5 review.
- Checkpoint 6 has not started; keep Streamlit until final representative
  validation in that checkpoint. No new architecture decision or Git commit/push.

## 1. Verified repository snapshot

- Environment: Windows/PowerShell, Python virtual environment `.venv`, timezone
  Africa/Casablanca. Repo:
  `C:\Users\REDA\Desktop\COURSES\Challenge camp\Challenge 1\pharmacy-assistant`.
- Active branch: `refactor/web-architecture`; application baseline:
  `0b7adb1b8eed60b9e5d43da8a4d6bfceb79b797e` (published prototype).
  Checkpoints 1–4 were subsequently committed/pushed as `cecab2f`. Checkpoint 5
  changes are currently uncommitted; no Git publication is implied by validation.
- Remote: `https://github.com/reda-alilou/pharmacy-assistant.git`; `master` was
  verified at that commit after publication. This is the pre-migration baseline;
  checkpoint 1 changes application organization, while data/evidence are preserved.
- Collection is stopped. Runtime requests use stored local data; no collection
  process is part of application startup.
- This file describes implemented functionality, configuration, data and evidence
  as verified on the date above. It contains no credentials.

## 2. Purpose and implemented scope

Challenge 1: Moroccan patient-pharmacy assistance; short/incomplete French, Arabic,
Darija (Latin/Arabic script), and code-mixed requests become structured intents and
entities through an API. The model interprets requests; local data/code provide
facts and arithmetic. Source brief: Challenge 1, pages 1-2 of
`C:\Users\REDA\Desktop\COURSES\Challenge camp\Challenges.pdf` (outside Git).

Implemented: local text demo, multilingual extraction, grounding, clarification,
follow-ups, package totals, partial Rabat pharmacy search/contact, source attribution
and evaluation. Qwen weights are Apache-2.0/open-weight; this application calls
Groq-hosted inference and does not train or locally host the model.

Current boundaries: text-only; Rabat-only partial pharmacy coverage; no distance
ranking, live stock, verified opening hours/duty, or diagnosis/treatment advice.
Independent real-user validation, public deployment and production-level
security/load/availability assurance have not been established.

## 3. Current runtime and configuration

```text
Browser -> React + Nginx localhost:8080 /api -> core FastAPI :8000 /chat
 -> HTTP/JSON -> language FastAPI :8001 /v1/interpret
 -> quota reservation + Groq/Qwen extraction of CURRENT MESSAGE ONLY
 -> strict Pydantic schema + source-span evidence validation (language and core)
 -> local context merge -> medication resolution / Rabat directory
 -> Decimal pricing -> reviewed language templates
 -> answer + medication/pharmacy cards + offered choices + sources
Core/language -> PostgreSQL :5432, separate owned schemas/credentials
```

- Four Compose containers: web, core FastAPI, language FastAPI and PostgreSQL.
  Only web is exposed by default. The retained `run_demo` host launcher starts
  Streamlit :8501/core :8000/language :8001 separately. Core owns
  catalogue/directory/ChatService and an HTTP interpreter; language owns provider
  clients and quota state. Both close their own clients at shutdown.
- Runtime facts: file mode loads `data/processed/*.jsonl`; PostgreSQL mode
  reconstructs records from related tables into the same in-memory indices.
  Neither mode scrapes at runtime. SQLite is the legacy file-mode quota/evaluation
  ledger, not a conversation/medication store. PostgreSQL mode uses `core` for
  facts/temporary conversations and `language` for quotas and future budgets.
- Selected config verified without printing secrets: provider `groq`, model
  `qwen/qwen3.8-27b`, mode `json_object`, timeout 20s, completion cap 1200,
  minimum local interval 0; key configured. This is not a promise of current quota.
- `config.py`: service-owned runtime settings select only their fields from explicit root `.env`, UTF-8/BOM support, interpolation disabled;
  OS environment overrides file; keys use `SecretStr`. IMPORTANT: class provider
  default is still `gemini`; root `.env.example` explicitly selects Groq. A missing
  `.env` does not imply Groq. Configuration changes require relevant service restarts by user.
- `contracts/interpreter.py`: `Interpreter` Protocol (`interpret`, `close`). Core
  uses `transport/language.py` only. `language/inference.py` selects the hosted
  adapter; no automatic fallback. Root `inference.py` remains a compatibility alias
  for explicit evaluation tools.
- Current prompt: `nlu.py`, `step9-package-selection-v1`. Temperature 0;
  Qwen reasoning_effort=none; not streaming. Normally one model request/message.
  JSON-object mode appends full schema to prompt. Provider-enforced `json_schema`
  remains supported but observed Arabic generation failures motivated explicit
  JSON-object mode plus mandatory strict LOCAL validation; no silent downgrade.
- Groq SDK retries disabled; adapter allows at most one retry for eligible transient
  errors with short delays. 429 returns immediately and records shared cooldown;
  invalid/refused returned extraction is not retried until successful. Metadata:
  requested/actual model, prompt version, latency, attempts, completion ID, usage.
  Usage covers successful attempt, not necessarily all failed-attempt token costs.
- Provider history: Groq/Qwen -> OpenCode GLM (`glm-5.3-flash-free`, direct access
  restricted in prior test) -> Gemini (`gemini-3.8-flash`, daily quota exhausted)
  -> current Groq/Qwen. Earlier reports are historical, not current provider status.
  A new key in the same organization does not reset organizational limits.

Python >=3.12; `.python-version`=3.12; uv/uv_build; locked direct versions:
FastAPI 0.141.1, Pydantic 2.13.5, Streamlit 1.66.0, Groq 1.7.0, httpx 0.28.1,
requests 2.34.2, python-dotenv 1.2.3, BeautifulSoup4 4.15.0, Uvicorn 0.53.0.
Checkpoint 2 adds SQLAlchemy 2.1.5, Alembic 1.20.0, and Psycopg 3.3.6 (binary).

## 4. Public contracts and state

`nlu_models.py`: strict extra-forbidden extraction; text 1-2000 characters,
non-whitespace; entity spans max 200; <=10 medication mentions; unique intents.
Required nullable entity fields mean unknown=null, not omitted/invented.

```text
Interpretation:
 language = fr|ar|darija|mixed|unknown
 reply_language = fr|ar|darija; reply_script = latin|arabic
 intents[] = price|availability|medication_information|medication_request|
             pharmacy_search|pharmacy_contact|opening_hours|pharmacy_on_duty|unsupported
 entities.medications[] = {name,strength,quantity,form,presentation} (nullable spans)
 entities.{pharmacy,city,area,date,time,symptom} = nullable spans
```

Every non-null raw entity must occur in current input after Unicode/whitespace
normalization. Empty mentions rejected. This prevents absent-span inventions,
NOT incorrect semantic labeling of a present word. Model never receives prices
or answers from memory on our behalf; reply generation is local templates.

API (`api.py`, `create_app(dataset,settings,pharmacy_dataset)`):

| Route | Behavior |
| --- | --- |
| GET `/health` | Catalogue file/count/brand count + public model/provider/configured flag; no inference call. |
| GET `/medications/search?query=...` | Name/substance search; optional separate strength/form/presentation; whitespace invalid; returns matches/suggestions/not_found and partial-scope wording. |
| GET `/medications/{record_id}` | Full stored medication or 404 partial-catalogue wording; static search route registered first. |
| POST `/interpret` | `{text}` -> `{interpretation,metadata}`. No context merge. |
| POST `/chat` | Grounded orchestration; modes below; `/docs` exposes schemas. |

Chat request modes (`chat_models.py`; mutually exclusive, strict validation):

```json
{"text":"Quel est le prix de ABIP ?"}
{"text":"Et pour deux boites ?","session_id":"LATEST_RESPONSE_SESSION_TOKEN"}
{"session_id":"TOKEN","reference_index":0}
{"continuation_id":"TOKEN","selections":[{"mention_index":0,"record_id":"9080"}]}
{"continuation_id":"TOKEN","refinements":[{"mention_index":0,"field":"presentation","value":"EXACT_OFFERED_VALUE"}]}
```

Tokens above are placeholders, not valid examples of real server state. Refinement
fields: strength/form/presentation/brand_name/page. One action per mention; page
must match offered next offset. Only offered candidates/options accepted; arbitrary
IDs/values or cross-mention choices fail 422. Expired/lost state fails 410.

Chat response: answered|needs_clarification; raw interpretation; per-medication
results (resolved/ambiguous/suggestions/not_found/missing_name/filters_not_matched);
pharmacy result; answer; source links/timestamps/record IDs; inference metadata and
inference_performed; continuation token/expiry; session token/expiry; order_pricing;
context {effective_interpretation,inherited_fields,normalized_fields,needs_reference,
reference_options,action}. Raw and effective interpretations MUST remain distinct.
Error responses use sanitized detail {code,message,retryable,retry_after_seconds};
provider errors map to 429/502/503/504, refusal 422; routing validation also uses 422.
Retry-After header is supplied when known. Never expose raw provider error bodies.

Legacy file-mode state (`chat.py`, `conversation.py`): in-memory OrderedDicts for sessions
and pending choices, TTL 900s, capacity 128 each, oldest eviction. New reply returns
a new session token; UI must attach LATEST SUCCESSFUL RESPONSE token, not stale
cached token. Choices/refinements/reference buttons need zero extra inference;
typed follow-up/typed ordinal normally still invokes model. Restarts lose state;
multiple API workers do not share it. Expiry uses process monotonic time and is local to the running API process.
Confirmed anchors come from selected records, not rejected model filters. A new
named drug avoids unrelated inherited filters; changing form/strength clears
incompatible inherited fields. Multiple possible antecedents require reference
clarification. Reviewed complete ordinal phrases may select offered candidates.
Pharmacy city/name changes avoid carrying incompatible area/name constraints.

PostgreSQL mode wraps this engine using `core/storage/`: versioned validated JSON
snapshots, hashed tokens, parent conversation expiry 30 minutes after a successful
interaction, transaction/revision guards, transcript restore, reset, and cleanup.
`POST /conversation` creates state; GET/DELETE use an Authorization bearer token.
Optional `/chat` request_id supports deduplication with a valid conversation token.
`/health` reports storage_backend. Full contract details and activation commands
are in `docs/architecture-checkpoint-2.md`; frontend restore/reset wiring is later.

## 5. Domain invariants and recent fixes

- `catalog.py` search is a compatibility API, not identical to chat's ranked
  `resolution.py`; the two interfaces have distinct matching behavior.
- Identity priority: exact brand -> exact substance -> partial -> fuzzy. Reviewed
  Arabic/Darija aliases live in `medication_normalization.py`; aliases are finite.
  Fuzzy/confirmation-required aliases do not silently select even a lone candidate.
- Match strength/form/presentation separately. Do not confuse 5mg/15mg, 20/200,
  or packaging with pharmaceutical form. Never invent missing units.
- No exact filtered match: retain explicitly unselected recovery candidates with
  conflict metadata (strength/form/presentation penalties 4/2/1); require user
  confirmation. >5 candidates trigger grouped refinements/pagination. Record IDs
  identify PRESENTATIONS: two packages of one brand must remain distinct.
- `pricing.py`: explicit quantities only; multilingual words/digits/Arabic duals;
  bounded 1..1000 packages. Quantities mean COMPLETE catalogue presentations,
  not tablets or model-calculated unit conversions. Specific flacon/tube requests
  must fit the actual presentation container. None != 1; unclear plural != 1.
  Decimal(str(price)), ROUND_HALF_UP to cents; API totals are two-decimal strings.
  Order total only if EVERY line is calculable; unresolved/missing-price lines
  cannot produce a guessed partial grand total.
- Latest corrections: Ventoline/Augmentin reviewed Arabic spellings; package counts
  separated from strength/order quantity in prompt; explicit Arabic indefinite
  singular package quantities can mean one. Definite references like `lboita`
  are NOT automatically one. A narrowly bounded context rule clears mistaken
  definite-container quantities on unnamed presentation follow-ups and can inherit
  prior price intent; records normalized_fields, leaves raw extraction untouched.
- `pharmacy_directory.py`: Rabat default disclosed; other city -> outside_coverage.
  Exact/reviewed name then whole-token matching; optional area aliases/filter.
  Multiple named matches remain ambiguous. Results alphabetical, <=5 displayed,
  actual count/truncation reported; coordinates do not imply nearest ranking.
- Price/commercialization/stock are different. Stock ALWAYS unknown; hours unknown;
  duty unverified. Preserve these limitations in any new UI. Clinical requests
  get a brief boundary response. Missing in this catalogue != does not exist.
- The retained Streamlit interface displays raw extraction JSON, effective context,
  pricing diagnostics and sources in expandable panels. React instead shows the
  patient answer, structured factual cards and readable sources without raw JSON.

## 6. Active data and provenance

| `data/processed/` file | Current meaning/count |
| --- | --- |
| `ammps_medications_enriched.jsonl` | Runtime catalogue: 9,936 presentations; 2,700 with secondary observations; 1,126 missing public price. |
| `medicament_medications.jsonl` | 1,008 secondary observations; not additional unique runtime medicines. |
| `saydalia_medications.jsonl` | 5,299 secondary observations; same caveat. |
| `pharmacies_rabat.jsonl` | 327 Rabat records; partial directory. |
| `pharmacy_duty_observations.jsonl` | 327 historical raw map-duty observations, explicitly unverified; not a duty schedule/runtime authority. |
| `ammps_medications.jsonl` | Older basic processed sample; NOT the active enriched catalogue. |

AMMPS snapshot: 497 pages, 9,936 unique records; complete for that observed listing,
not a guarantee of complete/current Moroccan market data. Secondary enrichment is
incomplete and deliberately stopped at user-approved cutoff. Do not blindly rebuild
active data from old basic/detailed samples or assume all local artifacts are active.

`models.py` Medication core: numeric-string source_record_id; brand, substance, epi,
dosage, form, presentation, commercialization; nullable public/hospital/PFHT prices;
authorization/class/tax/RCP/NAF fields; official page/URLs/fetch timestamp; nullable
ATC/reimbursement; source_observations[] and data_conflicts[]. Stored prices are
validated floats; arithmetic uses Decimal.
Official URLs accept BOTH basic `/recherche-medicaments?page=N` and detailed
`/basesdedonnes/liste_marocaine_des_medicaments?page=N`. RCP/NAF may be text, not URLs.
Secondary observations preserve source ID/URL/time, price/status/reimbursement/ATC.
Unique normalized brand+strength+form+package joins only; AMMPS price/status retained,
disagreement recorded, no fuzzy automatic data merges. Unmatched observations stay
separate. Counts across sources overlap; never sum them as unique medication count.

PharmacyRecord now lives in `core/pharmacy_models.py`: ID `saydalia:<id>`,
name/city/address/phone, lat/lng, optional opening text, source and request URLs,
fetch timestamp, directory scope. Runtime and collection use the same model.

Raw artifacts: `data/raw/ammps_snapshot/{manifest.json,page_N.json}` required by
foundation tests/source checks; local page_N.html/.meta.json exist but are ignored.
Old tracked `data/raw/ammps/` and `ammps_detailed/` samples remain historical.
Three tracked parser fixtures in `data/raw/source_discovery/`:
`ammps_live_1.html`, `medicament_detail_2.html`, `saydalia_medications.html`.
Ignored: other discovery pages, newer source caches, staging trees, processed archives.
Local ignored archives/staging may not exist in another checkout. Backups/collection
manifests record provenance; no further downloads are required to run the demo/tests.

## 7. Code navigation (read the relevant row, not every file)

| Modules (all under package root) | Responsibility |
| --- | --- |
| `api.py`, `models.py`, `nlu_models.py`, `chat_models.py` | ASGI startup/routes; catalogue, interpretation and chat contracts. |
| `core/chat.py`, `core/conversation.py`, `core/errors.py` | Orchestration/state, contextual inheritance, selection; framework-independent application errors mapped by `api.py`. |
| `catalog.py`, `resolution.py`, `medication_normalization.py` | Loaded indices, compatibility search, ranked matching/refinement, aliases/units/forms/packages. |
| `pharmacy_directory.py`, `pharmacy_normalization.py` | Directory lookup and reviewed name/area normalization. |
| `pricing.py`, `answer_templates.py` | Explicit-package arithmetic; French/Arabic/Darija Latin+Arabic templates. No second answer-generation call. |
| `config.py`, `inference.py`, `nlu.py`, `gemini_nlu.py`, `opencode_nlu.py` | Settings, adapter Protocol/factory, hosted inference and sanitized failures. |
| `quota.py`, `evaluation_state.py` | SQLite atomic reservations/shared cooldowns/durable budgets; live-run fingerprints and OS file locks. |
| `demo.py`, `demo_client.py`, `run_demo.py` | Streamlit UI/HTTP errors+request client; launcher for API/UI. Client has some historical provider-specific wording. |
| `ammps.py`, `collect_ammps.py`, `collect_ammps_detailed.py`, `parse_ammps.py`, `parse_ammps_detailed.py`, `build_ammps_dataset.py`, `process_ammps.py`, `enrich_ammps.py`, `search_medications.py` | Original collection/parsing/processing/enrichment/search tools; inspect defaults before using. |
| `collect_ammps_snapshot.py`, `collection_http.py` | Complete fresh official snapshot; bounded per-source HTTP, cache metadata, atomic writes/redaction. NOT runtime scraping. |
| `supplementary_sources.py`, `collect_rabat_pharmacies.py`, `build_reference_data.py` | Secondary parsers/collection; pharmacy normalization; conservative source linking and provenance. |
| `expand_medications.py`, `expand_pharmacies.py`, `run_collection_expansion.py`, `review_collection_expansion.py` | Capped/resumable staged expansion, grid/city collection and audits; stopped, not a deployment dependency. |
| `prepare_demo_enrichment.py`, `activate_demo_enrichment.py`, `quality_ammps.py` | Offline candidate prep/validation; controlled backup/activation; schema/source/price/uniqueness checks. Do not rerun activation as routine startup. |
| `evaluation_dataset.py`, `baseline_metrics.py`, `evaluate_baseline.py` | Frozen fixture validation; span/intent scoring; annotated-extraction oracle vs live baseline modes. |
| `evaluate_development.py`, `evaluate_held_out.py`, `evaluation_freeze.py`, `merge_development_rechecks.py`, `report_live_evaluation.py` | Durable-budget live capture + real backend replay; held-out freeze guards; explicit recheck history; corrected metrics. |
| `evaluate_interpretation.py`, `evaluate_chat_smoke.py`, `evaluate_conversation_smoke.py`, `evaluate_pharmacy_smoke.py`, `evaluate_demo_smoke.py` | Earlier focused live smoke tools, some resumable; spend quota unless specifically mocked/offline. |
| `__init__.py` | Initial package/CLI stub; `pharmacy-assistant` entry point is not the demo launcher. |

## 8. Tests and evaluation: do not confuse the measurements

The published prototype had 22 `tests/test_*.py` files; checkpoints add
`test_architecture_boundaries.py`, `test_storage_contracts.py`, and
`test_postgres_storage.py`. Tests use unittest, mocked inference and source
fixtures; no live API
key needed. Coverage: catalogue/quality/API validation, matching, state/refinement,
Streamlit/client session flow, quantity math, pharmacy names, all provider adapters,
quota concurrency/failures, evaluation budgets/locks/freeze/resume, parsers/imports.
No tests rerun to write this handoff. Last published verification:
- 236 passed / 37.503s: `reports/github_checkpoint_tests_verified.log`.
- Clean staged export WITHOUT `.env` or ignored caches: 236 / 38.268s,
  `reports/github_clean_checkout_tests_verified.log`. Used existing locked Python
  environment/PYTHONPATH, not a fresh independent dependency install.
- `uv lock --check --offline` passed; staged known-key scan clean; frozen annotation
  hashes and evidence bytes preserved. Summary: `reports/github_checkpoint.json`.

Baseline fixture `data/evaluation/baseline_v1/`: manifest + development.json (40)
+ held_out.json (40). Each: 10/group (fr,ar,darija,mixed), 32 standalone +8 followups;
8 setup calls means 48 accepted outputs per complete split. Synthetic assistant-
authored/reviewed, no independent speaker/inter-annotator review. Entities are RAW
CURRENT-MESSAGE spans; follow-up intent labels can describe contextual intent.
Score raw slots + effective dialogue intents; inherited identities evaluated by
backend resolution. Null matches do not inflate slot F1; wrong span -> FP+FN.

| Evidence | Results and meaning |
| --- | --- |
| Development first pass | 39/40 backend; slot F1 .9793, intent 1.0; later 6 targeted rechecks addressed time-vs-date/container-vs-form. |
| Reviewed development history | 40/40, combining 42 earlier outputs +6 newer-prompt outputs; NOT a uniform-prompt independent benchmark. |
| Original frozen held-out | 34/40 backend; medication decisions 25/31; intent P/R/F1 .928571; entity P .964706/R .953488/F1 .959064; schema 48/48; 49 attempts incl. one HTTP429; median adapter 797ms/p95 1625ms. |
| Held-out groups | Intent F1 fr .9091/ar 1/darija .9/mixed .9091; entity F1 1/1/.8837/.9545; outcomes 10/10,8/10,8/10,8/10. |
| Later correction regression | `matching_regressions_v1.json`: 6 seen failures +8 fresh variations, 14/14 backend, 20/20 valid model outputs (6 setup turns); intent 1, raw slot .857143; median 882.5ms/p95 1703ms. Development evidence, NOT new independent overall accuracy. |

Original held-out used prompt `step8-temporal-packaging-v1`, frozen before execution.
Failures: 4 Arabic Ventoline/Augmentin identity aliases; 2 box-of-40 follow-ups
misread as strength. Extra unnamed-order intent disagreement did not break backend.
Latest step9 fixes address these; stricter scorer rejects unnecessary clarification
even when correct record returned. 14/14 does not mean perfect raw extraction.
Regression run retained 11 accepted outputs via documented BACKEND-ONLY replay,
then completed remaining live calls; cumulative 24 reserved attempts =20 accepted,
2 historical HTTP429,2 sandbox connection failures. No live jobs remain pending.

Primary evidence (retain original files):
- `docs/evaluation-checkpoint.md`, `reports/held_out_qwen_frozen_v1.json`,
  `reports/held_out_qwen_frozen_metrics.json`, `reports/qwen_evaluation_freeze.json`.
- `docs/arabic-package-fix.md`, `reports/matching_package_live_v{1,2}.json`,
  `reports/matching_package_metrics_complete.json`, `matching_package_checkpoint.json`.
- Original partial metrics/checkpoints/quota diagnostics remain historical.
  `reports/matching_alias_offline_replay.json` =38/40 using OLD saved model outputs
  after alias changes; `matching_package_backend_oracle.json`=14/14 using GOLD
  extraction. Neither is fresh model accuracy.
- Targets .90 intent/.85 slots/.80 per-language intent were evaluation targets,
  not numeric requirements in the PDF; original frozen extraction met them.
- Held-out examples are now SEEN data after inspection/tuning. The original freeze
  belongs to the earlier code version; current correction checks are development
  regressions, not an independent benchmark of the current version.

## 9. Commands and operational traps

Commands are for the USER to run unless execution explicitly requested. Repo root:

```powershell
uv sync --frozen
# Fresh checkout ONLY: Copy-Item .env.example .env ; user fills key locally.
# Do not overwrite an existing configured .env.
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
# UI http://127.0.0.1:8501 ; API/docs http://127.0.0.1:8000/docs
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pharmacy_assistant.quota
```

Launcher starts localhost API/UI, reuses compatible existing API, errors on occupied
UI port; Ctrl+C stops only owned processes. Supports --api-port/--ui-port. Do not
assume processes are running from old screenshots/reports; check without stopping.

Quota CLI sends no inference. SQLite contains counters/timestamps/provider-model
scope/budgets, no prompts/keys/responses. Scope is scope:provider:model, not key;
changing key does not clear local cooldown. Do not delete ledger/reset cooldown to
force requests; accepted saved evaluation + missing ledger rejects unsafe resume.
Provider limits change; do not hardcode historical quotas as current guarantees.

Optional live example, ONLY with authorized request budget and NEW output path:
```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_development --output reports/development_new.json --max-requests 4 --interval 20
```
--resume skips accepted jobs; fingerprint/provenance/ledger guard model/prompt/schema/
config/code/data changes. Explicit --examples supports development-only fixtures;
--case-ids supports development targeting. Held-out command requires compatible
freeze/full split; do not rerun historical held-out as a new independent benchmark.
`report_live_evaluation SOURCE --output NEW_METRICS` scores offline (add
--split held_out for historical held-out). Oracle: `evaluate_baseline offline`
uses annotated extraction, not model performance; choose a new --output path.

Environment pitfalls:
- Restricted Windows test sandboxes previously failed temp directory/SQLite access;
  same unchanged suite passed with normal permissions. API connection failures in
  sandbox also occurred; don't diagnose invalid credentials from transport errors.
  Distinguish permission/network restrictions from actual provider/logic failures.
- `.gitattributes` preserves EXACT bytes of evaluation fixtures, processed JSONL,
  parsed snapshot JSON and reports. Earlier Git normalization broke manifest hashes
  in an export; fixed with byte-preserving attributes/restaging, then clean tests.
  Do not normalize line endings/reformat frozen evidence or silently update hashes.
- `.gitignore`: .env (except example), .runtime, .venv, IDE files, report locks,
  tmp/, interrupted reports/tmp*/, processed/archive/, data/staging/, new raw
  HTML/meta/cache trees. Old tracked raw samples still tracked. Never git-add -f
  local secrets/cache directories. Some ignored interrupted test dirs may deny access.
- repo-relative ROOT paths use `Path(__file__).resolve().parents[2]`; moving modules
  breaks data/config paths unless configuration is explicitly redesigned.

## 10. Useful recorded examples (not live stock/current retail guarantees)

| ID | Presentation | Stored public MAD |
| --- | --- | ---: |
| 9079 | ABIP 15mg, box20 tablets; Non Commercialise | 268.00 |
| 9080 | ABIP 15mg, box30 tablets; Commercialise | 372.00 |
| 4262 | ACOL 1000mg, box30 | 18.30 |
| 1972 | VENTOLINE 100 micrograms/dose, 200-dose inhaler | 42.20 |
| 1974 | VENTOLINE 2mg, box40 tablets; Retire du Marche | 18.70 |
| 1790/1791/1792 | AUGMENTIN 1g/125mg sachets, box12/16/24 | 118.00/157.20/207.00 |

Validated flow: ABIP price -> Darija box30 -> French two boxes =744.00; retaining
latest session token fixed lost-presentation bug. Mixed order: 2xABIP box30 +3xACOL
box30 =744.00+54.90=798.90; user successfully combined this with Arabic request for
Pharmacie Ibn Nafis Rabat contact. Box40 VENTOLINE follow-up ->18.70; two boxes
->37.40; status remains withdrawn. Wrong AUGMENTIN 2g/125mg must clarify, not
silently use 1g/125mg. Missing name/price stays unknown, no invented fact.

## 11. Focused reference guide

- Startup and current overview: `README.md`.
- Runtime: API/chat contracts and module map in sections 4 and 7.
- Data provenance and accepted collection cutoff: `docs/data-checkpoint.md`,
  `docs/demo-enrichment-cutoff.md`, `reports/demo_enrichment_activation.json`.
- Evaluation: section 8's original frozen results and later correction results;
  they measure different versions/scenarios and are not interchangeable.
- Requirements assessment: `docs/challenge-1-requirements-audit.md`.
- `docs/step-*`, `docs/improvement-step-*`, provider and collection reports describe
  their historical versions. Some status/setup statements are superseded by the
  current code and README; their original measurements remain historical evidence.
- Source snapshots support parsing/provenance tests. Reading hundreds of raw pages
  is unnecessary for understanding application behavior.
