# R6 — Archive and retirement

Status: **complete, reviewed by the user**. The user authorized R7. All ten user-run isolated checks and
all 18 PostgreSQL tests passed with no skips. The user reviewed R5 and authorized
R6. R7 has not started.

## Final structure

The active root contains the README, project handoff, decision log, uv workspace
configuration and normal repository dotfiles. Application code belongs to
`apps/web/`, `services/core/`, `services/language/`, `packages/` and `tools/`.
Shared tests belong to `tests/architecture/`, `tests/integration/` and
`tests/support/`. Deployment uses `deploy/compose.yaml`, explicit debug/phone
overlays and the unchanged gateway configuration at `deploy/nginx/nginx.conf`.

The root is now a virtual uv coordinator, not an installable CLI stub. Six
members own their dependency manifests. The lock drops 26 unused dependencies,
including Streamlit, Beautiful Soup and Requests plus their unused transitive
dependencies; retained versions are unchanged. The old duplicate root dependency
groups and root console script are removed.

R6 removes **140 explicitly gated obsolete files**: 104 legacy package modules,
32 root tests/helpers, the Streamlit configuration, root Alembic configuration,
obsolete database-only Compose file and old verification seed. R5's complete
coverage map and successful React/real-stack flows satisfied the removal gates
before the interface was removed. Source history remains available at the saved
baseline commit. See [the per-file removal record](cleanup-r6-removals.json).

The initial R6 baseline left ignored local files untouched. The user subsequently
authorized removing verified obsolete local leftovers, including nested files.
That follow-up removes old builds, exported test copies, logs, bytecode caches,
the root legacy cache directories and the throwaway R5 evaluation environment.
Previously ignored raw downloads and staging data are preserved byte-for-byte
under ignored `archive/local/`, with a separate local manifest. Active imports,
tracked archive, private configuration/ledgers, primary environments and current
validation evidence remain intact. See the
[local housekeeping record](cleanup-r6-housekeeping.json); the earlier baseline
JSON remains an unchanged record of the initial R6 checkpoint.
The completed housekeeping removed 9,629 files and preserved 6,433 local raw/
staging files with matching hashes. Focused post-cleanup checks passed 38 offline
tests, with 18 PostgreSQL tests intentionally skipped. All 204 canonical source
hashes and the public archive manifest are unchanged. No bytecode was regenerated;
`data/` now contains only active imports and evaluation inputs. This follow-up
started no application stack and did not begin R7.

## Preservation and historical tools

Exactly **1,002 historical files** moved to
`archive/historical/<original-relative-path>`. The manifest records exact R1
checkout hashes, original Git identities, committed-content hashes and sizes.
Raw snapshots were preserved, not discarded. Existing private ledgers/backups
were not included in the archive.

The two authoritative JSONL inputs moved unchanged from `data/processed/` to
`data/imports/`. Active annotations/regressions remain unchanged in
`data/evaluation/`. All service/tool/test/Docker consumers use the new input
paths. Import identity, content hashes, migration revisions and SQL semantics
are unchanged; existing database volumes need no reset or re-import.

`pharmacy-archive` verifies all **1,004 mapped files**. The wider R1 preservation
audit checks **1,010 files**, including the six active annotation/manifest files;
this includes all 982 original data/report files. Git attributes disable byte
normalization for archived material and active imports. Every archived file is
addable despite old cache ignore rules.

Maintained evaluation readers use the manifest to resolve old input references,
validate preservation hashes and reject traversal, unknown archived paths,
duplicate entries or modified/missing data. Historical report contents, embedded
paths and freezes remain unchanged. Recorded held-out and correction predictions
can be rescored with the same recorded metrics; an old freeze still cannot
authorize current hosted execution. New reports remain under ignored artifacts.

## Current documentation

- [README](../../README.md): normal startup/shutdown, structure and current limits
- [Architecture overview](../architecture/overview.md): processing and ownership
- [Setup guide](../operations/setup.md): existing workspace, fresh setup and explicit migrations/import
- [Operations guide](../operations/tooling.md): commands, verification and backup prerequisites
- [Evaluation guide](../development/evaluation-tools.md): scoring, budgets, provenance and resume
- [Data/evidence guide](../project/data-and-evidence.md): active inputs and historical measurements
- [Requirements audit](../project/requirements-audit.md): implemented requirements and remaining submission work
- [Archive guide](../../archive/README.md): mapping and historical reference interpretation

Earlier checkpoint guides and frozen JSON describe their original versions. The
root handoff and current guides replace them as startup/navigation instructions.
Archived documents are preserved byte-for-byte, including their original links.

## Verification

- All eight maintained Python suites passed: **247 offline tests**, with the
  **18 real PostgreSQL tests** deliberately skipped outside isolated verification
  (265 discovered). New checks cover archive integrity/tampering/traversal,
  historical scoring, old-freeze rejection and retired source/dependency absence.
- Frontend production build and **22 offline browser tests** passed; one
  deployment-only scenario is intentionally skipped offline. Lint has no errors
  and the same two pre-existing shadcn fast-refresh warnings.
- Six independent package wheels and source distributions built offline; frozen
  lock verification passed. Retained dependencies did not change versions.
- All four application/setup images rebuilt. Network-disabled, self-removing
  checks verify installed core/language ownership, original OpenAPI hashes,
  PostgreSQL-only startup and the operations image's nine CLI commands plus
  relocated import files. Legacy source/Streamlit and private files are absent.
- Existing Compose configuration validates quietly without exposing credentials.
  The user-run complete stack passed all ten checks and all 18 PostgreSQL tests,
  including fresh/repeated migrations and import, complete fact reconstruction,
  owned permissions, outages, cooldowns, transcript/choice recovery, real frontend
  restore/reset, persistence, backup/restore and evaluation resume. The test
  project/volume were removed; the application volume was untouched.

Evidence: [baseline and source hashes](cleanup-r6-baseline.json),
[removal gates](cleanup-r6-removals.json), [installed-image checks](cleanup-r6-images.json),
[successful isolated verification](cleanup-r6-container.json) and the
[archive manifest](../../archive/manifest.json). Detailed local logs/builds are
ignored under `artifacts/cleanup/r6/`.

No hosted inference, scraping, network changes, application-volume modification,
private credential/ledger change, Git commit or push was performed. R7 remains
the final complete validation and user laptop/phone demo review. Stop after the
R6 result and handoff for user review.
