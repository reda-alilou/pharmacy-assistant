# Checkpoint 5 — React patient chat

Status: **implemented, verified and reviewed by the user on laptop and phone**.
Checkpoint 4 was reviewed: the user started all four healthy services, confirmed
the placeholder in the browser, and authorized continuation. Checkpoint 6 has
not started. Streamlit and its launcher remain available until final validation
in checkpoint 6.

## Agreed experience

The new `frontend/` implements D005–D006 and D008–D015: French chat with medication
and pharmacy cards in the conversation, a calm off-white/teal healthcare style,
responsive layout, and keyboard support. There are no gradients or decorative
card side strips. Example questions populate the composer without sending.
Historical choices are disabled; current choices use core-issued continuation
tokens and require no new inference.

Medication cards distinguish recorded prices, missing prices, commercialization
and unknown stock. Explicit package quantities, line totals and complete order
totals come from core. Pharmacy cards show available contact information and
the partial Rabat coverage; they do not claim verified hours, duty or stock.
Source links, collection dates and recorded conflicts remain available without
showing raw interpretation JSON or provider diagnostics. Existing multilingual
answers and factual backend behavior are preserved.

## Implementation

| Area | Responsibility |
| --- | --- |
| `frontend/src/App.tsx` | Chat, composer, error/recovery actions and reset dialog |
| `frontend/src/components/results.tsx` | Grounded medication/pharmacy cards, offered choices and sources |
| `frontend/src/lib/conversation.ts` | Temporary session, canonical transcript restoration and request recovery |
| `frontend/src/api/` | Generated request types, response validation and same-origin API client |
| `frontend/src/components/ui/` | Project-owned shadcn/ui controls using Radix primitives |
| `frontend/tests/` | Mocked browser scenarios and opt-in real deployment scenario |

The browser keeps only the active token/expiry in sessionStorage, plus a separate
cooldown deadline. It stores no transcript or permanent history. A refresh reads
the server transcript without inference or expiry extension. Local expiry and
server rejection clear the expired view. New conversation confirms the action
and invalidates server state before clearing the interface. Unavailable storage
is explained; the current tab still works in memory.

Sending is guarded while busy. Each explicit action gets a fresh request ID;
there is no automatic POST replay. On connection loss the client performs one
read-only reconciliation to recover a completed response. A still-pending request
requires manual verification before another send. Failed questions remain visible
and can be edited or explicitly retried, respecting cooldowns. A question which
never reached core is retained only in memory, not across refresh.

The checked-in OpenAPI schema is exported without loading runtime settings or
starting services. `openapi-typescript` generates request types; Zod validates
patient-facing responses and strips unused metadata. Source links accept HTTP(S)
URLs only. React renders text as text; upstream error messages are replaced with
known French messages. Credentials remain server-side.

## Build and operation

`deploy/Dockerfile.web` builds from the frozen npm lock with Node 22.23.2, then
copies static output into the existing Nginx image. There is no additional runtime
container. Hashed assets have immutable caching; HTML uses `no-store`. Existing
API forwarding, cooldown headers, timeouts and Docker DNS recovery are retained.
The Docker context excludes dependencies, browser fixtures, tests and credentials.

The web image has been rebuilt. The user controls application startup:

```powershell
docker compose --env-file .runtime/compose.env -f deploy/compose.yaml up -d --wait
```

Open <http://127.0.0.1:8080>. For a later source change, run the same Compose
command with `build web` first. Existing data uses the same persistent volume;
do not re-import or reset it. Stop with `down` without `--volumes` when finished.
See [frontend development instructions](../frontend/README.md) and the
[checkpoint 4 setup guide](architecture-checkpoint-4.md) for fresh setup/debugging.

## Verification

- Production TypeScript/Vite build passes. Lint has no errors; the two warnings
  concern shadcn's exported component variants and development hot refresh.
- Twenty Playwright scenarios pass, covering chat, selections, server totals,
  refresh, expiry, reset, failed/pending/lost responses, cooldowns, duplicate-send
  prevention, refinements/reference choices, safe rendering and responsive layout.
  Axe reports zero violations for the tested empty/chat/reset views. This is
  automated coverage, not a claim of complete accessibility conformance.
- Browser fixtures are generated from the real local catalogue/conversation
  engine with mocked extraction. The missing-price fixture uses an actual record
  with no recorded price. No hosted model requests or scraping were performed.
- The web image builds successfully from its lockfile. Python lock verification
  and source/wheel package builds pass offline.
- Python regressions: 270 passed, with ten opt-in host PostgreSQL tests skipped
  because host database access was not enabled. Both new contract/fixture checks
  then passed separately: 272 passing checks across the two runs. Real PostgreSQL
  behavior was also verified in the isolated container stack.
- The user-run real Compose verification passed all nine checks, including the
  new browser scenario. Temporary resources were removed, no hosted inference
  was performed, and the application volume was untouched.

The explicit command below reruns the eight checkpoint 4 integration checks and
adds a browser check against real web/core/PostgreSQL services. It restores a
synthetically seeded conversation, verifies a quota rejection, chooses an offered
presentation without inference, refreshes and resets. The language service has no
internet egress. It uses a separate generated project/volume and removes only its
own resources; the application volume is untouched.

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.compose_verify --run-isolated --frontend
```

After the user confirmed the frontend works, phone testing added an optional
`deploy/compose.phone.yaml` overlay. It binds only web to an explicitly supplied
Wi-Fi address; the default remains localhost. Request IDs now use cryptographic
`getRandomValues` so typed questions and selections also work over HTTP LAN
origins without `randomUUID`. A browser regression covers that unavailable API;
the web image was rebuilt. No application service or firewall setting was changed
by the agent. See [the phone instructions](../frontend/README.md#test-on-a-phone-over-wi-fi).
The user then confirmed access works and the interface is clean on both devices.

Evidence: `reports/architecture_checkpoint5_browser_tests.json`,
`reports/architecture_checkpoint5_browser_final.log`,
`reports/architecture_checkpoint5_web_build_verified.log` and
`reports/checkpoint5-*.png`. Python evidence is in
`reports/architecture_checkpoint5_python_verified.log` and
`reports/architecture_checkpoint5_contract_tests.log`. Real integration passed in
`reports/architecture_checkpoint5_container_validation.json` and
`reports/checkpoint5-real-compose.png`. Intermediate diagnostic logs are retained
separately from final passing evidence. The final status is recorded in
`reports/architecture_checkpoint5_status.json`.

## Review boundary

The user completed frontend review. Await authorization for checkpoint 6. Its final representative demo checks,
Streamlit retirement and final setup consolidation remain outstanding. No
provider, model, prompt, catalogue, pharmacy data or historical evaluation result
was changed. No final architecture decision was added or revised in this checkpoint.
