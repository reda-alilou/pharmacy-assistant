# Checkpoint 3 — Independent language service over HTTP

Status: **implemented, verified, and reviewed by the user**. The user reported
the demo works and explicitly authorized checkpoint 4.
Checkpoint 2 was accepted after the user tested the PostgreSQL-backed demo and
reported it worked seamlessly. The user then authorized checkpoint 3. No new
architecture decision was needed; this implements D001, D002, D004, D015, and
D018. Stop for review before checkpoint 4.

## Ownership and request flow

```text
Streamlit -> core API :8000 -> HTTP/JSON -> language API :8001 -> hosted provider
                 |                             |
                 v                             v
          PostgreSQL core schema        PostgreSQL language schema
```

| Component | Owns |
| --- | --- |
| `api.py`, `transport/language.py` | Core HTTP routes and a single-attempt HTTP interpreter client |
| `core/` | Context, temporary conversations, clarification, matching, pharmacy lookup, pricing, and factual answers |
| `language/api.py`, `language/inference.py` | Independent FastAPI application, provider selection, validation, and quota handling |
| `contracts/` | Shared Pydantic message/response/error/health contracts; no service implementations |
| `config.py` | Separate runtime `CoreSettings` and `LanguageSettings`; combined legacy `Settings` only for explicit tools/fixtures |

Core imports no language implementations or provider SDKs and cannot fall back to
in-process inference. Its settings contain only its database URL, storage mode,
language origin, and HTTP deadline. Language settings contain provider options,
its own database URL, and quota settings; they contain no core database URL.
Each loader selects only owned fields from the existing configuration sources.
The launcher filters credentials from child environments by responsibility.
Full container build/runtime isolation is checkpoint 4.

The retained legacy root adapter imports and direct evaluation tools still work.
They are explicit tools, not a core runtime fallback. Provider/model selection,
prompt, strict extraction/evidence checks, data, matching, and pricing are unchanged.

## Internal contract

| Language route | Behavior |
| --- | --- |
| `GET /health` | Liveness and public provider/model/configured/storage metadata, service=`language`, contract_version=1; no inference or quota reservation |
| `GET /ready` | Checks configured key and access to quota state; never sends a provider request or reserves an attempt |
| `POST /v1/interpret` | Strict `{ "text": "current typed message" }` -> existing `InterpretationResponse` |

Only the current message crosses from core to language. Conversation tokens,
transcript, catalogue facts, prices, database credentials, and provider keys are
not included. Core keeps its existing `/interpret` route as an HTTP proxy through
the same client, alongside `/chat`, catalogue, and conversation routes.

Both success and error payloads are validated. Core rechecks source-span evidence
and rejects malformed JSON, invalid metadata, unknown fields, invented entities,
unexpected status/code combinations, redirects, and responses over 64 KiB.
Known error codes map to fixed French messages; remote/provider free text is never
relayed. Cooldown seconds and `Retry-After` survive the boundary. Invalid language
request bodies get a short error without echoing patient input.

## Waiting, quotas, and failures

- Core sends **one HTTP attempt**, with no retry, provider SDK, or local fallback.
  Redirects and environment proxy inheritance are disabled for this internal link.
  Connect/pool waits are 2 seconds; the overall deadline defaults to 160 seconds.
- Language owns the existing provider policy: SDK retries disabled, at most one
  adapter retry for eligible transient failures, no retry on 429 or invalid
  extraction. Its total request deadline is twice the configured provider timeout
  plus 25 seconds, including quota work. With the current 20-second Groq setting,
  that is 65 seconds; the maximum supported provider setting gives 145 seconds.
  The retained demo client waits at most 175 seconds for a chat response.
- The same PostgreSQL quota scopes, reservations, and cooldown rows continue to
  apply across language processes. No counters or historical ledgers are reset.
  A quota-storage failure blocks inference and returns 503.
- A disconnect or deadline may happen after the provider accepted work. No layer
  automatically replays that HTTP request; the error explains possible accounting
  and requires an explicit manual retry. Exactly-once provider billing is not
  promised. Existing conversation request IDs still guard successful publications.
- Core can start and serve catalogue, restoration, reset, and valid offered
  choices while language is unavailable. Its `/health` remains a core liveness
  response and reports `language_service_status` separately, using a bounded
  one-second probe. This does not claim provider availability or remaining quota.
- In PostgreSQL mode, failed user messages remain in the temporary transcript;
  failures and restoration do not extend expiry or advance successful context.
  A valid clarification selection does not contact language or consume quota.

## Run and review on this laptop

Leave the user-managed PostgreSQL container running. Stop the previous demo in
its own terminal with Ctrl+C, then from the repository root:

```powershell
$env:DATABASE_ENV_FILE = (Resolve-Path .runtime/postgres.env).Path
$env:STORAGE_BACKEND = "postgres"
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501>. The command now starts three processes: language API,
core API, and retained Streamlit. It reuses compatible existing APIs and leaves
them running on exit; it terminates only children it started. It refuses to reuse
an older core API or an API using a different language origin/storage mode.
PostgreSQL is never started/stopped by this launcher.

Optional overrides: `--language-port`, `--api-port`, and `--ui-port`, or set
`LANGUAGE_SERVICE_URL` to an existing internal HTTP(S) origin. Default language
port is 8001. Restart services after changing their configuration.

Review flow: ask `Quel est le prix de ABIP ?`, choose the 15 mg presentation with
30 tablets, then ask `Et pour deux boîtes ?`. Expected stored unit price is
372.00 MAD and total is 744.00 MAD. Core docs: <http://127.0.0.1:8000/docs>;
language docs: <http://127.0.0.1:8001/docs>.

For a manual outage check, run language and core in separate terminals using the
same PostgreSQL environment:

```powershell
# Terminal 1:
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.language.api:app --host 127.0.0.1 --port 8001
# Terminal 2:
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000
# Terminal 3:
.\.venv\Scripts\python.exe -m streamlit run src/pharmacy_assistant/demo.py
```

Get clarification choices, stop language with Ctrl+C, then choose an offered
presentation. That action should still work. A new typed request should produce
a clear language-service error. Restart language to continue typed requests.

Streamlit remains temporary: the React UI, transcript restoration after browser
refresh, and new-conversation wiring belong to checkpoint 5. Full Compose
integration belongs to checkpoint 4; neither was started here.

## Validation

Automated HTTP checks use real FastAPI routes and JSON serialization with mocked
hosted transport; one check uses an ephemeral loopback Uvicorn language listener
and the production HTTP client. PostgreSQL checks create/drop only their own
uniquely named disposable database. They cover both APIs with persistent failed
messages, restore, inference-free selection during outage, recovery to a 744.00
MAD total, and shared PostgreSQL cooldowns. No hosted inference is performed.

Final suite: **275 passed, no skips, 55.099 seconds**, including ten real
PostgreSQL checks. Offline lock verification and source/wheel builds passed.
Source medication/pharmacy input hashes and tracked historical evidence remain
unchanged. Final suite/build results are in `reports/architecture_checkpoint3_status.json`
and `reports/architecture_checkpoint3_final_verified.log`. Earlier diagnostic
logs are retained separately. No application data import, schema migration,
provider change, Git commit, or user demo startup is part of this checkpoint.
