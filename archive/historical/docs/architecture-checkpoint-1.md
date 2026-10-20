# Architecture migration — checkpoint 1

Implementation of D018 checkpoint 1 on `refactor/web-architecture`.
The agreed target architecture is in the root `DECISION_LOG.md`.

## Implemented boundaries

All paths below are relative to `src/pharmacy_assistant/`.

| Location | Ownership |
| --- | --- |
| `core/` | Conversations, clarification, catalogue, matching, pharmacy lookup, pricing, answer templates, and core data/API models |
| `language/` | Provider adapters, provider factory, current prompt, and existing SQLite quota implementation |
| `contracts/` | Validated interpretation request/response models, inference failures, and the `Interpreter` protocol |
| `api.py` | Existing FastAPI routes and temporary in-process composition of core and language code |
| `config.py`, `paths.py` | Existing settings and a stable repository-root path |
| Root collection/evaluation/demo modules | Existing offline tools and Streamlit client, retained during the migration |

Core code depends on its own modules, interpretation contracts, and repository
paths. It does not import language adapters, HTTP frameworks, or collection code.
Language code depends on its own implementation, contracts, and settings; it does
not import core business logic. The shared contract package has no service or
provider dependencies. Tests enforce these import boundaries.

The pharmacy record model now lives in `core/pharmacy_models.py`; the collector
imports that model rather than defining a runtime dependency on collection code.
The model's fields and validation are unchanged.

The `Interpreter` protocol now lives in `contracts/interpreter.py`. Conversation
code can accept an implementation of that interface without loading provider SDKs.
The current application still injects an in-process interpreter. A remote client
and independently running language API belong to checkpoint 3.

## Compatibility and HTTP behavior

Old root module names remain thin compatibility imports pointing to the canonical
module objects. Existing imports, test patch targets, and demo/evaluation tools
continue to refer to the same classes and functions, without duplicate state.
The existing `python -m pharmacy_assistant.quota` entry point is retained.
New service code should use the canonical packages above.

Conversation code now raises `core.errors.ChatError` with an application code and
safe message. Only the API boundary translates it to HTTP:

| Codes | HTTP status |
| --- | --- |
| `session_expired`, `clarification_expired` | 410 |
| `invalid_reference`, `invalid_selection`, `invalid_refinement` | 422 |

The response body remains `{"detail": {"code": "...", "message": "..."}}`.
Provider error sanitization and Retry-After behavior remain unchanged.

Root paths are resolved in `paths.py`, so moving modules one directory deeper
does not redirect catalogue, pharmacy, environment, or quota paths.

## Evaluation integrity and verification

Evaluation provenance now includes the nested service and contract implementation.
Freeze snapshots scan Python files recursively. Moving implementation behind
compatibility imports must not allow code changes to escape evaluation guards.
Existing frozen reports and annotations remain historical evidence and were not
rewritten or re-frozen for this refactor.

- Original offline baseline: **236 tests passed**, 36.919 seconds, in
  `reports/architecture_checkpoint1_baseline.log`.
- Six new checks cover import boundaries, isolated core imports, compatibility
  identity, data paths, nested evaluation fingerprints, and HTTP error mapping.
- Full post-change suite: **242 tests passed**, 39.807 seconds, in
  `reports/architecture_checkpoint1_tests.log`.
- Baseline and final regression runs use normal Windows permissions because the
  restricted sandbox prevents some temporary-file/SQLite operations.
- Dependency lock verification and offline source/wheel build passed. Build
  artifacts are in ignored `tmp/checkpoint1-dist/`.
- AST comparison confirmed unchanged behavior in 15 moved domain, provider, and
  contract modules apart from imports and stable root handling.

The full post-change regression result is recorded in
`reports/architecture_checkpoint1_tests.log`.

## Review boundary

Stop here for user review before checkpoint 2. Runtime storage is still JSONL
plus in-memory conversation state and SQLite quotas, with the original 15-minute
token lifetime. PostgreSQL, the agreed 30-minute persistent conversations, HTTP
service extraction, Docker, and the React interface are later checkpoints.
No demo service was started and no live inference or collection was performed.

Next checkpoint begins with concrete relational schema design and user review
before tables are created or data is imported, as required by D016.
