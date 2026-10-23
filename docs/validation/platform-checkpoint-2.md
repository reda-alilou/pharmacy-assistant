# Pharmaceutical platform — Checkpoint 2 evidence

Date: **2026-10-23**. Status: **implemented and verified, including the follow-up
metadata-save fix in rebuilt production images**. All 14 isolated checks and
18 assistant PostgreSQL tests pass. User review and normal-volume upgrade remain pending. The user authorized continuation
after Checkpoint 1. Checkpoints 3–6 have not started. Historical Checkpoint 1 and
R7 reports are unchanged and do not validate this work.

## Scope delivered

Guided private CSV uploads, preview/configuration, complete validation and report
download, idempotent atomic publication, immutable import versions, original and
typed values, editable metadata, archive/restore and dependency-reviewed deletion.
React dataset views provide full-version server search/typed filters/sort/pages,
counts, column statistics, completeness and version history. Backend ownership
applies to administrators too. Account disabling is checked within write
transactions, including publication after potentially lengthy validation.

Owned `0002_datasets.sql` and explicit restricted grants extend populated account
tables without rewriting the account or Python revisions. Backup/restore retains
datasets/originals/receipts/dependencies and excludes staged uploads, sessions and
temporary patient history. An explicit offline exporter and attributed 28-record
pharmaceutical sample use the normal user import workflow. No Python-private
table access, automatic imports or changes to original source facts.

Analysis/grouping/charts, the four advanced analytical features, dashboards,
sharing, suspension/inspection and administrative UI are later checkpoints.
Current Quality is completeness profiling only; Analysis is a future-work notice.
The deletion dependency registry is a tested safeguard for future resources, not
an implemented saved-analysis or sharing feature.

## Checks actually run

| Gate | Actual result |
| --- | --- |
| Branch/tree | `feat/pharmaceutical-analytics`; existing planning/account edits retained; no branch/commit/push |
| Platform build | TypeScript passed |
| Node unit/security/HTTP/configuration/CSV | 8 tests passed, zero skips |
| Real dataset PostgreSQL | 9 scenario groups plus parent: 10 results passed, zero skips; final run 26.4 s |
| Retained account PostgreSQL | 7 scenario groups plus parent: 8 results passed, zero skips |
| Real dataset browser | 2 React → Vite → Express → PostgreSQL workflows passed; desktop/mobile axe, overflow and held-preview race checks included; final run 35.7 s |
| Real account browser | 1 workflow passed against dedicated PostgreSQL |
| Frontend build/lint | Passed; two preexisting button/badge fast-refresh warnings, no lint errors |
| Offline frontend | 26 passed, 1 deployment-only skip; retained assistant behavior covered |
| Offline Python | 247 passed, 18 intentional real-PostgreSQL skips |
| Final focused operations/architecture | 12 passed after verifier/backup updates |
| Maintained backup/restore | Real dump/restore preserves dataset versions, configuration, profiles, typed/original cells and permanent receipts; staging/authentication state absent |
| Initial user-run images/Nginx/full stack | 13 checks passed; 18 assistant PostgreSQL tests passed, zero skips; no hosted inference/application-volume modification; isolated cleanup confirmed |
| Final-source production gate | All 14 checks passed, including dataset browser workflows through Nginx; all 18 assistant PostgreSQL tests passed, zero skips; cleanup/no inference/no application-volume modification confirmed |
| Follow-up metadata review | New offline held-save/draft-recovery regression and four account/navigation checks passed (5 total, 29.8 s); frontend build/lint passed; rebuilt production images passed all 14 checks and 18 assistant PostgreSQL tests, zero skips |

Commands and environment prerequisites are in [dataset operations](../operations/datasets.md).
Real database tests refuse application URLs and create/remove random databases
in the separately user-started dedicated test cluster. Browser tests use synthetic
accounts and omit credential-bearing traces. No agent container lifecycle command
was executed.

Local ignored logs: `artifacts/platform-cp2-datasets.log`,
`platform-cp2-browser.log`, `platform-cp2-account-browser.log`,
`platform-cp2-web.log`, `platform-cp2-python.log` and `platform-cp2-operations.log`.
The initial successful report is `artifacts/platform-cp2/full-stack.json`.
The passing final source gate is `artifacts/platform-cp2/full-stack-final.json`,
reported at `2026-10-23T18:06:14.165839+00:00` (verifier start timestamp).
[Tracked final container evidence](platform-checkpoint-2-container.json) records
the inspected result. Its temporary project was
`pharmacy-checkpoint4-test-e83b7810cc54478c9efa03459768fe20`; the legacy helper's
project prefix refers to the older architecture phase, not a completed analytics
Checkpoint 4. That isolated project/volume was removed.

## What the real database scenarios cover

- Upgrade from populated Checkpoint 1 schema/checksum with accounts and sessions
  preserved, repeat migration/grants, peer-schema isolation and immutable privileges.
- Exact identifiers/zero/false/null/large decimals, six-digit timestamp precision,
  raw originals, full-version profiles and idempotent publication.
- BOM/Unicode/embedded quotes/newlines, malformed widths/headers, late invalid
  values, error truncation and no partial datasets. 100 long column headers require
  more than the account JSON limit and validate through the dataset API.
- Search/count across all pages, typed numeric/date/boolean filters and ranges,
  AND/selected-value OR, stable typed sorting, missing/present and injection input.
- Anonymous/CSRF/cross-account denial, including administrators; revision conflicts,
  archive behavior, old-version stability and upload expiry.
- Synthetic mid-import database failure rolls back all published state. Disabling
  an owner after validation blocks publication. Explicit deletion checks real
  dependency registrations and removes versions only when dependencies are absent.
- Complete source round trip and measured limits, plus real backup/restore using
  the maintained Python command, with temporary state excluded.

## Measured operating bounds

Enforced bounds: 10 MiB, 25,000 rows, 100 columns, 1,000,000 cells and 16,384 UTF-16
units per cell. At most five active staged uploads/account, one heavy CSV operation
per Express process, one-hour retention. Reports retain the first 1,000 issues
while counting all issues. Dataset JSON is 128 KiB; account JSON remains 16 KiB.

Final local PostgreSQL run, measured **2026-10-23 17:54:41 UTC**:

| Fixture | Data rows | CSV bytes | Publication | Filtered page query |
| --- | ---: | ---: | ---: | ---: |
| Complete pharmaceutical source | 9,936 | 2,182,846 | 1,136 ms | 7 ms |
| Larger synthetic fixture | 25,000 | 884,779 | 3,050 ms | 13 ms |
| Wide synthetic fixture, 100 columns | 10,000 | 2,900,990 | 13,338 ms | 49 ms |

All 9,936 source records and 1,126 missing prices round-trip; source identities,
observations and original strings remain intact. These are local measurements,
not a throughput/latency guarantee or simultaneous-user benchmark. One earlier
wide run took 62.4 seconds while several heavy suites competed for CPU, above
the 60-second browser/gateway deadline. Run benchmark suites sequentially; a
client timeout requires read-only import-state recovery before retrying. Atomic
publication/idempotence handles uncertain results. Multi-process workers and
larger production capacity are not established by these measurements.

## Failures found and corrected during implementation

Database tests exposed a count-query parameter mismatch when sorting; count
parameters are now separate from the row-query sort parameters. Real source
timestamps required preserving six fractional digits rather than restricting
input to milliseconds. A new-version browser request initially included extra
dataset fields in strict metadata; it now sends only metadata fields. Axe found
an invalid label on a generic filter container; it now has a group role.

An assistant busy-state browser test used a short timed mock that expired under
CPU load; its response is now held until disabled controls are asserted. This
test change does not alter assistant request behavior.

The final production browser run exposed a genuine preview race: controls could
be edited while an inferred-type response was in flight, and that response could
replace the edit. The import editor now disables all form controls while an
operation is pending. The real browser suite holds a preview response and asserts
the disabled state before proceeding. Both host workflows passed after the fix;
the rebuilt frontend then passed both workflows through production Nginx (15.1 s).
The first unsuccessful attempt remains documented here rather than counted as a
pass. The final report validates the corrected image.

## Remaining acceptance

- User-run explicit migration/grants against the preserved normal volume, if not
  already performed. Isolated success is not evidence of a normal-volume upgrade.
- User review of dataset workflow and layout, including an own CSV. Automated
  mobile browser checks do not claim a physical-phone review.
- Stop for review before Checkpoint 3. No advanced analytics/dashboard/sharing
  functionality is implied by the current navigation or profile summaries.

## Follow-up review — metadata save in flight

The user's request for another confidence check prompted an acceptance/source
cross-check after the passing container run. This found a second pending-response
edge case: metadata fields and their reset action remained editable during a
save. An edit made after submitting could be discarded when the successful save
refreshed the dataset. Metadata fields/reset now disable during pending operations;
errors re-enable them and preserve the unsaved draft.

A new offline browser regression holds the save response, checks every metadata
field and the reset action, then verifies success persistence and failure recovery.
It failed against the prior source (title remained enabled), confirming the gap.
After the fix, all five focused browser checks passed; a textarea locator was
corrected to use its accessible textbox role. Build and lint passed with only
the two existing fast-refresh warnings. Log: `artifacts/platform-cp2-review-browser.log`.
The real dataset browser workflow also now checks a held metadata save and persistence
after refresh. The attempted host real-database rerun could not start because the
dedicated user-controlled database was stopped (`ECONNREFUSED` on port 55433);
this is not counted as a passing check. No container was started by the agent.

The earlier passing [container report](platform-checkpoint-2-container.json) is
retained as evidence for that earlier image. The user rebuilt web and reran the
isolated verifier with the extended metadata-save browser assertions. All 14
checks passed, including both real dataset browser workflows through production
Nginx, and all 18 assistant PostgreSQL tests passed with zero skips. Cleanup,
no hosted inference and no application-volume modification were confirmed.

Latest [tracked review container report](platform-checkpoint-2-review-container.json)
matches `artifacts/platform-cp2/full-stack-review.json`, reported at
`2026-10-23T18:43:34.817823+00:00` (verifier start timestamp), project
`pharmacy-checkpoint4-test-7bd25fd975a54d87bca0287d7b5ce222`. The user-provided
build output confirms the web image was rebuilt before this run. No required
automated gate remains failing or pending; normal-volume upgrade, manual user
acceptance and the documented heavy-load timeout limitation remain separate.
