# Checkpoint 1: explicit platform setup and verification

The user runs all container lifecycle commands. These commands preserve the
existing `pharmacy-assistant-architecture_postgres_data` volume, Python revisions,
imports, private environment files and provider configuration. Never regenerate
the existing database credentials for this upgrade. No command below imports
pharmaceutical analytics samples. Checkpoint 2 now implements user-driven imports;
see [dataset upgrade and verification](datasets.md). Existing account configuration
must be reused. The explicit migration command applies all owned revisions;
Checkpoint 3 adds analyses as described in [current upgrade steps](analytics.md).

## Existing configured workspace

From the repository root, install the new service dependencies and create a
**new** private platform-only configuration file. This prepares the credential
for the new role; it never changes existing credentials or overwrites a file:

```powershell
npm ci --prefix services/platform
npm ci --prefix apps/web
npm --prefix services/platform run admin -- configure --source .runtime/compose.env --output .runtime/platform.env
```

Run `configure` only once for this new service. If `.runtime/platform.env` already
exists, reuse it. Its runtime URL is derived from the existing Compose database
address, with a new `pharmacy_platform` identity. Do not print either file or
expanded Compose configuration. The second env file is required for the upgraded
stack. Existing `.runtime/compose.env` and `.runtime/postgres.env` remain unchanged.

Then **the user runs**, in order:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools build platform platform-setup web database-setup
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait postgres
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup migrate
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup grant
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm -it platform-setup provision-admin --email admin@example.com --name "Administrateur"
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Choose the real administrator email/name locally. The administrator password is
entered at a hidden terminal prompt (12–128 characters); it is never an argument
or output. Provisioning creates a new administrator only; it refuses an existing
email and never elevates a preexisting analyst silently. Repeat migrations/grants
are safe and do not rotate role credentials. A checksum mismatch is an error to
investigate, not a reason to edit migration history or reset data.

Open <http://127.0.0.1:8080> for the introduction, `/inscription` or `/connexion`
for accounts, `/profil` for the own profile, `/espace` for the account workspace,
and `/assistant` for the visitor-accessible assistant. Dataset, analysis,
dashboard, sharing and administration workflows are explicitly unavailable.
The admin route shows its later-checkpoint status; it is not an administration UI.

For later start/stop operations reuse both env files:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml down
```

No `--volumes`. Startup never applies migrations, provisions accounts or imports.

## Fresh checkout

First prepare the existing Python/database environment using
[setup](setup.md#new-checkout-with-no-existing-credentials-or-volume). Create the
new platform file immediately after `pharmacy-compose-setup`, before building
images. Apply the existing core/language migrate/grant/import/verify steps, then
platform migrate/grant and explicit administrator provisioning, before starting
the full application. Use both env files for each Compose command. Existing
workspaces must use the upgrade procedure above instead of `init-env`.

## Account operations and host development

The future Users screen is not implemented. Explicit operations remain available
to the database administrator. Example, **user-run**:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml --profile tools run --rm platform-setup set-account --email analyst@example.com --role analyst --active false --confirm
```

This invalidates account sessions immediately and preserves the account/activity.
To reenable, set `--active true`. Role changes require the desired role and active
status explicitly; all permission changes are logged. The final active admin
cannot be disabled/demoted. No permanent account-delete command is provided.
`--confirm` acknowledges the CLI's immediate effects; no user-management UI is
claimed. For automated provisioning only, the host CLI also accepts a private
`--password-file`; never pass passwords as command-line arguments.

For host development, use a dedicated private env file or process environment
with a host-accessible `PLATFORM_DATABASE_URL`, exact `PLATFORM_ORIGIN`
(`http://127.0.0.1:5173` for Vite's default), `PLATFORM_COOKIE_SECURE=false`,
and `PLATFORM_TRUST_PROXY=false`. Run `npm run dev` in `services/platform` and
`apps/web`. The service reads process environment only; Node 22's
`node --env-file=<private-file> dist/server.js` can load an explicit host file.
Do not use the internal `postgres` Compose hostname from a host process. The
existing debug overlay still exposes only the original host debug ports; no
new database or Express host port is added to normal Compose.

## Checks

Offline checks (no container lifecycle or hosted inference):

```powershell
npm --prefix services/platform run build
npm --prefix services/platform test
npm --prefix apps/web run build
npm --prefix apps/web run lint
npm --prefix apps/web test
.\.venv\Scripts\pharmacy-check.exe
```

For actual PostgreSQL/security and React account integration, **the user starts**
the dedicated test service:

```powershell
docker compose -f deploy/compose.platform-test.yaml up -d --wait
```

Then the agent or user can run:

```powershell
npm --prefix services/platform run test:postgres
npm --prefix apps/web run test:accounts
```

The test cluster has fixed **test-only** credentials on localhost:55433 and uses
tmpfs, with a different Compose project and no application volume/environment.
Tests assert this cluster's identity, create random `platform_cp1_*` databases,
and remove only those databases. They exercise migrations/grants, account API
security, concurrent throttling and last-admin changes, session expiry/revocation,
the maintained backup exclusion policy, and the real browser account workflow.
The browser tests start/stop temporary host Vite/Express processes, not containers.
The PostgreSQL test additionally needs the Python workspace and PostgreSQL 17
client tools for the maintained backup check. Tests do not make hosted calls.
Tests leave only unprivileged probe/runtime roles inside the disposable cluster;
their databases are removed. Finally **the user stops** the service:

```powershell
docker compose -f deploy/compose.platform-test.yaml down
```

The separate full application verifier is also **user-run**, after building all
images with `--profile tools build`:

```powershell
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend --output artifacts/platform-cp1/full-stack.json
```

It now explicitly migrates/grants platform before starting its five-service
isolated stack. It retains the original inference-blocked assistant/PostgreSQL
scenarios. It does not replace the dedicated account tests above. The full
container verification and normal-volume upgrade are separate evidence gates;
see [actual results and limits](../validation/platform-checkpoint-1.md).

Backups now retain platform accounts/activity and exclude sessions/auth throttles
alongside the existing temporary-conversation exclusions. Restored runtime grants
must be applied explicitly. Later dataset/upload/sharing backup coverage belongs
to the checkpoints introducing those resources; no such tables exist yet.
