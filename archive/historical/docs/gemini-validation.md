# Gemini provider checkpoint

The selected provider is now `gemini`, using `gemini-3.8-flash`. This changes
hosted interpretation only: medication data, Rabat directory, language templates,
presentation selection and Streamlit remain on the existing backend.

Google currently lists this stable model with free input/output on the Standard
free tier and structured-output support. Live requests succeeded with the locally
configured account. Future availability and quota are account-dependent. Gemini
is proprietary and does not meet the original open-weight
model choice. Google's free-tier pricing table also states that free-tier data
is used to improve its products; use synthetic demo messages.

Official references checked on 2026-10-18:

- [Model capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [Pricing and free-tier data use](https://ai.google.dev/gemini-api/docs/pricing)
- [GenerateContent structured JSON output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
- [API response, usage and error-related fields](https://ai.google.dev/api/generate-content)
- [Creating and configuring API keys](https://ai.google.dev/gemini-api/docs/api-key)

## Local setup

1. Open [Google AI Studio API Keys](https://aistudio.google.com/api-keys), sign in,
   and create a key in a free-tier project. No paid billing activation is part of
   this checkpoint. Existing Cloud users may need to import a project in AI Studio.
2. The provider/model are already selected in the local `.env`. Fill in its
   `GEMINI_API_KEY=` line. Keep the value out of source control, chat and screenshots.

```dotenv
INFERENCE_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
GEMINI_TIMEOUT_SECONDS=30
GEMINI_MAX_OUTPUT_TOKENS=4096
```

`.env.example` contains the same fields without credentials. Other provider keys
are preserved and used only if explicitly selected. This adapter reads
`GEMINI_API_KEY`, not `GOOGLE_API_KEY`. Process environment variables override
the local `.env` file. Restart a running API after changing configuration.

## Implementation

- Uses the existing `httpx` dependency and Google's native `generateContent`
  REST endpoint. The key is sent in `x-goog-api-key`, never in a URL or the UI.
- Sends the shared extraction schema using `generationConfig.responseFormat.text`
  with the REST MIME enum `APPLICATION_JSON` and schema. The guide's string
  `application/json` was rejected by the live REST endpoint and corrected.
  Applies the full Pydantic contract and raw-span
  evidence validation locally, including rules beyond Google's schema subset.
- Uses LOW thinking on Gemini 3 models. Reasoning parts are excluded from results.
- Reports the requested model, returned `modelVersion`, response ID, latency and
  token usage. `completion_tokens` maps to `candidatesTokenCount`; Google's total
  also includes thinking tokens, so the displayed counts need not sum together.
  Usage refers to the successful attempt and does not total failed retries.
- Handles bad keys, permissions, unavailable models, quota, timeouts, connection
  failures, refusals, incomplete output and malformed/invented entities visibly.
- At most one retry for other transient failures. HTTP 429 is now returned
  without automatic retry. Shared local spacing and persistent cooldowns are
  described in the [quota guide](improvement-step-1-quota.md).
- No schema downgrade, automatic provider fallback, billing change or paid fallback.
  A free-tier project is required for the no-cost workflow; the app cannot infer
  a project's billing tier from its key.

## Verification

Offline checks cover the serialized native request, isolated credentials, schema
and evidence checks, actual provider metadata, refusal/error/retry behavior,
hard timeouts and the real `/chat` ABIP clarification flow with source prices.
All provider calls are mocked in these tests; no server is launched.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The provider checkpoint passed 97 tests, including 10 Gemini tests; the subsequent
quota checkpoint passes 119. The first sandboxed
run hit Windows temporary-directory permissions in existing fixture tests; the
same suite was rerun with temporary-directory access. After correcting the REST
MIME enum, the live run passed all 12 cases: 12 correct intent sets, 12 exact
entity cases, and no incorrect non-null entities. Each language group (French,
Arabic, Darija and mixed) passed all three cases. One case used the adapter's
single bounded retry; the other eleven succeeded on their first attempt.
Median extraction latency was 3.38 seconds, with a 2.42–24.89 second range.
These small checks do not establish general accuracy.

Five additional real Gemini chat flows passed through FastAPI in process, with
no listening server: Darija price/stock, ABIP presentation clarification and
selection, unknown medication, missing price, and a Rabat pharmacy contact.
Returned medication records were compared with the canonical record endpoint.
ABIP's box of 30 returned 372 MAD, and an unrelated record selection was rejected.
The valid follow-up required no new inference call. Stock remained unknown.

Evidence:

- [Extraction report](../reports/interpretation_smoke_gemini.json)
- [Five live chat flows](../reports/chat_smoke_gemini.json)
- [Checkpoint, language-group counts and latency](../reports/gemini_checkpoint.json)
- [Initial integration rejection, preserved separately](../reports/interpretation_smoke_gemini_initial_request_rejected.json)

To repeat the existing 12-case multilingual smoke check, run it directly
without starting API or UI services:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_interpretation --max-requests 4
# Repeat later to continue the same report:
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_interpretation --resume --max-requests 4
```

New resumable runs use `reports/interpretation_budgeted_gemini.json`. The previous
`reports/interpretation_smoke_gemini.json` remains historical evidence from before
the quota changes. Acceptance requires all 12 cases completed, at least
10 correct intent sets and 10 exact entity cases, and no incorrect non-null
entities. This small development check is separate from Step 5's held-out evaluation.

Start the demo yourself after validation:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open http://127.0.0.1:8501. Ctrl+C stops the services owned by the launcher.
No demo services were started during this provider checkpoint.
