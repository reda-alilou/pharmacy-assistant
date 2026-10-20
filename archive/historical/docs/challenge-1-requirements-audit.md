# Challenge 1 requirements check

Checked on 2026-10-19 against pages 1-2 of
`C:\Users\REDA\Desktop\COURSES\Challenge camp\Challenges.pdf`.
Only Challenge 1 was assessed. Document requirements are assessment criteria,
not authorization to change scope or run services.

## Conclusion

The core technical objectives are implemented, with recorded test evidence.
The submission is not yet fully documented: the required related-work study
is missing, and the architecture/setup explanation needs to describe the
implemented system consistently. Further scraping is not a prerequisite in
the written brief.

## Requirement-to-evidence mapping

| Written requirement | Assessment | Evidence and limits |
| --- | --- | --- |
| Pharmacy-oriented conversational assistance | Implemented | `src/pharmacy_assistant/chat.py`, `conversation.py`, `resolution.py`, `pricing.py`: medication requests, follow-ups, clarification and totals. Session state expires and is lost on API restart. |
| Text and/or voice input | Met through text | `demo.py` accepts typed messages; `nlu_models.py` defines the validated text request. Voice is not implemented, but the brief permits text alone. |
| Arabic, Darija, French and code-mixed interaction | Implemented and evaluated | Model extraction and reviewed answer templates support the language groups. The 80-example fixture has 40 development and 40 held-out cases, ten per group per split. These are small synthetic examples, not independent native-speaker validation. |
| Intent recognition and structured extraction, including medication names and quantities | Implemented | `nlu_models.py` provides intent and entity schemas; `nlu.py` performs hosted inference and validation. Raw extraction remains separate from inherited/corrected context. The model still makes some extraction errors. |
| Return structured interpretations rather than only free-form answers | Met | `/interpret` returns validated interpretation and inference metadata; `/chat` also returns medication results, context, pricing and sources. Streamlit exposes extraction JSON. |
| Expose the final service through an API | Met | `api.py` defines `/interpret`, `/chat`, `/health`, medication search and record lookup, with FastAPI-generated API documentation. Streamlit is the demo client. |
| Study of the problem and related work | Partial; clear remaining deliverable | README discusses the Moroccan multilingual pharmacy problem. No completed related-work study comparing relevant prior approaches with cited sources was found in README/docs. Provider setup links alone do not satisfy that study. |
| Architecture and processing-pipeline design | Implemented; documentation needs consolidation | Code follows Streamlit -> FastAPI -> hosted extraction -> local validation/context -> catalogue/directory resolution -> pricing -> answer templates. README contains an older target diagram and stale pending-work sections, including already implemented functionality and optional voice. |
| Implementation of NLP and/or speech components | Met through NLP | Hosted-model multilingual intent/entity extraction, schema/evidence validation and local normalization are implemented. No speech component or model training is claimed. |
| Test scenarios and evaluation of results | Met with disclosed limits | `data/evaluation/baseline_v1/` contains the 80 annotated examples. `docs/evaluation-checkpoint.md` documents the frozen run. `docs/arabic-package-fix.md` and complete regression metrics document later corrections. The reports need a concise current overview separating historical benchmark results from subsequent development checks. |

## Verified evidence

- Historical frozen held-out evaluation: 34/40 backend scenarios, intent F1
  92.86%, current-message entity slot F1 95.91%, 48/48 schema-valid model
  completions. Source: `reports/held_out_qwen_frozen_metrics.json`.
- Later targeted correction set: 14/14 backend scenarios, 20/20 schema-valid
  completions; effective intent F1 100%, raw current-message entity slot F1
  85.71%. Source: `reports/matching_package_metrics_complete.json`. This set
  contains six seen failures and eight fresh variations; it is development
  regression evidence, not a new independent benchmark or overall accuracy.
- Last recorded offline suite: 236 tests passed in 224.936 seconds. Source:
  `reports/matching_package_offline_tests_final.log`. No tests were rerun during
  this document review.
- Active files counted during this check: 9,936 AMMPS medication presentations;
  2,700 have secondary-source observations; 1,008 Medicament.ma observations;
  5,299 Saydalia observations; 327 Rabat pharmacy records. Secondary counts
  are not counts of additional uniquely resolved medications. There are 1,126
  AMMPS records without a public price; those prices must remain unknown.

## Scope distinctions

- The brief does not require complete collection from three sources, every
  Moroccan city, live pharmacy stock, verified duty schedules, a particular UI
  framework or public hosting. Rabat-only coverage and incomplete enrichment
  must still be stated clearly.
- Availability and pharmacy information motivate the brief. The assistant
  recognizes those requests, retrieves directory details where available and
  explicitly reports that live stock, opening hours and duty are unverified.
  It must not be presented as a service that verifies those facts.
- No written requirement in these two pages specifies open-source models,
  training, fine-tuning or self-hosting. The user's separately reported
  professor instruction about open-source models remains an additional
  constraint; absence from this PDF does not cancel an oral instruction.
- The actual implementation uses hosted Groq inference. It must not be
  described as locally hosted or trained by the team.
- A five-minute script, backup screenshots and a visual redesign are useful
  presentation aids from our plan, not explicit deliverables in this brief.

## Recommended next checkpoint

Prepare the problem/related-work study and a concise current architecture and
evaluation explanation, then replace the outdated README with accurate setup,
implemented capabilities and limitations. Preserve the original evaluation
evidence. Do not delay this checkpoint for more scraping or a frontend rewrite.

This review did not start/stop demo servers, call an inference API, change
application code or datasets, or restart collection. A temporary PDF reader
was installed under `tmp/pdfs/runtime` solely to extract and visually inspect
the two relevant pages; project dependency files were unchanged.
