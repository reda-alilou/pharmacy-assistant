# R3 — Frontend organization

Status: **complete and reviewed**. All offline checks and all nine user-run
real-stack checks passed. The user subsequently authorized R4; see
`cleanup-r4.md` for current work. The JSON evidence remains frozen at R3's handoff.

## Changes

React now lives in `apps/web/`, including its own Dockerfile, dependency lockfile,
Vite/TypeScript configuration, core OpenAPI snapshot and browser tests.

| Location | Owns |
| --- | --- |
| `src/app/` | Entry point, composition and existing styles |
| `src/features/chat/components/` | Conversation interface |
| `src/features/chat/state/` | Temporary conversation controller, recovery and reset |
| `src/features/results/components/` | Results, medication/pharmacy cards, clarification and source details |
| `src/features/results/lib/` | Factual formatting and safe link handling |
| `src/shared/api/` | HTTP client, Zod schemas and generated types |
| `src/shared/ui/`, `src/shared/lib/` | Reusable controls and style utility |
| `tests/browser/`, `tests/support/`, `tests/fixtures/` | Existing browser scenarios, mocked API and factual fixtures |

Result components were extracted at their existing function boundaries. The
reviewed French markup, styles, API URLs, sessionStorage keys, request/recovery
behavior and price/source handling are preserved. No frontend package versions
changed. No fixture or type regeneration is required for a path-only move.

Compose now builds `apps/web/Dockerfile` from the existing repository context.
The Docker allowlist excludes the relocated tests, dependencies and build caches.
The web service, port, nginx routing, phone/debug overlays and volume identity
are unchanged. Core/language images remain the verified R2 images.

Contract export, fixture generation, Python contract checks and the isolated
Compose verifier use the new paths. Their command names remain unchanged until
R5. Browser reports/screenshots/traces now use ignored `artifacts/web/`;
deployment captures use `artifacts/compose/`. Saved `reports/` are preserved.

## Checks

- Host build passed. Lint passed with the same two existing Fast Refresh warnings
  in the shared shadcn button/badge files; there are no lint errors.
- Both core contract/factual fixture checks passed. The lockfile, generated API
  types, OpenAPI snapshot, fixtures and styles are byte-preserved.
- All 20 offline browser scenarios passed; the deployment scenario is skipped
  until the explicit isolated-stack run. Checks include 390px phone layout,
  accessibility, refresh/reset, expiry, uncertain requests, cooldowns, safe sources
  and inference-free choices. The first mobile accessibility scan was interrupted
  by a navigation; an isolated rerun passed. It now waits for the interface to be
  ready, and the full final suite passed with no retries.
- Both phone screenshots match the saved screenshots pixel for pixel. Desktop
  captures retain their dimensions and reviewed layout, with transient hover/focus
  rendering differences. Historical data and reports were byte-checked unchanged.
- The web image built successfully, and a network-disabled, self-removing helper
  verified the static assets without starting nginx. Compose's builder handoff
  stalled/failed locally; the equivalent direct Desktop build succeeded:

  ```powershell
  docker --context=desktop-linux buildx build --builder desktop-linux --pull=false --load -f apps/web/Dockerfile -t pharmacy-assistant-web:local .
  ```

  This uses the same Dockerfile, build context and image tag as Compose; it changes
  no saved Docker context or network settings. No application containers started.
- The user-run isolated stack passed all nine checks, including explicit setup,
  frontend restore/reset/selection, service outages, cooldown propagation and
  persistence across database/whole-stack replacement. Its temporary resources
  were removed; no containers remained running at handoff. Hosted inference and
  changes to the application volume were both excluded.

Public status/source hashes: `cleanup-r3-baseline.json`; real-stack evidence:
`cleanup-r3-container.json`. Disposable logs, test
reports and screenshots are in ignored `artifacts/cleanup/r3/` and `artifacts/web/`.
No hosted inference or scraping was performed. R2's full backend and real-stack
evidence remains valid for its unchanged backend images; this checkpoint reruns
the checks affected by frontend relocation and the complete isolated stack.

From `apps/web/`:

```powershell
npm run build
npm run lint
npm test
```

From the repository root, after building the web image, the user explicitly runs
the isolated real-stack verification:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.compose_verify --run-isolated --frontend --output docs/validation/cleanup-r3-container.json
```

It uses a unique temporary stack, disables hosted inference, and removes its own
resources without modifying the application volume. Application startup remains
an explicit user action; existing Compose startup/phone commands are unchanged.

Stop for review before **R4: PostgreSQL-only runtime**. Legacy imports, tools,
Streamlit, file-mode selection and historical archives belong to later checkpoints.
