# R1 — Baseline and cleanup inventory

Status: **complete and reviewed; the user authorized R2**. During R1 no application code, tests,
deployment files, import data or historical evidence has been moved, deleted or
changed. See [R2](cleanup-r2.md) for current implementation progress. The R1 JSON
snapshots preserve the state recorded at the original review boundary.

## Saved version

Branch `refactor/web-architecture`, commit
`b1bca1693c6b351edd95f40aed4ced7e19e78520`: "Complete checkpoint 5: React chat
and phone testing". Local HEAD, the remote-tracking branch and a fresh read-only
GitHub check all match. The user accepted the interface on laptop/phone and
stopped the containers. R1 starts/stops no application or isolated test stack.

## What to review

The [cleanup plan](../development/cleanup-plan.md) records the approved structure,
ownership rules, seven checkpoints and review gates.

The [file inventory](cleanup-r1-inventory.json) covers **all 1,203 tracked files**
at the saved commit. Every entry records its original path, committed blob ID,
content/checkout hashes, disposition, target paths, checkpoint and reason. These
counts describe future actions, not work already performed:

| Planned disposition | Files |
| --- | ---: |
| Archive unchanged | 1,000 |
| Archive original and write a current replacement document | 2 |
| Move canonical code/configuration/data | 99 |
| Split by responsibility | 8 |
| Consolidate evaluation commands | 3 |
| Migrate test coverage | 25 |
| Delete obsolete code/configuration/tests after coverage migration | 47 |
| Keep/update root/deployment configuration or references | 19 |

Raw source snapshots are **archived, not deleted**. The two authoritative JSONL
inputs remain active and move to `data/imports` in R6; evaluation datasets stay
under `data/evaluation`. Earlier checkpoints use current data paths until then.

The [test map](cleanup-r1-test-map.json) assigns a future disposition to every
**282 Python test methods**, plus all **20 offline browser scenarios and one
opt-in real-stack browser scenario**:

| Python coverage disposition | Methods |
| --- | ---: |
| Preserve/retarget | 219 |
| Replace obsolete import/settings/startup/expiry contracts | 5 |
| Adapt repository-path expectations | 1 |
| Port UI behavior to React | 14 |
| Consolidate evaluation-scenario coverage | 4 |
| Preserve quota concurrency/durability semantics against PostgreSQL | 5 |
| Retire with collection/enrichment/launcher-only capabilities | 34 |

Replacement tests are planned, not implemented. Matching, arithmetic, sources,
failed messages, explicit retries, offered choices, expiry and reset remain
required. The map replaces obsolete automatic resend on expired choices and
combined-secret settings expectations with the new architecture's contracts.

The [dependency inventory](cleanup-r1-dependencies.json) records static imports,
module/patch literals and path assumptions. Test mocks, Docker copy paths,
migration configuration, `parents[2]`, fixture/report paths and evaluation
fingerprints must move together. Static references alone are not proof of
non-use; CLI/configuration and tests also govern deletion.
Cross-test helper imports are also recorded: fixtures currently borrowed from
`test_chat`, `test_gemini`, `test_demo` and other modules need explicit new test
support homes before those files move or disappear. Non-Python path consumers
include Docker/Compose, Alembic, frontend aliases/entry points and fixture manifests.

## Verification

The [baseline report](cleanup-r1-baseline.json) captures public OpenAPI hashes and
route lists, factual input hashes/counts, inventory totals and check results.
Schema inspection entered no lifespan, read no runtime credentials, connected to
no database and invoked no inference.

| Fresh R1 check | Result |
| --- | --- |
| Offline Python suite | 272 passed, 10 opt-in PostgreSQL skips; 282 discovered |
| TypeScript/Vite production build | Passed |
| Frontend lint | No errors; two existing shadcn hot-refresh warnings |
| Offline uv lock verification | Passed |
| Python source/wheel builds | Passed |
| Core OpenAPI vs checked-in frontend schema | Identical |
| Import identities | 9,936 unique medication IDs; 327 unique pharmacy IDs |
| Runtime/data/evidence vs saved commit | Unchanged |

New logs/build products are in ignored `artifacts/cleanup/r1/`; their hashes are
in the baseline report. Initial approval-review usage limits were resolved by
retrying through normal approval after resumption. An initial GitHub timeout was
followed by successful read-only verification. No approval bypass or network
setting change was used.

Checkpoint 5's 20 passing browser scenarios, nine passing isolated Compose
checks, and user laptop/phone review are **reused historical evidence, not fresh
R1 runs**. Their implementation and tests are unchanged. Running the browser suite
normally would overwrite checkpoint 5 screenshots/reports, so R1 preserves those
files. No fresh PostgreSQL or Docker check is claimed while services are stopped.

## Changes and review gate

R1 adds only the plan, inventories, baseline/review documentation, decision-log
entry and handoff links. `.gitignore` excludes `/artifacts/` so generated output
does not repopulate the repository. R1 documentation remains active and is not
part of the historical-baseline archive set.

No provider/model/prompt, behavior, credentials, private ledger, data, migration
or application volume changed. No hosted inference, scraping, Docker lifecycle
action, network setting change, commit or push was performed.

Review the dispositions before authorizing **R2: separate backend packages**.
The inventory does not authorize early deletion or automatic work on R2–R7.
