# OpenCode GLM provider checkpoint

**Live result after key configuration: blocked by OpenCode's free-tier policy.**
The direct GLM request returned HTTP 403 with `error.type=FreeTierError` and the
message "OpenCode's free tier can only be used from within OpenCode."
The 12-case suite stopped on its first request; no interpretation completed, so
GLM quality, latency and direct JSON-schema support remain unmeasured.
Changing schema mode or retrying cannot resolve this access-policy rejection.
The adapter now reports `provider_free_tier_restricted` without retry or fallback.
No payment, client-identity spoofing, or access-restriction workaround was attempted.

The user selected OpenCode GLM as the next inference provider. The backend now
selects providers through `inference.create_interpreter`; medication lookup,
grounding, templates, clarification state and the Streamlit interface use the
same contracts as before. No services are left running after verification.

## Selected configuration

The local `.env` selects this model. The user has now filled in the key locally;
the example below intentionally omits it:

```dotenv
INFERENCE_PROVIDER=opencode
OPENCODE_API_KEY=
OPENCODE_MODEL=glm-5.3-flash-free
```

The existing Groq key was preserved. It is never sent to OpenCode and does not
count as a configured key for the selected provider. Add an OpenCode API key
locally to `OPENCODE_API_KEY`; do not put it in chat, reports, or source control.
The tracked `.env.example` documents both providers. Process environment variables
override file configuration.

The adapter sends requests to the documented
`https://opencode.ai/inference/openai/v1/chat/completions` endpoint. It does not
follow redirects, change models, use a paid model as fallback, or switch back to
Groq automatically. A payment/credit-required response is shown as a visible
`provider_payment_required` error, with no billing action taken.

Defaults: 30 seconds per attempt, 2,048 completion tokens, non-streaming JSON,
and at most one bounded retry for transient provider failures. The GLM model card
documents `reasoning_effort=low`; that budget is requested for this extraction
task. Long provider cooldowns are returned to the caller rather than retried
early. Refusals, truncation, invalid schema/entities and missing metadata are
rejected. Raw provider error text is neither relayed nor logged.

## Structured output: requested versus verified

Default `OPENCODE_OUTPUT_MODE=json_schema` requests the same strict schema used
with Groq. **Actual GLM endpoint support is unverified until a live key test.**
OpenCode's coding-agent SDK structured-output feature uses a tool and validation
retries; it does not itself establish strict-schema support on the direct API.
An unsupported schema/output format returns a visible configuration error.

There is also an explicitly configurable `OPENCODE_OUTPUT_MODE=json_object`
option. That mode includes the full schema in the prompt and applies the same
strict Pydantic and raw-span evidence validation locally, but does not claim
provider-enforced JSON-schema decoding. It is never selected automatically after
a failed strict request. Metadata and the UI show the requested mode.

Every successful interpretation reports `provider`, requested and actual model
IDs, requested output mode, attempts, latency, completion ID and token usage.
`/health` reports the selected provider/model and whether that provider's key is
present; it is not a live authentication or model-availability check.

## Verify once the key is configured

First run the direct extraction suite, without starting either service:

```powershell
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.evaluate_interpretation --output reports/interpretation_smoke_opencode.json
```

It makes real provider requests and checks the same 12 balanced French, Arabic,
Darija and mixed-language fixtures used for the earlier Qwen checks. It records
errors and stops on a provider failure. The previous Groq report remains intact;
new default report names include the selected provider. Missing-key reports are
labelled `not_run_missing_key`, with no inference results or success claim.

After reviewing live extraction, start the demo yourself:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501>. Source details display `opencode` and the actual
returned model. Ctrl+C stops the services started by the launcher. End-to-end
chat and Streamlit smoke scripts remain available, but should use separate
output report paths to preserve the earlier Qwen evidence.

To deliberately return to the prior provider, set `INFERENCE_PROVIDER=groq` and
restart. This is an explicit configuration choice, not an automatic fallback.

## Evidence and remaining work

Offline tests cover correct credentials/endpoint/schema, provider selection,
local validation, metadata, absence of fallback, auth/payment/redirect errors,
rate-limit handling, timeouts, refusals and bounded retries. Live quality, speed
and reliability are **not measured yet**, because the provider denied direct
free-tier access despite the key being configured.
The earlier Qwen scores are historical and do not describe GLM.

The earlier offline checkpoint passed 86 tests. A new check covers the observed
`FreeTierError` policy rejection. `reports/interpretation_smoke_opencode.json`
records the stopped live attempt; the checkpoint report records the diagnosis.
All credentials are omitted from reports. Neither demo service was started.

Official references checked on 2026-10-18:

- [OpenCode catalogue and endpoints](https://opencode.ai/v2/docs/console/models/):
  GLM-5.3-Flash Free is a limited-time offer; its stated data policy is
  zero-retention with no use for training. Free availability is not guaranteed.
- [Official GLM-5.3-Flash model card](https://huggingface.co/zai-org/GLM-5.3-Flash)
  and [license](https://huggingface.co/zai-org/GLM-5.3-Flash/blob/main/LICENSE):
  published weights are labelled MIT; the model card documents thinking budgets.
  The demo uses hosted inference and does not download or train those weights.
- [OpenCode SDK structured output](https://opencode.ai/docs/sdk/#structured-output):
  SDK-level structured output is separate from direct-endpoint schema support.
