# R5 — Owned tools and maintained coverage

Status: **complete, reviewed by the user**. The user authorized R6. All ten
user-run isolated-stack checks passed, including 18 real PostgreSQL tests with
no skips. The sections below record R5 before the [R6 archive/removal](cleanup-r6.md).

## Changes

Operations and evaluation are independently installable uv workspace members:
`tools/operations/src/pharmacy_ops/` and
`tools/evaluation/src/pharmacy_evaluation/`. Operations own database setup,
backup, migrations, Compose setup/verification, schema export, fixture generation,
quota status and the maintained test runner. Evaluation separates datasets,
scoring, runners and reporting behind `pharmacy-evaluate`.

Commands and prerequisites are documented in the
[operations guide](../operations/tooling.md) and
[evaluation guide](../development/evaluation-tools.md). Database migration
assets belong to the services. The operations image installs owned packages and
assets; it does not copy the legacy source checkout or private configuration.
Core and language do not depend on these tools or on each other's implementations.

Evaluation uses the language-owned PostgreSQL ledger directly. Explicit budgets,
cooldowns, conservative attempt counts, report locking and resume validation
remain enforced. Output defaults to ignored `artifacts/`; report writes/locks
reject historical data, report and archive paths. New fingerprints and freezes
hash canonical workspace sources and do not silently accept earlier freezes.
No new live model benchmark or held-out evaluation was performed.

Maintained tests now belong to their services/packages/tools, with cross-service
checks in `tests/integration/`, ownership checks in `tests/architecture/`, and
shared fixtures in `tests/support/`. They import neither compatibility modules
nor Streamlit. Offline tests inject a test-only memory ledger. Real quota
concurrency, process sharing, cooldowns, budgets and failure handling are checked
against PostgreSQL in the explicit isolated verifier.

The [coverage map](cleanup-r5-coverage.json) accounts for all 282 R1 methods:

| R1 disposition | Methods | R5 outcome |
| --- | ---: | --- |
| Retain and retarget | 219 | Owned tests; two overlapping architecture checks consolidate into existing canonical guards |
| Adapt paths | 1 | Workspace root/path contract |
| Consolidate scenarios | 4 | Maintained evaluation scenario runners |
| Adapt PostgreSQL semantics | 5 | Actual isolated PostgreSQL quota tests |
| Replace obsolete contracts | 5 | Current API, service settings, startup/import and persistent-expiry contracts |
| Replace UI coverage | 14 | React interaction, error, expiry, safe presentation and pricing checks |
| Retire with capability | 34 | Explicitly identified collection/parser/launcher tests; retained until R6 |

Old root tests, forwarding modules, Streamlit and retired tooling are still on
disk for the next reviewed removal checkpoint. They are no longer maintained
entry points. Use `pharmacy-check`, not old root unittest discovery. The directory
will still look transitional until R6 completes the approved archival/removal work.

## Verification

- Eight maintained Python suites: **238 passed**, 18 explicit PostgreSQL tests
  skipped offline (256 discovered). The affected language/evaluation suites
  were rechecked after the database serialization fix: 84 passed.
- Offline browser suite: **22 passed**, one deployment-only test skipped. A
  focused follow-up also passed the migrated pharmacy ambiguity/real-directory
  presentation scenario. Product source, styling, generated types, contract,
  fixtures and frontend dependency lock remain byte-preserved.
- Deterministic annotated backend baseline: **40/40**. This checks backend
  behavior with known extraction, not hosted model accuracy. Schema export and
  local fixture generation passed without inference.
- Seven workspace wheels and source distributions built; frozen offline lock
  verification passed with existing dependency versions preserved. Evaluation
  installs non-editably without the root package, operations or Streamlit.
- Network-disabled, self-removing installed-image checks passed for core,
  language and operations. Original OpenAPI hashes are preserved; absent or
  unavailable PostgreSQL and file mode are rejected without SQLite fallback.
  Operations exposes eight installed CLI entry points and owned migration assets.
- The user-run verifier passed **all ten aggregated checks and all 18 PostgreSQL
  tests**, including fresh/repeated migrations and import, all-record round-trip,
  owned permissions, failed-message recovery, outages, cooldown forwarding,
  inference-free selection, frontend restore/reset, persistent replacement,
  transactional invalid-import rejection, backup/restore and evaluation resume.

The first isolated attempt found PostgreSQL `SUM(bigint)` returning a `Decimal`
that could not be saved in evaluation JSON. Counts now convert to exact integers.
It also found an unclosed SQLite handle in a legacy-import test fixture on
Windows; fixture connections now close explicitly. The complete rerun passed.
No migration revision or schema change was needed.

Preservation checks compare **982 historical data/report files** with R1 hashes,
26 frontend application/contract/fixture/lock files with R3, and canonical runtime
sources with the pre-R5 capture. Only two runtime helper changes were required:
integer attempt totals and explicit migration URL precedence before reading
configuration. Business logic, providers, prompts, migration revisions and HTTP
contracts remain preserved.

## Evidence and handoff

- [Baseline and source hashes](cleanup-r5-baseline.json)
- [Per-method coverage map](cleanup-r5-coverage.json)
- [Installed-image checks](cleanup-r5-images.json)
- [Successful isolated stack/PostgreSQL report](cleanup-r5-container.json)

Detailed local logs, generated fixtures, builds and offline results are ignored
under `artifacts/cleanup/r5/`. No hosted inference, application-volume changes,
private configuration/ledger changes, network changes or Git publication occurred.
The isolated resources were removed and Docker reports no running containers.

Stop here for user review. R6 will archive historical material with verified
hashes, remove obsolete code/tests/dependencies and finish current navigation.
R7 remains the final complete validation and user demo review.
