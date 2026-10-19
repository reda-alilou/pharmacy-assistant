# Live evaluation checkpoint

This checkpoint evaluates the actual Groq adapter, followed by the unchanged
`ChatService`, medication resolver, conversation state, directory and pricing
logic. No API or Streamlit server is needed. Collection remains stopped.

The selected model is `qwen/qwen3.8-27b`, with explicit `json_object` output,
strict local Pydantic validation and entity evidence checks. The corrected prompt
version is `step8-temporal-packaging-v1`. No provider, key, dataset or stored
price was changed during this checkpoint.

## Evidence and scoring

The frozen annotation dataset has 40 development and 40 held-out cases, with ten
French, Arabic, Darija and mixed-language cases in each split. Each split has
32 standalone messages and eight follow-ups. Eight additional live setup calls
establish the prior turns, so a full split requires 48 accepted inference calls
when no failures/retries occur.

Intent precision/recall/F1 compares intent sets. Entity slot F1 counts non-null
raw spans with one-to-one medication alignment, allowing the frozen annotation
alternatives. Correct nulls do not inflate F1; a wrong non-null slot contributes
both a false positive and a false negative. A refused/invalid prediction stays
a failed case rather than being retried until it looks correct. Transport/quota
interruptions remain visibly pending and can resume under a new bounded budget.

Follow-up annotations contain the dialogue's intended action but only the
current message's entity spans. Consequently, the primary 40-case report scores
**effective dialogue intents and raw current-message slots**. Correct inherited
drug names are assessed by medication-resolution/outcome checks, not counted as
invented current-message entities. Pure raw extraction scores for the 32
standalone messages are reported separately.

Schema validity counts SDK-returned completions; HTTP failures have a separate
denominator. Latency measures the production interpretation adapter, including
its bounded retry, rather than the browser round trip. Evaluation calls were
paced separately; the demo's artificial local delay remains disabled.

Targets were defined before the live run: intent micro-F1 at least 0.90, entity
slot micro-F1 at least 0.85, and intent F1 at least 0.80 in every language group.

## Development history

The first complete run used 48 calls and returned valid, evidenced interpretations
for all 48. It passed 39/40 backend outcomes and 28/29 medication decisions.
Effective intent F1 was 1.000; current-message entity slot F1 was 0.9793.

Two extraction mistakes were found:

- Arabic "tonight" was extracted as a date rather than a time. The requested duty
  information still correctly remained unverified, but the structured slot was wrong.
- Container wording inside a rare product's presentation was duplicated into its
  pharmaceutical form. The extra form filter blocked the correct record and its
  missing-price response.

The prompt now distinguishes calendar dates from parts of the day and containers
from pharmaceutical forms. Both affected examples and four nearby regression
examples were checked live: all six passed, preserving explicit tablet and
inhalation forms and the date/time distinction. These were six additional calls.

The reviewed development history reaches 40/40 backend outcomes and 29/29
medication decisions. It combines 42 retained setup/current predictions from the
original prompt with six rechecks from the corrected prompt. **It is development
history, not a uniform-prompt benchmark.** All selected rechecks replace their
original predictions regardless of success; original failures remain preserved.

Evidence:

- [Original predictions](../reports/development_qwen_live_v1.json) and
  [first-pass metrics](../reports/development_qwen_first_pass_metrics.json).
- [Six live rechecks](../reports/development_qwen_prompt_rechecks_v2.json).
- [Reviewed development history](../reports/development_qwen_reviewed_history.json)
  and [reviewed metrics](../reports/development_qwen_reviewed_metrics.json).
- [Offline regression log](../reports/frozen_evaluation_offline_tests.log).

## Held-out evaluation

Held-out results are recorded only after the implementation and configuration
freeze. The freeze hashes all Python modules, dependency files, annotation files
and active datasets, and records public model settings without credentials.
The held-out command refuses changed code/data/settings before loading examples
or sending a provider request. The annotation files themselves are unchanged.

The final measured results and any failures are listed below after completion.
No held-out result is used to tune this frozen version.

The frozen run completed all 40 held-out cases using 48 valid live model
responses. It used 49 outbound attempts: one HTTP 429 interrupted the last batch;
after honoring the cooldown, only pending calls resumed. No key, model, prompt,
backend code or dataset changed during held-out execution.

| Primary measure | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| Effective dialogue intents, 40 cases | 92.86% | 92.86% | 92.86% |
| Raw current-message entity slots, 40 cases | 96.47% | 95.35% | 95.91% |
| Raw standalone intents, 32 cases | 97.06% | 97.06% | 97.06% |
| Raw standalone entity slots, 32 cases | 100.00% | 98.65% | 99.32% |

| Language group | Intent F1 | Entity slot F1 | Backend outcomes |
| --- | ---: | ---: | ---: |
| French | 90.91% | 100.00% | 10/10 |
| Arabic | 100.00% | 100.00% | 8/10 |
| Darija | 90.00% | 88.37% | 8/10 |
| Mixed | 90.91% | 95.45% | 8/10 |

All previously defined **extraction F1 targets were met**. This does not mean all
requests succeeded: backend outcomes passed **34/40 (85%)**, and medication
resolution/clarification decisions passed **25/31 (80.65%)**. Schema validity was
**48/48 returned completions**, with no evidence-rejected entity values. The
single HTTP failure is counted separately rather than excluded from attempt costs.

Median accepted adapter latency was **797 ms**, p95 **1,625 ms**, and maximum
**2,172 ms**. These exclude operator pacing, the quota pause and browser/backend
round-trip time. Returned completions used 76,744 prompt tokens and 7,238 output
tokens (83,982 total); the failed HTTP request returned no token usage.

Six behavioral failures remain:

1. Four cases (`held-ar-01`, `held-ar-02`, `held-darija-02`, `held-mixed-04`)
   fail to map Arabic Ventoline/Augmentin spellings to their existing catalogue
   records. A separate offline run supplying perfect annotated extraction also
   fails these same four cases: **36/40 oracle backend outcomes**. This isolates
   a normalization/matching gap rather than an absent source record.
2. Two follow-ups (`held-darija-09`, `held-mixed-09`) interpret a box's count of
   40 tablets as strength, then apply an incorrect strength filter. Their raw
   intent also differs from the dialogue's annotated price intent.

One additional standalone intent disagreement (`held-fr-08`) does not break its
backend outcome: an unnamed medication order is labeled medication information.
One Arabic sachet/form slot disagrees with the annotation. All 40 language-group
labels match the annotations; mixed-language reply language/script matches 7/10
labels, and other groups match 10/10. These are annotation-agreement diagnostics,
not independent human judgments of linguistic quality.

No held-out failure was used to alter this frozen version. The next engineering
checkpoint should address Arabic name normalization and package-count follow-ups;
this held-out set must then be treated as seen data for further development.

Evidence: [frozen predictions](../reports/held_out_qwen_frozen_v1.json),
[complete metrics](../reports/held_out_qwen_frozen_metrics.json),
[oracle diagnostic](../reports/held_out_backend_diagnostic.json), and
[implementation freeze](../reports/qwen_evaluation_freeze.json).

The final offline regression suite passed **225 tests in 204.477 seconds**.

## Reproduction

These commands spend live quota and never start the demo servers. Existing
evidence is protected: use a new output path for a new run. Resume the same run
with `--resume`; model, prompt, code or data changes reject resume.

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_development --output reports/development_new.json --max-requests 8 --interval 15
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_development --output reports/development_new.json --max-requests 8 --interval 15 --resume
```

The development-only `--case-ids` option supports explicit targeted rechecks.
The separate held-out command requires the recorded freeze and always uses the
complete split:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_held_out --freeze reports/qwen_evaluation_freeze.json --output reports/held_out_qwen_frozen_v1.json --max-requests 8 --interval 15
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_held_out --freeze reports/qwen_evaluation_freeze.json --output reports/held_out_qwen_frozen_v1.json --max-requests 8 --interval 15 --resume
```

Reports can be rescored offline without calling the model:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.report_live_evaluation reports/held_out_qwen_frozen_v1.json --split held_out --output reports/held_out_rescored.json
```

Once this held-out set has been inspected, subsequent tuning on its failures
makes it development data. A later independent benchmark needs a new held-out
set rather than repeated tuning and evaluation on these same examples.

## Limits

These are small, synthetic, assistant-authored/reviewed examples, with no
independent native-speaker annotation review. Related concepts occur across the
splits. Reply-language/script labels, especially for mixed messages, sometimes
admit more than one reasonable choice; exact agreement is reported separately.

Backend checks verify structured outcomes and equality with the local catalogue;
they are not an independent linguistic review of every generated sentence.
Recorded prices are historical source observations. Pharmacy stock, opening
hours and duty schedules remain unverified, and the Rabat directory is partial.
The evaluation does not establish clinical safety, nationwide coverage, sustained
provider availability or production-level reliability.
