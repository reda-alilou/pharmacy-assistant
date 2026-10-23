# Pharmaceutical platform — Checkpoint 1 evidence

Date: **2026-10-23**. Status: **implemented and verified in host and isolated
container checks; normal-volume upgrade and user review pending**. Checkpoints 2–6
have not started. This report does not replace or rewrite R7 evidence.

## Scope delivered

Express/TypeScript service and production image recipe; owned transactional SQL
migrations; platform users/sessions/throttles/account activity; restricted runtime
grants and identity checks; explicit administrator provisioning/status/role CLI;
registration/login/logout/profile/password APIs; backend role and own-profile
guards; React Router account/navigation screens and visitor assistant route.
CSRF, PostgreSQL throttling, expiry/revocation, password hashing, session rotation
and last-active-admin safeguards are part of the foundation.

Private datasets, CSV imports, analytics, saved analyses, dashboards, sharing and
the administration workflow are **not implemented**. The account workspace and
admin notice explicitly label future work. No resource tables or fake metrics
claim those capabilities exist.

## Checks actually run

| Gate | Actual result |
| --- | --- |
| Branch/tree inspection | `feat/pharmaceutical-analytics`; existing uncommitted planning changes preserved; no branch/commit/push |
| Platform build | `npm --prefix services/platform run build` passed |
| Node security/HTTP/configuration | 5 tests passed, zero skips |
| Real PostgreSQL | 7 scenario groups plus parent (8 Node results) passed, zero skips |
| Real browser account workflow | 1 React → Vite proxy → Express → PostgreSQL test passed |
| Frontend build | TypeScript and production Vite build passed |
| Frontend lint | Passed, zero errors; only the two preexisting shadcn button/badge hot-refresh warnings |
| Frontend offline browser suite | 26 passed: 4 new account/navigation scenarios and 22 assistant regressions; 1 deployment-only skip |
| Existing offline Python suites | 247 passed; 18 real-assistant-PostgreSQL tests skipped outside the controlled full verifier |
| Backup exclusion | Maintained Python backup command dumped a disposable database; real PostgreSQL restore preserved users/activity/migration receipts and contained no session or throttle rows |
| Isolated production stack | User-run verifier passed all 12 checks, including Nginx account cookie/CSRF/roles, assistant browser flow, outages and stack-replacement persistence |
| Real assistant PostgreSQL | All 18 checks passed, zero skips, in the user-run isolated verifier |
| Isolated cleanup | Verifier confirmed `isolated_resources_removed: true`; application volume untouched |

The user started `deploy/compose.platform-test.yaml`. Account tests connected
only to that dedicated localhost:55433 cluster with a distinct test identity,
created random test databases and removed them. No application database, volume,
private credentials or environment files were modified. Test probe/runtime roles
remain only inside that disposable cluster until the user stops it.

The PostgreSQL scenarios exercised:

- Fresh/repeated checksummed transactional migration; altered-checksum rejection;
  repeated grants; no runtime peer-schema access, DDL, migration writes or activity
  deletion; peer-role denial; rejection of administrative runtime identity.
- Strict analyst-only registration, unique-email normalization/duplicate race,
  session fixation prevention/rotation, hashed identifiers, safe response fields,
  profile persistence and direct API ownership/admin denials.
- Pre-auth and authenticated CSRF/origin rejection, logout invalidation, idle and
  absolute expiry, periodic cleanup and persistence across store reconstruction.
- Database-coordinated concurrent throttle reservations, HTTP 429/Retry-After and
  consistent unknown/wrong/disabled-account login errors.
- Current-password verification, all-session revocation after password changes,
  explicit administrator provisioning, refusal to silently elevate existing users,
  immediate role/status enforcement and concurrent last-admin protection.
- Real dump/restore of platform accounts/activity without live authentication state.

The real account browser test covers direct protected URLs, registration, an
HttpOnly cookie invisible to `document.cookie`, no localStorage account secret,
API ownership/role denials, own-profile persistence across refresh, password
change/login/logout, disabling with an already-issued session, administrator
navigation and explicit future-work labeling. API traces are disabled for this
test. All accounts/passwords used are disposable synthetic test fixtures.

Offline browser checks cover responsive account forms, accessible profile and
registration pages, unavailable-service recovery, visitor introduction, route
guards, and assistant independence from account-service startup. The assistant
suite still checks sources, null/zero/decimal prices, selections/refinements,
refresh/reset, cooldowns, uncertain completion, no POST replay, text safety and
mobile accessibility. A navigation-induced skip-link landmark regression was
fixed and the complete suite rerun successfully.

The Python groups ran 107 core, 43 language, 1 contracts, 7 infrastructure,
10 operations, 41 evaluation, 12 architecture and 44 integration tests (265
results, including 18 intentional PostgreSQL skips). No hosted inference ran.

Initial restricted runs encountered Windows temporary-directory/child-process
permission errors; those were rerun with the required tool access and passed.
The first browser run also exposed a test-import CLI side effect and an account
workflow timeout under simultaneous heavy checks. CLI execution is now isolated
from importable administration helpers; workflow timeouts reflect their complete
interaction scope. The final results above refer to the corrected reruns.

Generated diagnostics/results remain ignored under `artifacts/`, including
`platform-cp1-python.log`, `platform-cp1-web.log`, `web/browser-tests.json`,
account/assistant screenshots in `web/results`, and
`platform-cp1/browser/real-accounts.json`. Source tests and this report remain
the maintained review material; generated historical reports were not modified.

## User-run container acceptance

The user ran the production image build and full-stack verifier. The report at
`2026-10-23T17:04:14.029589+00:00` records **12/12 checks passed**, all **18 real
assistant PostgreSQL tests passed with zero skips**, no hosted inference, no
application-volume modification and successful isolated-resource removal.
The compact report is preserved as
[Checkpoint 1 container evidence](platform-checkpoint-1-container.json), copied
from ignored `artifacts/platform-cp1/full-stack.json`. It includes fresh/repeated
platform migration/grants, account sessions/CSRF/roles through Nginx, internal
ports and service boundaries, core/language/database outage behavior, database
and whole-stack replacement persistence, the real assistant browser workflow,
quota concurrency, legacy backup and evaluation-resume checks. The gateway
account probe deliberately supplies the exact configured Origin because the
isolated browser port is allocated dynamically; the separate real account
browser test verifies the full form workflow through Vite/Express/PostgreSQL.

The agent observed all five isolated services healthy during the run and read
the completed report, but did not execute container lifecycle commands.

## Not yet verified / next user actions

Normal-volume platform migration/grants/provisioning and manual user review
remain pending. The isolated passes do not mean the normal application volume
has been upgraded automatically. No new product checkpoint is started by these
verification results.

Exact upgrade, provisioning, full-stack verification and test-service shutdown
commands are in [platform operations](../operations/platform-accounts.md). The
user retains all container lifecycle actions. The application volume is preserved
and has not been upgraded automatically. Accounts and activity are backed up;
future dataset/upload/sharing retention and backup verification remain later
checkpoint work. There is no claim of public production readiness.

Stop for user review before Checkpoint 2.
