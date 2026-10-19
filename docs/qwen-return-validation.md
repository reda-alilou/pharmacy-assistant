# Groq/Qwen selected again

The local `.env` now explicitly selects Groq and `qwen/qwen3.8-27b`. Existing
provider keys were preserved. No API/UI service was started or stopped. The
artificial message delay stays disabled.

```dotenv
INFERENCE_PROVIDER=groq
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_OUTPUT_MODE=json_object
INFERENCE_MIN_INTERVAL_SECONDS=0
```

## Output mode and validation

Qwen's initial strict-schema run handled the ABIP lookup and presentation choice,
but omitted the quantity in the third turn. A small prompt clarification now
requires unnamed quantity fragments to retain a medication object with a null
name. Prompt version is `step7-quantity-fragments-v2`.

The revised strict-mode ABIP flow passed. However, the Arabic pharmacy request
repeatedly returned HTTP 400 `json_validate_failed`. A bounded diagnostic found
very short malformed JSON in the provider's failed generations, not a key error.
Historical failures remain in the `qwen_return_*` reports rather than being
overwritten or relabelled as successful.

The selected configuration therefore uses **explicit JSON-object mode** with the
full schema supplied in the prompt. This differs from the original provider-
enforced strict-schema setting. Every response still passes strict local
Pydantic schema validation and the raw-message entity-evidence check before it
can reach retrieval. Invalid values, unexpected fields, missing schema fields
and invented/non-evidenced entities are rejected. Model prices are never used.

`GROQ_OUTPUT_MODE=json_schema` remains available and is the code-level default
when no output mode is specified. There is **no automatic mode downgrade or
provider/model fallback**. The local file and tracked example explicitly select
`json_object`, and metadata/UI source details report that actual mode.

## Verified results

The final configured adapter passed four live requests in four provider attempts:

| Request | Observed behavior | Adapter latency |
|---|---|---:|
| French ABIP price | Both stored presentations offered | 953 ms |
| Darija box-30 follow-up | Record 9080 selected, unit price 372 MAD | 797 ms |
| French two-box follow-up | 2 × 372 = 744 MAD | 547 ms |
| Arabic Ibn Nafis contact | Unique record `saydalia:5256`, stored phone 0537720657, Arabic reply | 1047 ms |

Evidence: [final conversation report](../reports/qwen_return_conversation_json.json),
[final Arabic chat report](../reports/qwen_return_arabic_pharmacy_json.json),
[checkpoint](../reports/qwen_return_checkpoint.json).
These are development smoke checks, including a previously observed failure used
to clarify the prompt. They do not establish general model accuracy, a new F1
score, sustained reliability or a latency guarantee. Held-out cases were not run.

All **202 offline tests pass**. The two new adapter tests verify explicit output-
mode transmission/metadata and continued rejection of invented entities, extra
fields and invalid schema in JSON-object mode. Existing tests continue to verify
provider-enforced strict mode. Tests used mocked inference.

Earlier attempts in this migration are also recorded: the first strict conversation
run failed, its revised run passed, the strict Arabic run/diagnostic failed, and
an explicit JSON-mode probe passed. Total live attempts across these development
runs are recorded in the checkpoint; the final four successes are a separate result.

Gemini's stored daily cooldown is preserved for that provider. Selecting Groq
does not clear or evade provider-issued cooldowns, and Groq's own limits still
apply. Existing reports from earlier prompts/modes have different fingerprints;
use new output filenames for further live evaluations.

## Run it yourself

Stop your existing API/UI processes with Ctrl+C, then start the updated demo:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501> and check that the sidebar says **groq /
qwen/qwen3.8-27b**. Start a new conversation. Repeat the ABIP three-turn flow, then
start another conversation and ask:

```text
أعطني رقم هاتف صيدلية ابن نفيس في الرباط.
```

No new key is needed. The original key was used for the successful checks.

Offline verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_interpretation.py -v
```

An optional live conversation recheck spends up to four attempts:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_conversation_smoke --quantity-check --max-requests 4 --output reports/qwen_return_conversation_recheck.json
```

The pharmacy runner can later check all four language groups, with a separate
four-attempt ceiling and a new report (do not resume the old Gemini report):

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_pharmacy_smoke --max-requests 4 --output reports/qwen_pharmacy_multilingual_recheck.json
```

Broader live extraction and held-out evaluation remain separate work. No local
model hosting, CLI intermediary, paid fallback or automatic provider switch was added.
