# R7 — Final validation

Status: **complete, 2026-10-20**. Repository cleanup R1–R7 and the remaining
D018 validation are finished. The user confirmed the laptop demo works perfectly
and explicitly waived the final physical-phone review. They suspected campus
Wi-Fi restrictions; network isolation was not confirmed. Automated mobile browser
checks passed. Earlier physical-phone acceptance is historical evidence, not a
new R7 device test.

## What was verified

The working tree is uncommitted. Fresh-install verification used a clean export
of **1,290 publishable files**, with SHA-256 hashes back to the source. This was
not a remote clone or a committed checkout. Existing environments, credentials,
runtime state, ignored local archive/downloads, npm dependencies and prior
generated artifacts were excluded.

| Gate | Result | Evidence |
| --- | --- | --- |
| Independent installation | Six frozen, noneditable installs with owned dependencies; installed import origins, service boundaries and CLI checks passed | [Installs](cleanup-r7-installs.json) |
| Python checks | 247 offline tests passed; 18 PostgreSQL tests intentionally skipped offline and all passed against real PostgreSQL in the isolated run | [Baseline](cleanup-r7-baseline.json) |
| Fresh frontend | Offline `npm ci`, production build, type regeneration and lint passed; generated types unchanged; two preexisting hot-refresh warnings, zero lint errors | [Baseline](cleanup-r7-baseline.json) |
| Browser checks | 22 offline checks passed, including mobile layouts; one deployment-only test skipped offline and covered by real-stack verification | [Baseline](cleanup-r7-baseline.json), [stack](cleanup-r7-container.json) |
| Distribution builds | All six wheels/source distributions and frozen offline lock validation passed | [Baseline](cleanup-r7-baseline.json) |
| Images | All four images built from the clean export; installed-image checks passed; fresh frontend assets match the web image byte for byte | [Images](cleanup-r7-images.json) |
| Contracts and offline tools | Original OpenAPI preserved, fixture factual fields preserved, all 1,004 archive mappings verified, 40 annotated backend oracle cases passed | [Commands](cleanup-r7-commands.json) |
| Real isolated stack | All ten scenarios and 18 PostgreSQL tests passed, zero PostgreSQL skips | [Container report](cleanup-r7-container.json) |
| Manual review | Laptop passed; final physical-phone review waived by the user | [Exact user statements](cleanup-r7-user-review.json) |
| Temporary resources | Test stack removed its own resources; disposable export and seven environments removed; compact evidence retained | [Cleanup](cleanup-r7-temporary-cleanup.json) |

The real-stack run covered explicit fresh/existing-revision migrations, repeated
imports, the full 9,936-medication/327-pharmacy round trip, database ownership,
backup/restore, outages and recovery, concurrent quotas and evaluation resume,
transcript restoration, offered choices, refresh/reset, database replacement and
whole-stack persistence. Inference was mocked; no automated hosted requests were
made. The 40 annotated oracle cases check local behavior, not current model accuracy.

The exported frontend required an empty temporary Git boundary so normal ignore
rules matched a checkout. No commit was created. That boundary and the export
were removed after validation. [Export hashes](cleanup-r7-export.json) identify
the tested files; final handoff documentation was updated afterward. No runtime
source changes were needed during R7.

## Handoff

The production-style structure is implemented: independently installable core
and language services, shared packages, organized React application, owned
PostgreSQL migrations, operations/evaluation tools and a verified historical
archive. Streamlit, compatibility modules and obsolete workflows are retired.
Private ignored raw/staging files remain preserved in `archive/local/`.

Detailed logs, wheels/source distributions, screenshots, export hashes and
verified static assets remain under ignored `artifacts/cleanup/r7/`. Earlier
R1–R6 JSON reports remain checkpoint snapshots. Current navigation is in
[PROJECT_CONTEXT.md](../../PROJECT_CONTEXT.md), the
[setup guide](../operations/setup.md) and [tooling guide](../operations/tooling.md).

The user controls the normal demo stack, which was started for laptop review.
No agent-owned temporary containers remain. When finished, the user can stop the
demo without deleting its database:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml down
```

No application data, private credentials/ledgers or environment files were changed
by validation. No system network/DNS changes, scraping, primary Git commits or
pushes occurred during R7. User-initiated demo provider calls were not measured.

## Remaining work and limits

Engineering cleanup is complete; committing/pushing these uncommitted changes
is a separate user-controlled step. The cited related-work study and final
submission/presentation remain separate work, without automatic authorization
to begin them.

This remains a local challenge demo and learning project. Historical model
metrics retain their original version limits. There was no new hosted accuracy
measurement, independent clinical/native-speaker evaluation, or live validation
of pharmacy stock, hours or duty schedules. Provider availability and quotas
still affect new typed questions. Current physical-phone access on campus Wi-Fi
was not established and was explicitly waived.
