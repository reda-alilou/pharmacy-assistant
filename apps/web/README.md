# Platform and assistant frontend

React, TypeScript and Vite, with Tailwind CSS and project-owned shadcn/ui controls.
React Router provides introduction, account/profile, private datasets/import/
exploration, analysis builder/charts/private saved definitions and separate
`/assistant` routes. Dashboards, sharing and administration remain future
checkpoints. The interface is French;
backend multilingual answers remain unchanged. No
frontend environment variable contains a provider key or database credential.

## Local development

From `apps/web/` with Node 22.23.2 and npm available:

```powershell
npm ci
npm run dev
```

Vite listens on localhost and forwards `/api/*` to core at
`http://127.0.0.1:18000`, available through the explicit Compose debug overlay.
Set `DEV_API_ORIGIN` before starting Vite if using another core address. This is
development proxy configuration, not a value embedded in production assets.
`/platform-api/*` separately forwards to Express at `http://127.0.0.1:3000`;
`DEV_PLATFORM_ORIGIN` overrides this development target. Configure the Express
`PLATFORM_ORIGIN` to match the exact Vite browser origin for CSRF protection.
Starting backend services remains an explicit user action.

For the integrated demo, first apply the [analytics upgrade](../../docs/operations/analytics.md)
(and initial account setup if needed), then use the five-container stack from the repository root:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml build web
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>. Nginx serves the built assets and proxies `/api` to
core and `/platform-api` to the new Node/Express runtime. No migration or import occurs at startup.

`features/datasets` owns the guided CSV wizard and resumable import route,
metadata/archive/deletion controls and overview/data/columns/quality/versions.
The table queries Express for full-version search/typed filters/sort/pagination;
it does not filter only visible rows. Typed/original values and missingness stay
distinct. Column profiles are server-generated; `features/analytics` provides
advanced analyses. The wizard links an attributed downloadable sample and requires explicit
validation/publication. Dataset modules load separately from the main bundle.

`npm run test:datasets` runs two real React/Express/PostgreSQL workflows against
the user-started dedicated test cluster, with desktop/mobile axe checks. It creates
and removes only random test databases and temporary host processes. The same
suite runs against production Nginx when the user invokes the full verifier.
See [dataset API](../../docs/architecture/datasets-api.md) and
[Checkpoint 2 evidence](../../docs/validation/platform-checkpoint-2.md).

`features/analytics` adds `/analyses`, `/analyses/nouvelle` and `/analyses/:id`,
saved immutable source references, typed aggregation/grouping, pharmaceutical
templates and four advanced features. Recommendations create editable chart
definitions; SVG KPI/bar/line/pie/histogram/scatter views retain exact table
alternatives. Values stay decimal strings; only server-normalized coordinates
are used for plotting. Save is explicit, all controls lock during operations,
and obsolete results clear on configuration changes/failures. Whole-dataset
switches reset settings rather than implying equivalence; version switches retain
settings for server validation. The assistant's private temporary conversation
mechanism stays separate from accounts and analytical state.

`npm run test:analytics` uses a random dedicated PostgreSQL test database and
temporary host Vite/Express processes, or production Nginx when the user runs the
full isolated verifier. It covers the complete advanced workflow, saved source
pinning, every chart type, permission denial, duplicate keys, large decimals,
pending-save protection and desktop/mobile accessibility. It performs no hosted
inference and retains no credential-bearing network traces. See
[calculation/API contract](../../docs/architecture/analytics-api.md),
[current operations](../../docs/operations/analytics.md) and
[Checkpoint 3 evidence](../../docs/validation/platform-checkpoint-3.md).

## Test on a phone over Wi-Fi

Connect the phone to the laptop's Wi-Fi network. From the repository root, find
the Wi-Fi IPv4 address with `ipconfig`, then enable the optional web-only binding:

```powershell
$env:PHONE_HOST_IP = "192.168.1.7" # Replace with the current Wi-Fi IPv4 address
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml -f deploy/compose.phone.yaml up -d --no-deps --wait web
```

Open `http://192.168.1.7:8080/assistant` on the phone, using the actual address above.
The core, language service and database remain internal. This overlay binds web
to the specified Wi-Fi address instead of localhost; use that URL on the laptop
too during testing. Leave the other four services running. Account writes remain restricted to the
configured exact origin and loopback HTTP; this phone overlay is for the assistant,
not LAN account authentication. Accounts on LAN would require HTTPS configuration. It is intended for
local testing on a trusted Wi-Fi network, not public deployment. If blocked,
check Windows Firewall and router guest/client isolation; do not disable the
firewall. New questions use the same server-side inference quota on both devices.

Return web to its default localhost binding afterward:

```powershell
docker compose --env-file .runtime/compose.env --env-file .runtime/platform.env -f deploy/compose.yaml up -d --no-deps --wait web
Remove-Item Env:PHONE_HOST_IP
```

The overlay uses Compose's
[`!override` port replacement](https://docs.docker.com/reference/compose-file/merge/#replace-value),
which requires Compose 2.24.4 or later. Browser request IDs use cryptographic
[`getRandomValues`](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues),
available on HTTP LAN origins, rather than relying on HTTPS-only `randomUUID`.
Conversation bearer tokens continue to be generated by core.

## Contracts and checks

```powershell
# From the repository root; does not load runtime settings or start services:
.\.venv\Scripts\pharmacy-export-contract.exe

# From apps/web/:
npm run types:api
npm run build
npm run lint
npm test
```

`src/shared/api/generated.ts` comes from the checked-in core OpenAPI schema. Zod checks
the patient-facing response fields at runtime and discards provider/debug fields.
The Python contract test detects schema drift. Regenerate both files when the
core contract changes; review the resulting diff.

Browser tests use offline fixtures and mocked API responses. On Windows they
use installed Edge by default. Set `PLAYWRIGHT_CHANNEL=chrome` for installed
Chrome, or install Playwright Chromium and set the channel to `chromium`.
Tests cover actual interactions, restore/reset, expiry, uncertain requests,
quota errors, responsive layout, safe links and accessibility. Reports,
screenshots and traces go to ignored root `artifacts/web/`, preserving historical
evidence. Playwright starts and stops its own local Vite server for offline tests.

`tests/browser/deployment.spec.ts` is skipped in the normal suite. Explicit integration
verification from the root runs it against a fresh real Compose stack:

```powershell
.\.venv\Scripts\pharmacy-compose-verify.exe --run-isolated --frontend
```

This requires built images and installed frontend dependencies/browser. It
blocks hosted inference, seeds only a synthetic clarification, checks quota
handling, selection, refresh and reset, and removes only its own test resources.

## Code ownership

| Location | Responsibility |
| --- | --- |
| `src/app/` | Entry point, Router/application composition and styles |
| `src/features/accounts/` | Account API validation, in-memory CSRF/session view, forms and route guards |
| `src/features/chat/` | Conversation view, temporary state, restore/reset and recovery |
| `src/features/results/` | Medication/pharmacy cards, offered choices, sources and factual formatting |
| `src/shared/api/` | HTTP client, runtime response validation and generated core types |
| `src/shared/ui/`, `src/shared/lib/` | Reusable controls and styling utility |
| `tests/browser/` | Offline interaction/accessibility tests and explicit deployment verification |
| `tests/fixtures/`, `tests/support/` | Recorded factual fixtures and mocked HTTP support |

The Vite alias `@/` resolves to `src/`. Shared code does not import feature code;
results do not own chat session state. API paths, sessionStorage keys, markup,
styles and factual behavior are preserved from the reviewed interface.

## State and recovery

The browser stores only the active bearer token and its expiry in sessionStorage,
plus a separate cooldown deadline. Messages remain on the server with the same
30-minute inactivity expiry as context. A refresh restores through a read-only
GET; it never resends a question or renews expiry. Closing the tab drops its
browser token. If storage is blocked, an explicit notice explains that refresh
restoration is unavailable.

Typed questions and offered choices each have a unique request ID. The client
never automatically repeats a POST. After an uncertain result it tries one
read-only restore; pending requests require explicit verification. Successful
server results can be recovered without another inference call. Failed typed
questions remain visible with explicit edit/retry actions; an unsaved question
is retained only in memory if it never reached core. Cooldowns block inference
actions while valid offered choices remain usable. Reset clears local state
only after server invalidation succeeds or the token is already expired.

Amounts and totals displayed in cards come from core; the browser formats them
but does no price arithmetic. Source dates and unavailable facts stay visible.
The assistant has no account-based patient history, analytics, raw JSON viewer
or local model fallback. Account sessions use a separate HttpOnly cookie; only
the independent assistant conversation bearer uses sessionStorage.

The user-started dedicated PostgreSQL service supports `npm run test:accounts`
for the real React/Express/PostgreSQL workflow; see
[platform verification commands](../../docs/operations/platform-accounts.md#checks).
