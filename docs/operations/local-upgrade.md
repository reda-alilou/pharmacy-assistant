# Existing installation — backup, upgrade and engineering review

Current scope: actual software, safe installation, functional/UI review,
reproducible setup and technical documentation. The user explicitly excludes
presentation, submission packaging and demonstration scripts from this work.
Checkpoint 5 was reviewed/pushed as `fc2538a`; all 20 production checks and 18
assistant PostgreSQL tests passed. Checkpoint 6 engineering implementation/
verification is complete within the user-narrowed scope, ready for checkpoint
review. The normal volume was upgraded separately with verified backup/source
preservation; the agreed installed functional review also passed.

The user runs every container startup/shutdown/replacement command and Git push.
Finish independent work before requesting those commands; stop until the user
returns results. Do not change source during a user-run image verification gate.
Never reset the volume, regenerate existing credentials, re-import catalogue
facts as an upgrade shortcut, print environment files or run hosted inference.

## Recorded preflight, 2026-10-24

- Clean/synchronized `feat/pharmaceutical-analytics`, commit `fc2538a` before work.
- Normal volume `pharmacy-assistant-architecture_postgres_data` exists. Initially
  no normal project containers existed; the user then started only normal
  PostgreSQL. The dedicated test PostgreSQL is also running.
- Existing private `.runtime/compose.env` and `.runtime/postgres.env` are present;
  their database identities/credentials agree. Values were checked in memory,
  not printed. Internal Compose uses `postgres:5432`, host debug configuration
  uses `127.0.0.1:55432`. The normal stack exposes no host database port.
- Read-only database inspection found `core_0001` and `language_0001`, no platform
  schema/runtime role/administrator, and initially no `.runtime/platform.env`.
  After the backup below passed, first-time platform configuration was created;
  original configuration hashes still matched. No existing credential was rotated.

## 1. User starts only normal PostgreSQL

From the repository root, the **user runs**:

```powershell
docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait postgres
```

The explicit project selects the existing named volume, regardless of a shell's
`COMPOSE_PROJECT_NAME`. This starts no assistant/platform/web service, applies no
migrations, imports nothing and adds no host debug port. Stop and wait for the
user's result before connecting. Keep application writers stopped until backup
and restore verification finish.

## 2. Inspect and verify a private backup before upgrade

The maintained backup CLI now supports the normal container without exposing
PostgreSQL on the host. Status is read-only and returns only migration IDs,
admin counts and configuration-state booleans, without account emails/hashes or
database credentials:

```powershell
.\.venv\Scripts\pharmacy-backup.exe status --compose --env-file .runtime/compose.env
```

Choose a **new** private output path; the following example refuses to overwrite
an existing dump or manifest:

```powershell
.\.venv\Scripts\pharmacy-backup.exe backup .runtime/backups/pre-platform-upgrade.dump --compose --env-file .runtime/compose.env
.\.venv\Scripts\pharmacy-backup.exe verify .runtime/backups/pre-platform-upgrade.dump --compose --env-file .runtime/compose.env
```

`--compose` verifies the exact normal project/service/data mount and PostgreSQL
17/database identity. It uses only read-only Docker inspection and `docker exec`
for PostgreSQL's existing clients; it starts/stops no containers or host ports.
Credentials stay inside the container, not argv/output. Dump bytes are streamed
directly to a binary file, avoiding PowerShell text-redirection corruption.

The companion `.manifest.json` contains the dump SHA-256 and per-table persistent
row counts/fingerprints. Both files stay private/ignored. Every persistent table
in `core`, `language` and any existing `platform` schema is compared, including
original source facts/prices/nulls/provenance, quota state and existing accounts/
datasets/resources/access relationships. Temp conversations, account sessions,
throttles and upload staging are excluded as before. Source changes between
backup and verification cause refusal rather than a misleading current pass.

Verification restores only into a fresh `pharmacy_backup_verify_<uuid>` database
on that server, compares row fingerprints and exclusions, checks that the source
is unchanged, then removes only its temporary restore database. It never restores
over the normal database. Require `restore_verified:true`,
`source_database_unchanged:true`, `temporary_restore_database_removed:true`.
Keep the backup: it is useful even after the temporary verification database is
removed. Do not proceed with upgrade after a failed backup/restore check.

The **normal-volume backup/restore passed** on 2026-10-24: all 14 persistent
tables matched, excluded temporary state was absent, the source was unchanged
and the temporary restore database was removed. The retained private backup is
`.runtime/backups/pre-platform-20261024-fd3be1bd.dump` with its companion manifest.
It must remain private and must not be overwritten or removed during upgrade.
See [actual evidence](../validation/platform-checkpoint-6.md).

## 3. Prepare platform configuration and upgrade

Only after the real backup is verified, inspect the status:

- If `.runtime/platform.env` exists, reuse it and its existing administrator.
- If the file is absent and no platform runtime role exists, use the first-time
  `configure` command from [platform setup](platform-accounts.md). It creates a
  new platform-only credential and never rotates original core/language/admin
  credentials. Do not print the file.
- If the role already exists but the private file is missing, stop and recover
  the existing configuration; do not guess, reset a role password or overwrite data.
- If active administrators already exist, reuse them. Otherwise explicitly
  provision a new administrator with the user's locally chosen email/name and
  hidden terminal password. No passwords are requested in chat or passed in argv.

Then follow the [explicit five-revision upgrade](administration.md#upgrade-the-normal-installation-after-acceptance),
using both existing private env files and the same project/volume. The user runs
build/start/setup containers; the agent does not run their lifecycle. Apply only
the platform migration/grant steps needed by this installation; do not re-import
assistant facts or modify frozen migration revisions. No service migrates itself.

For this installation the backup, first-time configuration, five migrations,
runtime grants, explicit administrator provisioning and full startup have all
succeeded. All five normal services are healthy; read-only checks confirm one
active admin, expected runtime isolation and all 14 original assistant persistent
fingerprints unchanged. **Do not rerun the completed first-time sequence below.**
It remains a reference for a different not-yet-upgraded installation. Run one at
a time and stop on any error. Choose the account
identity locally; the provisioning command prompts for a hidden password
(12–128 characters). Never send that password or private env files in chat.

```powershell
docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build

docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate

docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant

$platformAdminEmail = Read-Host 'Administrator email'
$platformAdminName = Read-Host 'Administrator display name'
docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm -it platform-setup provision-admin --email $platformAdminEmail --name $platformAdminName

docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Do not rerun `configure`, `init-env`, source import or administrator provisioning
after success. The agent stops at user-run handoffs and resumes verification only
after the user returns the results. Installed readiness and persistent assistant
fingerprints pass; the subsequently completed signed-in review is recorded below.
Two earlier rejected provisioning attempts created zero users/events; the second
used a password outside the 12–128 character requirement, as confirmed by the user.
The valid retry created exactly one administrator and provisioning event.
The email/name prompt text in `Read-Host` is a label: enter the actual value when
prompted. Never enter or send the administrator password in chat.

## 4. Verify the installed application and review it

Completed on 2026-10-25: the agreed installed feature review passed, covering
listed CSV/analytics checks and four focused workflows (versions/pinning/
comparison; dashboard filters/save/reopen; sharing/revocation; suspension/
restoration). The [phased functional review](../validation/platform-checkpoint-6-functional-review.md)
records user observations separately from retained isolated coverage for other
detailed cases. No required review test or container command remains. Minor
tweaks are deferred; Git publication remains user-controlled. For future tests,
stop work after each user-run handoff until results arrive.

Record actual readiness/migration/runtime-ownership checks after upgrade, retain
pre-upgrade core/language fingerprints for source/quota comparison, and check
that only the expected web entry point is exposed. Do not invoke chat extraction
or hosted inference as a readiness check.

Installed verification on 2026-10-24 passed all 41 service/API assertions and
eight public desktop/mobile screens, with 12 correct protected-route redirects.
All original assistant fingerprints still match. See
[retained installed evidence](../validation/platform-checkpoint-6-installed.json).
The user reports that workspace/profile/administration look correct and defers
other minor tweaks. The reported left-aligned auth card is now fixed, deployed
and confirmed by the user. Real Nginx/API browser probes verify both auth routes
at 320/390/1440/1920px with zero centering error/overflow. Five services remain
healthy. The first update attempt timed out contacting Docker Hub; a later
successful update resolves that gate. No code changed after that build/review.

The **user-run** web-only update below is retained for future frontend changes;
no need to repeat the completed update. No migrations, grants, configuration
generation or administrator provisioning are needed for this visual change.
Stop at user-run handoffs; never send a password in chat. Original installed
probes and the later deployed geometry checks remain separate evidence.

```powershell
docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml build web
docker compose -p pharmacy-assistant-architecture --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --no-deps --wait web
```

Review registration/login/profile, private CSV validation and original values,
exploration, exact/advanced analysis, saved pinned versions, dashboards/mapped
filters, read-only sharing/revocation/onward approval, admin lifecycle/suspension/
logged inspection/activity, and the visitor assistant entry screen. Use clearly
synthetic or attributed data; never change source facts to make a review pass.
Keep clearly labelled review fixtures separate from existing user resources and
preserve the latter. The user signs in with their locally chosen credentials;
no administrator password is requested in chat. Report observed
issues and fix/test them before claiming acceptance.

After functional fixes, rerun only affected checks and the final clean isolated
stack gate when source changes justify it. Normal installation review, clean
setup reproducibility, and isolated regression evidence are separate gates.
Keep [technical evidence](../validation/platform-checkpoint-6.md) and project
context current. No presentation, submission package or slide deck is created.

The stream uses PostgreSQL's native [custom dump format](https://www.postgresql.org/docs/17/app-pgdump.html)
and [restore into a new database](https://www.postgresql.org/docs/17/app-pgrestore.html).
