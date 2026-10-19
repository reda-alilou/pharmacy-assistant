# Arabic identity and package-follow-up corrections

This development checkpoint addresses the six behavioral failures found in the
previous frozen evaluation. The original benchmark remains **34/40**, with its
original predictions and metrics preserved. These examples are now seen data;
results here are regression evidence, not a new independent accuracy benchmark.

## Implemented behavior

- Exact reviewed spellings `فنتولين`, `فينتولين`, `ڤنتولين`, `ڤينتولين` map to
  VENTOLINE; `أوغمنتين` and `أوجمنتين` map to AUGMENTIN. Existing Arabic
  normalization handles diacritics, hamza variants and tatweel. Raw extracted
  names remain unchanged. Strength, form and presentation still have to match;
  a name alone does not select one of several presentations.
- The extraction prompt explicitly distinguishes package contents, requested
  package counts and strength. Counts attached to a package/form stay in
  presentation; explicit strength cues without units stay unitless. An unnamed
  package choice is information that can inherit the prior price intent; an
  explicit request for a number of packages remains a medication request.
- A bounded, provider-independent context rule handles a remaining model error:
  for an unnamed follow-up with a stated presentation, a definite container
  reference such as `lboita`, `la boîte` or `العلبة` is not an order quantity.
  It is cleared only in the effective context, with changes listed in
  `context.normalized_fields`. Original extraction remains visible. Explicit
  counts, indefinite singular orders, plural unspecified quantities and strength
  filters are preserved. Several preceding medications still require a reference
  choice rather than selecting one automatically.
- Explicit Arabic indefinite singular quantities such as `علبة` denote one
  package, like French `une boîte`. A missing quantity stays unknown; definite
  references and unspecified plurals do not default to one. Specific-container
  pricing still requires the retrieved presentation to be that container.
- Outcome checks now reject an unexpected clarification when the expected
  medications are resolved. A correct record with an unnecessary quantity
  question no longer counts as a successful scenario.

No source data, prices, provider, model or local message-spacing setting
was changed. The user subsequently updated the local API key for the completion
check; credentials were never printed or stored in reports. No collection or demo server was started. The prompt version is
`step9-package-selection-v1`.

## Verification design

[`matching_regressions_v1.json`](../data/evaluation/matching_regressions_v1.json)
contains six seen failures and eight fresh development variations, authored
before their live checks. Six scenarios need a preceding conversation turn, so
the fixture requires 20 accepted model outputs. The fresh cases cover Arabic
letter/diacritic variants, box sizes 20/30/40, explicit quantity totals, a unitless
strength that must not acquire `mg`, and an unnamed explicit order that must ask
for the medication name.

The first live run preserved 11 accepted outputs before a Groq quota pause.
Checking full replies revealed unnecessary quantity questions despite correct
record identities. The context/pricing rules and outcome checks were corrected.
Those same 11 outputs were validated and replayed through the corrected backend
under a new report, preserving the original evidence and request ledger. The
model, prompt, schema and input fingerprint did not change during that replay;
it used **zero additional inference calls**. The completion check honored the shared provider cooldown before resuming
remaining fresh messages.

An offline replay of the original 40 frozen live predictions, after the alias
change alone, reached **38/40** backend outcomes: the four identity failures were
resolved while the two original package-extraction failures remained. This is
an offline backend comparison, not new model inference. Annotated extraction
for all 14 regression scenarios passes the corrected backend checks.

The six original failures now pass the corrected backend with **answered**
responses, using recorded live model outputs. This includes the two quantity
clarification issues exposed by the stricter outcome check. Three fresh cases
also pass from live outputs: Arabic V-letter spelling, diacritics with a tablet
presentation, and a two-box Arabic/Darija total.

The initial run hit a daily-token limit, leaving five fresh scenarios pending.
The [partial metrics](../reports/matching_package_metrics_partial.json),
[quota diagnostic](../reports/matching_package_quota_diagnostic.json) and
[partial checkpoint](../reports/matching_package_checkpoint_partial.json)
preserve that earlier state.

After the user updated the local API configuration and requested a retest, the
shared cooldown was honored. Two sandboxed connection attempts could not reach
Groq; after network access was enabled, **all eight remaining inference jobs
succeeded in eight calls**, with no quota rejection in that invocation.
No accepted output was repeated. All **14/14 scenarios now pass**, including
all six seen failures and all eight fresh variations. All **20/20 returned model
outputs are schema-valid**, with no entity-evidence rejections.

The cumulative ledger records **24 reserved attempts**: 20 accepted model
outputs, two historical HTTP 429 failures and two sandbox connectivity failures.
The first 11 accepted outputs retain the documented backend-replay provenance.
This remains a targeted development regression, not a new independent benchmark;
the original frozen 34/40 result is unchanged.

Raw current-message entity slot F1 is **85.71%** on this small regression set;
effective dialogue intent F1 is **100%**. In particular, the model still sometimes
extracts a definite container as quantity or omits a form. The bounded context
rules correct the relevant dialogue behavior, while the raw extraction stays
visible. Passing backend outcomes does not mean perfect raw extraction.
Median adapter latency across the 20 accepted calls is **882.5 ms**, with
nearest-rank p95 **1703 ms**; this excludes browser rendering and historical
transport failures.

See the [current checkpoint](../reports/matching_package_checkpoint.json) and
[complete metrics](../reports/matching_package_metrics_complete.json).

The final offline suite passed **236 tests in 224.936 seconds**. Tests cover
exact alias targets, retained ambiguity and wrong filters, raw versus effective
fields, explicit versus definite-reference quantities, package-selection then
quantity follow-ups, and rejection of unnecessary clarification by the outcome
metric. The API/UI tests use mocked inference; they do not spend live quota.

Evidence:

- [Development fixture manifest](../data/evaluation/matching_regressions_v1_manifest.json).
- [Original frozen benchmark](evaluation-checkpoint.md).
- [Original-output alias replay](../reports/matching_alias_offline_replay.json).
- [Initial live development run](../reports/matching_package_live_v1.json).
- [Updated live/replay run](../reports/matching_package_live_v2.json).
- [Annotated backend checks](../reports/matching_package_backend_oracle.json).
- [Final offline test log](../reports/matching_package_offline_tests_final.log).

## Run and validate manually

Start the demo yourself, then open `http://127.0.0.1:8501`:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

In a new conversation:

1. Ask `ما ثمن فنتولين 100 ميكروغرام / جرعة؟` — stored price **42.20 MAD**.
2. Ask `أريد ثمن ثلاث علب من أوغمنتين 1 g / 125 mg، علبة 24.` — **621.00 MAD** total.
3. Ask `Ch7al taman VENTOLINE?`, then `Bghit lboita dyal 40 dyal l9ras.` —
   selects record 1974, stored unit price **18.70 MAD**, without asking how many
   boxes. Its stored commercialization status is **Retiré du Marché**; live stock
   remains unknown. Then ask `Et pour deux boîtes ?` — **37.40 MAD**.
4. In a new conversation, ask `Quel est le prix de ABIP ?`, then
   `Les comprimés ديال 30 عافاك.` — selects the 30-tablet presentation at
   **372.00 MAD**.
5. Ask for `AUGMENTIN 2 g / 125 mg, boîte de 24` — requests clarification instead
   of silently accepting the catalogue's different stored strength.

The completed report already contains all outputs. The following resume command
skips completed jobs and does not start servers; a new live run requires a new
report and an explicit request budget:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_development --examples data/evaluation/matching_regressions_v1.json --output reports/matching_package_live_v2.json --max-requests 10 --interval 20 --resume
```

Completed outputs are skipped. Configuration, prompt, examples or backend
changes reject resume; old evidence is not silently migrated or overwritten.
The explicitly documented backend replay above was a separate offline operation.

The alias list remains finite. These fixes do not provide universal Arabic
transliteration, complete national data, clinical recommendations or live stock.
