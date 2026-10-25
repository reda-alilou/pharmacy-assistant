# Checkpoint 6 — engineering completion evidence

Dates: **2026-10-24–25**. Status: **engineering implementation/verification
complete within the user-narrowed scope; ready for checkpoint review**. Real
normal backup/upgrade, installed infrastructure/public checks and deployed auth
centering pass. The agreed installed review is complete: listed CSV/analytics
checks and all four focused workflows passed by user reports/screenshots.
Full automated workflows passed separately in isolated stacks. No required
review test remains; Git publication stays under the user's control.

The user reviewed/pushed Checkpoint 5 as `fc2538a`; all 20 CP5 production checks
and 18 assistant PostgreSQL tests passed. They explicitly narrowed remaining work
to the actual project: safe backup/upgrade, functional/UI fixes, reproducible
technical setup/verification/documentation. Presentation/submission materials and
demonstration scripts are outside this work; their external CdC delivery status
is not being claimed complete. No historical validation report is rewritten.

## Normal-installation preflight

- Clean `feat/pharmaceutical-analytics`, synchronized with origin before edits.
- Read-only Docker inventory confirmed the existing normal named volume and no
  normal project containers. The dedicated test PostgreSQL remains running.
- Existing Compose/host private configuration is present with matching database
  identities/credentials, checked in memory without printing values. No platform
  private configuration existed initially. The user then started only normal
  PostgreSQL on the original project/volume. Read-only inspection confirmed
  `core_0001`, `language_0001`, no platform installation/runtime role and zero
  platform administrators. Existing Python revisions need no upgrade/import.
- No container lifecycle, existing credential rotation, normal-volume migration,
  source import, inference or Git publication was performed by the agent.

## Implemented operational preparation

The maintained `pharmacy-backup` CLI adds explicit `--compose` transport and a
read-only status action. It checks exact normal project/container/data-volume/
database/PostgreSQL17 identity, requires application writers stopped, streams a
custom binary dump and writes an exclusive private SHA-256 manifest. It compares
all persistent owned-table fingerprints and retained exclusions after restoring
only into its own new temporary database, then removes that database. Source
changes, mismatched volume, tampered dump and existing output paths are refused.
Host ports and container lifecycle are untouched. Existing host-mode backup
behavior/exclusions remain available and share the same temporary-table list.

| Check | Actual result |
| --- | --- |
| New backup safety unit tests | 7 passed; Docker mocked, no lifecycle, safe volume/identity, binary data, overwrite prevention, failed-restore cleanup, checksum refusal and secret-safe failure output |
| Real PostgreSQL17 stream/restore | 1 passed in the dedicated cluster: new isolated source DB, exact zero/null/leading-zero/UTF-8/timestamp/numeric facts, private synthetic account retained, excluded temporary state absent, SHA-256 fingerprint match, source-change refusal and temporary-restore cleanup; native host clients stand in for Docker exec only |
| Retained administration/real backup | All 12 PostgreSQL results passed after shared backup exclusions were factored; no skips |
| Maintained operations/architecture | 18 + 12 = 30 passed, including all 7 new safety tests and retained command/backup/service-ownership checks |
| Normal-volume backup/restore | Passed against the user-started normal PostgreSQL container: all 14 persistent tables match, excluded temporary state absent, original source unchanged, generated restore database removed |
| First-time platform configuration | Created only after the real restore passed and absent role/file were confirmed; original private configuration hashes unchanged, distinct platform-only credential, internal database/origin valid, Compose `config --quiet` passes and private files are Git-ignored |
| Normal platform migrations/grants | User-run; read-only inspection confirms all five revisions, runtime users/activity INSERT and sequence USAGE, no core/language schema access; all 14 pre-upgrade assistant persistent table fingerprints still match |
| Normal administrator/full startup | Passed: user provisioned the administrator and started all five healthy services; database confirms exactly one active admin, one user and one provisioning event |
| Installed service/API checks | 41 assertions passed: exact project/volume, five source-matching migration checksums, actual per-service runtime connections/schema isolation, read-only app containers, no administrative runtime credentials, only loopback web published, readiness, visitor denials, HttpOnly scoped cookie, missing-CSRF rejection and anonymous logout; all 14 assistant persistent fingerprints still match |
| Installed public browser | 8 desktop/mobile screens passed for home/login/registration/assistant, zero axe violations/overflow/page errors; all 12 protected-route visits redirected to login; assistant reload and unknown-route behavior pass, no inference/API mutations submitted and anonymous check sessions revoked |
| Signed-in UI review/final acceptance | User reports workspace/profile/administration look correct, with minor tweaks they chose to defer; identifies left-aligned login card. This is basic screen review, not a claim of every signed-in workflow |
| Login/registration centering fix | Scoped auth class + automatic inline margins; build/3 retained account browser tests pass, lint exits 0 with 2 preexisting Fast Refresh warnings. Both production-preview and deployed real Nginx/API checks pass both routes at 320/390/1440/1920px, zero centering error/overflow; user confirms fixed |
| Full Stack technical coverage | Mandatory engineering requirements mapped to implemented screens/APIs and checkpoint evidence in the new Full Stack coverage reference; older challenge audit untouched |

The initial sandboxed unit attempt could not access its temporary files; the same
tests passed with normal host process permissions. No production backup pass is
claimed from mocked transport or the dedicated fixture test. Installed CLI help
shows the new `--compose`/status options; normal Compose configuration validation
passed using `config --quiet` without expanded output. `git diff --check` passed;
all React/Express/Python service sources, existing migrations, authoritative data
and CP1–5 historical validation reports were checked unchanged. These checks
finished before the first user-run normal PostgreSQL startup handoff.

Logs are ignored under `artifacts/platform-cp6-{backup-unit,backup-postgres,retained-administration,operations}.log`.
Actual normal backups/manifests belong under ignored `.runtime/backups/`; publish
only nonsecret aggregate verification evidence. See
[safe upgrade phases](../operations/local-upgrade.md).

## Real normal-volume preparation

The private backup `.runtime/backups/pre-platform-20261024-fd3be1bd.dump` and
companion manifest are retained, ignored and must not be committed. Native
`docker exec` transport was exercised against the real volume, in addition to
the independent tests above. Verification reported `restore_verified:true`,
`verified_persistent_tables:14`, `source_database_unchanged:true`,
`temporary_restore_database_removed:true` and no container lifecycle. The
normal source database was never a restore target. Aggregate evidence is retained
at ignored `artifacts/platform-cp6/normal-pre-upgrade.json`.

The original documented relative `configure` paths failed before creating a file:
`npm --prefix` changes the CLI working directory. Absolute paths succeeded;
setup guides now use resolved source/output paths. Original environment hashes
were checked unchanged without printing them or their values. This creates only
the first private platform configuration, not a database role/account/schema.
The agent has applied no platform migration/grant/provisioning to the normal DB.
The user subsequently applied the five platform migrations and runtime grants.
Read-only checks confirm the expected revisions and runtime permissions, no
private peer-schema access, and exact preservation of all 14 assistant persistent
table fingerprints from the pre-upgrade manifest. At that point no administrator existed.
The user confirmed that the second provisioning attempt used a password outside
the required 12–128 characters; zero users and zero provisioning activity records
confirm that neither failed attempt partially created an account. No password
was requested or received in chat.

The user retried with a valid hidden password; provisioning and full startup
succeeded. The agent then verified the running installation without lifecycle
commands or hosted inference. The catalogue has **9,936 records**, language is
available, platform/core readiness pass, and actual connections from each service
use the expected distinct restricted role with no access to peer schemas or DDL.
All 14 original persistent assistant tables remain unchanged after startup/probes.

The visitor browser check used real production assets/Nginx/API, not mocks,
at 1440×1000 and 390×844. It submitted no account registrations, CSV imports,
administrator operations or assistant questions. Each probe's anonymous session
was revoked. Screenshots remain local under ignored `artifacts/platform-cp6/`;
desktop home and mobile assistant were also visually inspected. A helper initially
used a percent-encoded Windows screenshot path; only its eight generated public
PNGs were moved into the correct artifact directory and its new empty directories
removed. The helper now uses `fileURLToPath`; application sources were unaffected.

Exact nonsecret installed reports, including UTC timestamps, are retained in
[installed evidence](platform-checkpoint-6-installed.json). No service source or
image had changed when the installed probes ran. These checks supplement the retained CP5
20-check/18-test isolated production pass; they do not substitute for the user's
signed-in administrator review. The user then reported that the workspace,
profile and administration screens look correct, with minor tweaks deferred,
and identified a left-aligned login card. The shared form class had a maximum
width but zero horizontal margins. A dedicated `platform-auth-card` class now
centers login/registration through `margin-inline:auto`; profile/import forms and
assistant layout remain unchanged. Host browser checks use the real production
build with mocked account bootstrap; no login attempt or normal data write.
Desktop/mobile screenshots were visually inspected. At that handoff the running
normal web image still predated the fix; the agent stopped for the user-run
web rebuild/recreation and review.

The user-run web rebuild then failed before frontend compilation: Docker Hub
metadata requests for the unchanged Node/Nginx base tags timed out. A separate
unauthenticated host HTTPS probe to the registry also failed (`URLError`);
local base-image tags are absent. Read-only Compose inspection confirms all five
normal services remained running/healthy on the previous image. No application
source or network setting was changed after that handoff. This failed attempt
did not require repeated administrator/data/migration setup.

The user subsequently confirmed the fix is good. Final real-browser probes
confirm the updated auth class/rule is served by normal Nginx: both auth routes
have exactly zero horizontal centering error at 320/390/1440/1920px and no
horizontal overflow. The probe's anonymous session was revoked. All five normal
services are still healthy. This resolves the deployment gate; no further code
change was made after the successful build/review.

[Full Stack technical coverage](../project/full-stack-coverage.md) maps the current
CdC to implemented screens/APIs and actual evidence. Current API documentation
was corrected where older checkpoint text still described sharing/admin as future
work or returned the obsolete admin-capability placeholder. These are technical
documentation updates; no historical validation reports were rewritten.

The earlier readiness statement covered engineering implementation and the
limited installed checks above. The user correctly identified that the complete
normal-app feature workflow had not yet been reviewed; proceeding to commit at
that point was premature. [Installed functional review](platform-checkpoint-6-functional-review.md)
now tracks dataset/exploration, all four advanced features, saved versions,
dashboards/filters, sharing/authorization, administration and lifecycle/recovery.
Small explicitly synthetic fixtures and independently checked expected values
are prepared; preparing them did not create normal accounts/data or grant any
permission. The user subsequently reports a successful v1 import. Phase A is now
in progress: user also confirms all original-value, search/filter/sort and reload
checks worked. The user also confirms both invalid CSV rejection/cancellation
checks behaved exactly as expected, preserving the original nine rows/one
version and creating no extra dataset. Phase A is passed by user report;
global sum/mean/min/max are also confirmed by the user's values and grouped
means/denominators by their screenshot (A=15, B=87.5; missing price excluded).
Subsequent screenshots confirm the matching bar chart, price missingness
(8 present/1 missing, 11.11%, source line 10) and IQR (Q1 17.5/Q3 52.5, bounds
-35/105, only price 200 at source line 9 flagged). Recommendation options are
shown in the user's screenshot; user confirms applying the grouped-mean option
and editing it to sums B=350/A=60. Remaining chart checks, version comparison
and phases C–G remain pending. Source/assistant facts remain untouched.

During pie review the assistant mistakenly requested a price-sum measure. The
documented implementation restricts pies to additive counts. The user's screenshots
confirm that incompatible configuration is rejected and obsolete results replaced
by `Résultat à calculer`. Corrected the review to row counts by group (B=5/A=4);
the later screenshot confirms successful pie rendering/counts/shares. This
corrects test guidance, with no application change or weakening of chart rules.
The user's histogram screenshot confirms all four bins 5/2/0/1 and excluded
missing value, and they confirm the scatter plot's eight points/one excluded
missing pair. The user then confirms the temporal chart (January 15/February
87.5) and global mean KPI (51.25). Phase B's scoped aggregate/chart/missingness/
IQR/recommendation checks pass. Explicit version comparison, saved versions and
phases C–G remain pending.

User subsequently confirms the v1 mean KPI is saved/listed, reopens and survives
refresh with version 1, mean/price/KPI settings and recalculated 51.25 intact.
Phase C is in progress: adding v2, verifying pinning after its publication,
explicit v2 execution and version comparison remain pending; phases D–G pending.
On 2026-10-25 user confirms v2 publication with 10 rows and saved-v1 pinning after
publication (version 1 remains selected and returns 51.25). Direct comparison
and its explicit v2 statistics remain pending, followed by the focused dashboard,
sharing/revocation and suspension/restoration workflows.
The user's subsequent screenshots confirm v1/v2 means 51.25/45, sums 410/450,
row counts 9/10 and unique-key differences 1 added/0 removed/2 changed/7 unchanged.
Phase C/focused workflow 1 passes; all four advanced features are now manually
exercised. Dashboard, sharing/revocation and suspension/restoration remain pending.
User confirms creating/saving the dashboard with the copied v1 mean KPI (51.25)
and adding/saving a second grouped-row-count chart (B=5/A=4). Dashboard review
now awaits interactive filter mappings and save/reopen behavior; the other two
focused workflows remain pending.

The user subsequently confirms saved explicit filter mappings to both widgets:
A gives KPI 15/count 4; after reopen/refresh, B gives KPI 87.5/count 5; resetting
reader filters restores KPI 51.25/counts A=4/B=5. The focused dashboard workflow
passes by user report. Sharing/read-only/revocation and dataset suspension/
restoration remain pending; detailed layout cases retain isolated coverage.

CP6 acceptance and Git publication wait for that feature review and any fixes.
Focused sharing/revocation subsequently passes by user report: the separate
reader's dashboard-only grant permits results and allowed filters without edit
controls; the unshared dataset's direct URL is denied without rows. Revoking the
dashboard grant blocks its results on reader refresh. The reader account remains,
its grant is revoked and no dataset grant was created. Test-dataset suspension/
restoration is the last focused installed workflow pending.
On 2026-10-25 the user accepted a focused remainder of four installed workflows:
version pinning/comparison, dashboard filters/save/reopen, sharing/revocation,
and dataset suspension/restoration. Other detailed cases retain the prior real
isolated automated coverage and are not claimed manually passed. The broader
step-by-step manual plan was unnecessarily granular for the remaining review.
The final user report confirms suspension blocks both owner widgets without old
results, restoration returns mean 51.25/counts A=4/B=5, and the revoked reader
remains denied. All four focused workflows now pass; the installed review is
complete within the agreed scope. No application code changed during this review.
The restored/unshared TEST CP6 dataset with v1/v2, saved analysis/dashboard and
ordinary reader account are retained; dashboard grant revoked. Cleanup remains
optional and was not performed. CP6 engineering implementation/verification is
ready for checkpoint review, with no required test pending.
Other minor tweaks remain deferred; two preexisting Fast Refresh lint warnings
remain. Changes are uncommitted and unpublished; the user retains Git publication
and container lifecycle control. No external presentation/submission claim.
