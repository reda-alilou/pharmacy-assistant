# Improvement Step 2: annotated evaluation and baseline

The 80-example dataset and complete offline development baseline are ready for
validation. Live extraction evaluation remains pending: four bounded Gemini
attempts timed out on the first case, yielding no usable predictions. Those
attempts and resumable progress are saved. No inference accuracy is claimed for
this new dataset, and no further requests were made after that budget.

## Dataset and annotations

Files in [`data/evaluation/baseline_v1`](../data/evaluation/baseline_v1):

- `development.json`: 40 examples, ten per language group.
- `held_out.json`: 40 examples, ten per language group, not executed.
- `manifest.json`: annotation version **baseline_v1.1**, SHA-256 checksums,
  annotation provenance, catalogue snapshot hash and prospective metric targets.

Each split contains 32 independent messages (eight per group) and eight follow-up
messages (two per group). Groups are French, standard Arabic, Darija in Arabic or
Latin script, and substantial language switching. Drug names/units alone do not
make a message mixed. These labels involve judgment, particularly for borrowed
pharmacy vocabulary, and should eventually receive independent speaker review.

Every example includes:

- Raw message, group, scenario tags and rationale.
- Annotated intent set, reply language/script, and separate medication mentions.
- Raw strength, quantity, form and presentation spans, plus pharmacy/location/time
  details where stated. Unknown fields are null; no unit or identity is inferred.
- Desired record IDs or confirmation/clarification behaviour, using the stored
  catalogue. Clinical requests have boundary expectations, not clinical answers.
- Prior annotated user turns for contextual examples, and desired final outcomes.
- Reviewed alternate raw spans where equally valid excerpts exist, such as
  `Pharmacie Ibn Nafis` and `Ibn Nafis`. Alternatives are not spelling corrections.

Quantities count requested packages; presentations describe package contents.
Names retain the user's spelling/script, including misspellings. Day references
such as `غدا` are date slots; time expressions such as `الليلة` are time slots.
Contextual cases preserve raw current-turn entities and identify the expected
medication via prior context; they are excluded from standalone live extraction.

The examples are **synthetic and assistant-authored/reviewed**. They were checked
against raw spans, the extraction contract and catalogue IDs. There is no claim
of independent human/native-speaker review, inter-annotator agreement, real-user
representativeness or an external benchmark. Related domain concepts occur in
both splits, so this is a development holdout rather than a fully independent
study.

## Freeze and review history

The loader rejects modified annotation files using manifest checksums. A final
pre-live review added explicit form coverage in each development group and
corrected form annotations in held-out package follow-ups. The manifest records
this revision from v1 to v1.1, including prior file hashes and affected IDs.
The first offline draft report is retained as
`reports/development_backend_baseline_draft_v1.json`; it is superseded by the
current v1.1 report. No held-out backend result or model output informed edits.

The held-out annotations were read for authoring and integrity validation only.
There is deliberately no held-out execution switch in the development runner.
Changes after this checkpoint require a disclosed new annotation version.

## Complete offline backend baseline

The real `ChatService`, resolver, directory and answer templates were exercised
with annotated intent/entities. **No LLM was called for these checks.** These
numbers isolate downstream behaviour; they are not model accuracy or live
end-to-end success rates.

| Measure | Observed |
| --- | --- |
| All development outcomes | 24/40 pass |
| Independent-message outcomes | 24/32 pass |
| Contextual follow-up outcomes | 0/8 pass |
| Medication decisions, independent messages | 17/21 correct |
| Incorrect automatic selections | 0 observed |
| Broad lists exceeding five candidates | 2 cases |

Outcome checks verify requested record identities, required clarification options,
pharmacy matches, quantity totals, missing prices, unsupported-request boundaries
and canonical record equality. A case can fail several checks. The summary's
failure counters count individual checks; the following list counts distinct cases:

1. **Medication matching: four failing cases.** Arabic `أموكسيسيلين` is not found;
   the Arabic inhalation form `الاستنشاق` prevents a match; unmatched ABIP/AIRCORT
   strengths return no useful correction options. These are backend failures
   even when extraction is supplied correctly.
2. **Pharmacy matching: one failing case, two checks.** Arabic `صيدلية ابن نفيس`
   does not match the stored Latin pharmacy name.
3. **Answer construction: three failing cases.** Requested totals of 166, 744 and
   536 MAD are absent, although the underlying presentations resolve correctly.
4. **Conversation state: eight failing cases.** Prior turns are sent through the
   actual current text-only request contract. Packaging and quantity follow-ups
   lose the medicine identity. No remembered identities are secretly injected.
5. **Clarification usability observation:** AMOXICILLINE and PARACETAMOL produce
   44 and 141 total candidates respectively, with only the first 20 shown. Their
   medication decision can be correct while the clarification remains cumbersome.

Evidence: [backend results](../reports/development_backend_baseline.json) and
[failure summary](../reports/development_baseline_summary.json). Dataset, directory
and unchanged production-module hashes are recorded for reproducibility.

## Live extraction baseline

The existing budgeted/resumable runner now accepts a scoring profile while its
original 12-case smoke default remains compatible. The new runner uses only the
32 single-turn development examples, interleaved by language group so a four-case
sample would cover one case per group if all requests succeeded.

For this checkpoint, two invocations authorized two attempts each in practice:
the first had a four-attempt ceiling but stopped after two timeouts; the second
used only the remaining two attempts. Both stopped on `dev-fr-01`. Total actual
attempt reservations: **4**. Completed predictions: **0/32**. All precision,
recall, F1 and accepted-response latency values are therefore **unmeasured/null**.
Timeouts do not establish whether quota, connectivity or provider execution was
responsible. No raw schema-only validity percentage can be calculated from the
adapter's combined schema/evidence rejection signal.

When predictions become available, scoring reports:

- Intent micro precision/recall/F1 and exact intent-set counts.
- Non-null entity-slot micro precision/recall/F1, overall, per language group and
  per field. Each medication is aligned one-to-one to maximize matching slots;
  reordered mentions are accepted and duplicate predictions cannot reuse gold.
- A wrong non-null slot contributes both a false positive and false negative;
  a missing slot contributes a false negative. Correct nulls do not inflate F1.
- Language/reply diagnostics, exact entity cases, accepted-response latency and
  incomplete-case counts. Empty groups/unsupported metric denominators remain null.

Targets remain intent F1 ≥ 0.90, slot F1 ≥ 0.85 and intent F1 ≥ 0.80 in each group.
Targets are not measured results. The dataset is too small to establish general
reliability even after a complete run.

Evidence: [resumable live report](../reports/development_live_gemini.json).

## Commands

Validate both frozen splits without inference or backend execution:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluation_dataset
```

Reproduce the offline development run into a new report (existing evidence is
protected from accidental overwrite):

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_baseline offline --output reports/development_backend_recheck.json
```

Resume the live development run later, explicitly authorizing at most four more
outbound attempts. This command spends quota; it was not run beyond this step's
four-attempt total:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_baseline live --resume --max-requests 4
```

Refresh the JSON failure summary from saved reports, without inference:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_baseline report
```

Run the offline regression suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

The new tests cover split integrity, freeze enforcement, raw evidence, mention
reordering/duplication, missing/wrong slots, null denominators, alternate spans,
wrong presentation selection, backend/model separation and budgeted resume with
the new metrics. Exact totals are in the checkpoint report.

## Validation boundary

Medication matching, conversational state, answer templates, sources and UI were
not changed in this step. The next implementation step fixes matching using the
measured development failures. Live extraction evaluation remains resumable and
must stay labelled incomplete until actual predictions are collected. No server
was started or stopped; the local `.env` was not modified.
