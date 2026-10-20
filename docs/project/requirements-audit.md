# Challenge 1 implementation and remaining deliverables

This current architecture audit carries forward the written-requirement review
in the [preserved original audit](../../archive/historical/docs/challenge-1-requirements-audit.md).
It updates implementation/evidence locations; it does not claim a new reading of
the original challenge PDF or independent clinical/language validation.

| Requirement assessed in the original review | Current implementation and limits |
| --- | --- |
| Pharmacy-oriented conversation | Core handles medication requests, clarification, follow-ups, recorded prices and partial pharmacy lookup |
| Text and/or voice | React supports typed text; voice remains unimplemented, and the reviewed brief permits text alone |
| Arabic, Darija, French and mixed language | Backend extraction/templates support the language groups; the patient UI is French only |
| Intent/entity extraction, names and quantities | Language validates structured hosted extraction; core performs deterministic matching/context/quantity handling |
| Structured interpretations | Language `/v1/interpret` and core `/interpret` expose validated fields; `/chat` includes grounded results and sources; the patient UI intentionally hides raw JSON |
| API exposure | FastAPI core and separate language API, served behind the same-origin web gateway; core docs at `/api/docs` |
| Problem study and related work | Problem context exists; a completed cited related-work comparison is still a submission deliverable |
| Architecture/pipeline explanation | [Current overview](../architecture/overview.md) describes React, separate services and owned PostgreSQL schemas; [setup](../operations/setup.md) describes the runnable project |
| NLP and/or speech | Hosted multilingual extraction plus local validation/normalization implement NLP; no speech or local model training is claimed |
| Scenarios and evaluation | Preserved live evaluation plus maintained Python/browser/isolated PostgreSQL checks; limitations are explained in [data and evidence](data-and-evidence.md) |

Cleanup R6 retired the superseded Streamlit interface and unused collection
tooling after useful behavior was covered in maintained tests. R7 final validation
is complete: automated checks passed, the user accepted the laptop demo and
explicitly waived another physical-phone review. See the
[final evidence](../validation/cleanup-r7.md) and the self-contained
[current project reference](../../PROJECT_CONTEXT.md).

The related-work study, final submission explanation and presentation preparation
remain separate work. Historical model measurements describe their frozen
versions; passing cleanup checks does not establish new model accuracy.
