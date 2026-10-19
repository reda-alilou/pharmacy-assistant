# Improvement Step 6: pharmacy-name matching

The remaining development failure was an Arabic pharmacy-contact request. Its
extraction correctly preserved `صيدلية ابن نفيس`, while the directory stored
`Pharmacie Ibn Nafis`. Direct substring matching could not bridge those scripts.

This checkpoint fixes local directory matching and adds an explicit ambiguity
response. It uses the existing 115-record Rabat sample. No new data was scraped,
no prompt/provider configuration/key was changed, and no API/UI service was
started or stopped.

## Implemented behavior

- Normalize case, accents, Arabic diacritics, punctuation and pharmacy labels,
  including attached Arabic labels such as `صيدليةابننفيس`.
- Use a small assistant-reviewed table of 11 alias spellings for seven stored
  pharmacy names. Examples include `ابن نفيس` → `ibn nafis`, `ابن سينا` →
  `ibn sina`, and `باب جديد` → `bab jdid`. These are lexical mappings, not a
  general transliterator, independent linguistic review or new source records.
- Prefer a complete normalized name over longer names containing it. `City Center`
  returns its own record rather than also returning `City Center Ryad`.
- Match remaining partial names only as complete contiguous words. `naf` cannot
  match `Nafis`, and `6 novembre` cannot match `16 novembre`. Unknown spellings are
  not fuzzily selected or silently replaced with another pharmacy.
- Return `pharmacy.status: "ambiguous"` and chat `needs_clarification` when a named
  query matches multiple records. Show the candidates and ask for a full name or
  area. Even duplicate normalized names retain their distinct record IDs.
- Apply explicit name and area filters together, with no unfiltered fallback.
  Area aliases are handled separately from pharmacy identity. Riad/Ryad spelling
  variants and reviewed Arabic district names share the same textual filter.
- Keep directory browsing as a list, not an ambiguous named match. Return the full
  match count, at most five displayed records, and `results_truncated`. The UI now
  states how many of the matching records are displayed.

Contacts, addresses, source links and timestamps remain verbatim retrieved data.
Stock is unknown, opening hours are unknown, duty status is unverified and order
is by name rather than distance. Area matching searches name/address text; it
does not establish official district boundaries. Coverage remains partial Rabat.

## Results

| Development outcome, annotated extraction | Before | After |
|---|---:|---:|
| Overall complete outcomes | 39/40 | 40/40 |
| Standalone outcomes | 31/32 | 32/32 |
| Contextual outcomes | 8/8 | 8/8 |
| Standalone medication decisions | 21/21 | 21/21 |
| Contextual medication decisions | 8/8 | 8/8 |

The frozen examples and scoring criteria were not changed. The held-out split
was validated for integrity only, not executed or used to tune matching. These
backend checks use annotated extraction, and the synthetic examples are assistant
reviewed without independent human/native-speaker review. **40/40 is not a model
accuracy score or proof of general reliability.**

All **199 offline tests pass**, including 12 new pharmacy matching/API/UI tests
and two new tests of the budgeted live-check runner. Tests cover all reviewed
alias targets, punctuation/script variants, real exact-name collisions, partial
word/number rejection, duplicate names, strict area/city filtering, partial
directory scope, grounded contacts, contextual clarification and Streamlit.

Evidence: [verified development run](../reports/development_backend_step6_verified.json),
[checkpoint](../reports/improvement_step6_pharmacy_matching.json),
`reports/step6_offline_tests.log` and `reports/step6_pharmacy_tests.log`.
The initial Step 6 report is an intermediate run; previous evidence is preserved.

## Live validation remains incomplete

The [live pharmacy check](../reports/pharmacy_live_step6.json) uses four existing
development cases: French, Arabic, Darija and mixed language. It runs the hosted
extractor, then the actual directory resolver and grounded answer templates.
Acceptance requires correct intents/entities, expected reply language/script and
the unique annotated pharmacy ID. The same durable budget, shared spacing and
resume protection used by the existing evaluator apply. Directory and resolver
fingerprints prevent mixing results after source/code changes.

The first invocation had a four-attempt ceiling. Gemini returned
`provider_unavailable` after **two attempts**, and the runner stopped on the first
French case. **0/4 cases completed.** Live F1/latency and end-to-end success are
unmeasured for this run. No saved response was substituted. This error does not
establish a key/authentication problem or a provider-wide outage; no key change
was made. Further requests were stopped rather than repeatedly probing.

The larger live extraction baseline and held-out evaluation remain pending.

## API additions

`PharmacyResult` now includes:

- `status: "ambiguous"` for multiple named matches, alongside existing statuses.
- `match_method`: `exact_name`, `reviewed_alias`, `name_tokens`, `area_filter` or
  `browse` (nullable outside coverage).
- `name_alias`: the canonical lookup name when a reviewed alias was applied.
- `results_truncated`: whether only the first five matches are included.

The raw extracted name stays in `interpretation.entities.pharmacy`; source record
names are not rewritten. For `صيدلية ابن نفيس`, the resolved record is
`saydalia:5256`, with its stored contact **0537720657**. Confirm contact details
with the pharmacy; collection is historical and is not live verification.

## Commands and user validation

Stop your own current API/UI processes with Ctrl+C, then start the updated demo:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

When the configured provider is responsive, try:

1. `أعطني رقم هاتف صيدلية ابن نفيس في الرباط.`
2. `3tini numero dyal Pharmacie Ibn Nafis f Rabat.`
3. `Téléphone pharmacie Ibn à Rabat` → several names, asking for clarification.
4. `Le téléphone de la Pharmacie Ibn Nafis` → one stored contact in the same session.

Offline verification requires no key:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_pharmacy_matching.py -v
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluation_dataset
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_baseline offline --output reports/development_backend_step6_recheck.json
```

Choose new offline report filenames on subsequent runs. The live checker can be
resumed later, explicitly authorizing up to four additional provider attempts:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_pharmacy_smoke --resume --max-requests 4 --output reports/pharmacy_live_step6.json
```

It skips completed cases, stops on provider errors and preserves both report and
budget history. Do not resume while the provider continues returning unavailable.
Stop here for validation before the broader live evaluation.
