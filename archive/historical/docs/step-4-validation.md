# Step 4: Streamlit browser demo

The user chose Streamlit for the first demo and deferred the React frontend.
Streamlit is a separate UI process that calls the existing FastAPI API over HTTP.
Medication matching, inference, templates and clarification validation stay in
the backend. The UI never calls Groq directly or substitutes saved responses.

## Start with one command

From the project root, after `uv sync` and the existing backend `.env` setup:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501>. The backend is <http://127.0.0.1:8000>, with its
interactive API documentation at `/docs`.

The launcher starts FastAPI if port 8000 is free, waits for its health check,
then starts Streamlit. It can reuse a compatible FastAPI instance already running
on that port. Ctrl+C stops only the child processes it started; a reused backend
is left running. An occupied UI port causes a visible startup error. To use other
ports, pass `--api-port 8001 --ui-port 8502`.

For separate terminals instead:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000

# Terminal 2, from the project root so .streamlit/config.toml is loaded
.\.venv\Scripts\python.exe -m streamlit run src/pharmacy_assistant/demo.py
```

The UI defaults to `http://127.0.0.1:8000`. For separate startup, optionally set
the process environment variable `PHARMACY_API_URL` to another API origin. This
setting contains no API key. Backend credentials remain in the backend `.env`.
The launcher sets the API origin from its `--api-port` option.

## What to validate

1. Use **Français**, **العربية**, **Darija**, and **Mixte** example buttons, or
   type a question. Each button sends a real request. Check the answer, price,
   interpretation JSON, and source URLs/collection dates.
2. Choose **Choix ABIP**. Select the box of 30. Confirm 372 MAD and the source
   details stating that no new model call was made for selection. The box of 20
   retains its distinct recorded price of 268 MAD.
3. Request `Donne-moi le téléphone de la Pharmacie Ibn Nafis à Rabat.` Check the
   source-provided phone/address and the expandable directory details.
4. Ask for an unknown medication or a medication with an unknown price. Unknown
   facts must stay unknown. Ask for duty/hours: no verified opening/duty claim.
5. Expand **Extraction JSON** and **Sources et détails**. Merely rerendering the
   page or expanding details must not send another `/chat` request.
6. If inference fails, the error stays in the conversation. **Réessayer** repeats
   the same request only on an explicit click. There is no UI automatic retry;
   the backend still has its existing one bounded retry. Rate-limit cooldowns
   are respected. Expired choices offer **Relancer la question initiale**, which
   starts fresh rather than replaying the expired continuation.

The loading indicator remains visible during requests. Arabic text uses explicit
text direction for replies and automatic direction for user text. Source/user
text is HTML-escaped before rendering. Secrets and raw provider error bodies
are not displayed.

## State and scope

Up to 20 turns are kept in the current Streamlit session. **Nouvelle conversation**
clears the displayed history. New text is interpreted independently; history is
for display and explicit presentation selections, not unrestricted conversational
memory. Only choices on the latest turn remain actionable. Backend continuations
still expire after 15 minutes, eviction or restart.

The interface displays recorded prices and commercialization information, with
unknown local stock. The Rabat directory remains partial; hours and dated duty
information remain unverified. The Qwen/Groq reliability limitations observed in
Step 3 remain relevant. Streamlit does not repair provider generation failures.

## Offline checks

The complete offline suite passed **76 tests** on 2026-10-18, including ten new
HTTP-client, Streamlit interaction and launcher checks. Streamlit 1.66.0 is locked
in `uv.lock`. The running UI's HTTP health endpoint returned 200.

All **five live AppTest flows passed**: French, Arabic, Darija, mixed language,
and ABIP presentation selection. The ABIP question initially returned
`provider_generation_failed`; the driver clicked the visible manual retry button
once, after which selection of the box of 30 succeeded at 372 MAD without a new
inference call. The failed attempt remains recorded. These results do not imply
that provider reliability has been resolved, and AppTest is not browser visual QA.

A fresh launcher check started both services on temporary ports 8001/8502, verified
HTTP 200 from each, and verified that both stopped on interrupt while the existing
8000/8501 services remained available. See
[live UI evidence](../reports/streamlit_live_smoke.json),
[launcher evidence](../reports/streamlit_launcher_smoke.json), and
[checkpoint summary](../reports/step4_validation.json).

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

UI tests use Streamlit AppTest with mocked HTTP-boundary results derived from the
real local catalogue and chat service. They check actual button/input events,
selection payloads, display reruns, manual retry, rate-limit cooldown, expired
choice recovery, escaping and conversation reset. These mocks are test-only;
the running UI contains no mock inference or replay mode.

Live provider verification through the same Streamlit widgets can be reproduced
separately, with FastAPI running and the local provider key configured:

```powershell
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.evaluate_demo_smoke
```

This drives the real French, Arabic, Darija, mixed-language and ABIP-selection
flows through Streamlit AppTest and the actual HTTP/provider path, with no mocked
inference. The test driver may explicitly click the visible retry button once
per case; all attempts are retained in `reports/streamlit_live_smoke.json`.

Actual browser visual QA could not run in this environment: computer-use reported
no connected browsers, and the Opera connector also reported no connection.
AppTest verifies widget events and rendered elements but does not verify browser
screenshots, responsive layout, or actual Arabic glyph layout. Those checks remain
part of the user's validation in the running app.

Stop after this checkpoint for user validation. The larger held-out evaluation
and presentation package belong to Step 5.
