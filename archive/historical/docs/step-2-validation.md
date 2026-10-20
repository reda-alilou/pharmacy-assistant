# Step 2: hosted multilingual interpretation

Implementation and offline tests are available. The live acceptance gate passed
on 2026-10-18 using the configured Groq account and Qwen model.
This step adds interpretation; `/chat` and the browser interface are later steps.

## Verified checkpoint

- All 12 live cases completed: 12 correct intent sets, 12 exact entity cases,
  and zero incorrect non-null entities under the smoke suite annotations.
- Median latency: 507.5 ms; range: 375–1,843 ms for the twelve cases, including
  retries. Three cases needed the single permitted retry.
- Groq intermittently returned `json_validate_failed` for valid requests. This
  is now recognized as a provider generation failure and receives at most one
  retry; invalid generated output is never accepted. The initial failed-run
  report is preserved in `reports/interpretation_smoke_qwen_initial.json`.
- The running HTTP endpoint also correctly interpreted `Bch7al AIRCORT?`;
  evidence is in `reports/interpretation_http_smoke.json`.
- All 38 offline tests passed, including the regression check for generation
  failures and the two-attempt ceiling.

Full live responses and metadata are in `reports/interpretation_smoke.json`.
These are development smoke checks, not held-out evaluation or an uptime guarantee.

## Configure the only external dependency

1. Create a free Groq account and a key at <https://console.groq.com/keys>.
2. In the project root, copy `.env.example` to `.env` if `.env` does not already
   exist. Set `GROQ_API_KEY` locally. Do not paste the key into chat or commit it.
3. Keep the other defaults for the first live check:

```dotenv
GROQ_API_KEY=your_key_here
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_TIMEOUT_SECONDS=20
GROQ_MAX_COMPLETION_TOKENS=1200
```

The placeholder above is intentionally treated as unconfigured. The API reads
the project's `.env` at startup; explicit process environment variables take
priority. Restart after editing configuration. Missing credentials do not stop
medication lookup. `/health` reports `interpretation_configured: false` until
a nonblank key is loaded; `true` means configured, not verified with Groq.

The model ID is configurable and there is no automatic model or paid-provider
fallback. Groq currently lists this Qwen model as **Preview**. Strict JSON output
support is documented, but live availability, account access, extraction quality,
and latency must be checked with your own key. [Model documentation](https://console.groq.com/docs/model/qwen/qwen3.8-27b),
[structured output documentation](https://console.groq.com/docs/structured-outputs).

## Start and try the API

```powershell
uv sync --locked
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/docs>, select `POST /interpret`, and send:

```json
{"text": "Wach kayn ABIP 15mg w bch7al?"}
```

The endpoint returns:

- `interpretation.language`, `reply_language`, and `reply_script`.
- An intent list, supporting multiple simultaneous intents.
- Separate medication mentions with `name`, `strength`, requested `quantity`,
  pharmaceutical `form`, and package `presentation`.
- Pharmacy, city, area, date, time, and symptom entities when stated.
- Metadata containing the requested and returned model IDs, prompt version,
  measured latency, number of attempts, completion ID, and token usage.

Unknown fields are `null`, with `[]` when no medication is mentioned. Entity
values are excerpts from the message, preserving units, spelling and number
words. The backend rejects extracted values absent from that message (allowing
Unicode equivalence, case and whitespace differences). This evidence check does
not prove a word was assigned the correct semantic label; live evaluation is
still required. Medication matching and normalization happen in Step 3.

Supported intents: `price`, `availability`, `medication_information`,
`medication_request`, `pharmacy_search`, `pharmacy_contact`, `opening_hours`,
`pharmacy_on_duty`, and `unsupported`. Clinical recommendations and unrelated
requests belong to `unsupported`; this endpoint generates no diagnosis or advice.

Inputs must contain nonblank readable text, with at most 2,000 characters.
Unknown request fields are rejected. Output permits at most ten medication
mentions; incomplete/truncated provider output is rejected rather than accepted.
The schema has no price, stock, or factual-answer fields.

## Error and retry behavior

| HTTP | Error code | Behavior |
| --- | --- | --- |
| 422 | FastAPI validation details | Invalid input; no model request |
| 422 | `provider_refused` | Provider refusal; no retry |
| 429 | `provider_rate_limited` | At most one retry if the supplied cooldown is at most 2 seconds; longer cooldowns are returned in `Retry-After` |
| 502 | `provider_invalid_response` | Invalid schema, unsupported entities, or incomplete output; no retry |
| 502 | `provider_generation_failed` | Groq explicitly reports `json_validate_failed`; one bounded retry, then fail without accepting output |
| 503 | `model_not_configured` | Configure the key and restart |
| 503 | `provider_authentication_failed` / `provider_permission_denied` | Fix key or account access; no retry |
| 503 | `provider_request_rejected` | Check model availability and schema; no retry |
| 503 | `provider_unreachable` / `provider_unavailable` | One bounded retry for connection or transient server errors |
| 504 | `provider_timeout` | One bounded retry, then return failure |

There are at most two attempts total. SDK automatic retries are disabled. Each
attempt has a hard configured timeout, with at most two seconds between attempts.
With defaults this bounds inference to approximately 42 seconds. Returned token
usage describes the successful attempt only; the provider might count additional
usage for a failed attempt. Missing usage is reported as unknown, not zero.

Provider response bodies, raw exceptions, patient text, and credentials are not
included in application error logs or relayed in public error messages.

## Offline verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests use the real Groq SDK with a local mocked HTTP transport. They exercise
the request schema, API validation and error mapping, secret redaction, bounded
retries, timeouts, missing entities, multiple medication mentions, and evidence
validation. They do not contact Groq or establish language-model accuracy.

## Live acceptance check

After configuring the key:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_interpretation
```

This calls the same interpreter directly; a running API server is not required.
The twelve synthetic cases include three each in French, Arabic, Darija and mixed
language, covering multiple intents, multiple drugs, requested quantities,
pharmacy questions, incomplete requests and an unsupported clinical request.
These are smoke checks, separate from the held-out Step 5 evaluation.

Cases are spaced 30 seconds apart to reduce free-tier token-limit pressure.
Actual account limits still apply. The command prints progress, writes
`reports/interpretation_smoke.json` after each case, and stops on provider errors.
Without a key it writes `status: not_run_missing_key`, `passed: false`, makes no
requests, and exits with status 1. Saved responses are never substituted for live
calls. The report preserves actual structured responses for your review.

Acceptance requires all 12 cases to complete, at least 10 correct intent sets,
at least 10 exact entity cases, and no incorrect non-null critical entities.
The entity threshold prevents an extractor returning only nulls from passing.
Missing entities are reported
separately. Inspect the response-language fields and entity bindings manually
before validating the checkpoint. A passing smoke suite is not a general
accuracy guarantee.

## Validation gate

Do not start Step 3 until the live checks pass and the user validates Step 2.
