# Step 3: grounded conversation API

This step connects hosted interpretation to local retrieval and reviewed response
templates. The browser interface belongs to Step 4; use Swagger or PowerShell
to validate this checkpoint. No additional scraping or paid service is needed.

## Run

From the project root, with the existing local `.env` configured:

```powershell
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/docs> and expand `POST /chat`, then **Try it out**.
The API key stays on the server. Existing `/interpret`, search, lookup and health
routes remain available. Restart the server after changing code or data.

```json
{"text":"Wach kayn AIRCORT w bch7al?"}
```

The response contains `interpretation`, per-mention `medications`, optional
`pharmacy` results, `answer`, and `sources` with retrieval dates and record IDs.
`inference` records the provider model, attempts, latency and token usage.
`inference_performed` distinguishes new model calls from presentation selections.
Recorded commercialization status never establishes local pharmacy stock.

## Presentation selection

```powershell
$chatResult = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType application/json -Body '{"text":"Quel est le prix de ABIP ?"}'
$chatResult.medications[0].candidates | Select-Object source_record_id, brand_name, dosage, presentation, ppv_price_mad

$selectionBody = @{
    continuation_id = $chatResult.continuation_id
    selections = @(@{mention_index = 0; record_id = '9080'})
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType application/json -Body $selectionBody
```

ABIP offers exactly ID `9079` (box of 20, 268 MAD) and ID `9080` (box of 30,
372 MAD). RABIPUR is excluded by exact-brand priority. The selection returns the
recorded price without another inference request. Each selection is checked against
the candidates returned for that exact medication mention. An unrelated ID gets
HTTP 422. Multiple mentions can be selected together or separately.

Continuations use opaque random IDs held only in server memory, for 15 minutes,
with a maximum of 128 pending entries. Oldest entries are evicted when full.
Expiry, eviction, or a restart returns HTTP 410; resend the original message.
The stored state contains the extracted interpretation and choices, not the full
original text. A continuation ID gives access to its own choices; treat it as
private. This mechanism is intended for the single-process local demo. Multiple
workers would need shared state. New text starts a new request; this is a
selection flow, not unrestricted conversational memory.

## Resolution rules

1. Exact brand first, then exact active substance.
2. Apply separate strength, form and presentation filters. Quantity requested is
   preserved separately and never interpreted as a package size.
3. Resolve automatically only when an exact identity and supplied filters leave
   one presentation. An unrecognized or conflicting filter remains unresolved.
4. Partial names and spelling suggestions always require confirmation, even if
   only one candidate remains. No approximate match is silently selected.
5. Offer at most 20 candidates per mention; `candidate_count` retains the full
   count and `candidates_truncated` asks the user to refine the query.

Strength normalization covers spacing, decimal commas, Arabic digits, common
Arabic units, microgram spellings, and equivalent simple mass units (1 g =
1000 mg). It does not infer an unstated unit. Form/package normalization covers
common French and Arabic labels; unsupported wording can require a clearer query.
A small reviewed Arabic alias table supports ABIP, AIRCORT, DOLIPRANE and
PARACETAMOL. This is not general medication transliteration. Names written in
other unrecognized scripts may remain unresolved. Raw extracted spans remain
unchanged and visible.

## Factual answers and limits

Replies use French, Arabic, or Darija templates in Arabic/Latin script, chosen
from the validated interpretation. Product labels from sources remain verbatim.
Public price is for one recorded presentation; no requested-quantity total is
calculated. Unknown prices remain null and are described as unrecorded.
AMMPS prices and commercialization status are retained when secondary sources
disagree; conflicts and their provenance remain visible in the response.
Non-clinical information can include the stored active substance. Unsupported
clinical requests receive a boundary message without treatment recommendations.

The optional pharmacy service searches the 115-record Rabat sample by city,
pharmacy name, and address/name text for an area. Common Rabat/Agdal/Hassan/Hay
Riad Arabic spellings have reviewed aliases; arbitrary address translation is
not implemented. With no city, the response explicitly defaults to Rabat. Other
cities return outside coverage; an unmatched name/area never falls back silently
to unrelated entries. Up to five matches are ordered by name, without distance
ranking. Missing addresses/phones remain unknown. An absent directory file leaves
medication service available; malformed directory records fail startup.

Requests for hours or duty keep their extracted location/date/time details, but
the response states that hours are unknown and duty is unverified. Directory
matches are never presented as currently open or on duty. No local stock data is
available. None of this step queries a live stock, opening, or duty service.

Groq/provider failures remain visible HTTP errors. There is one bounded retry
inside interpretation, with no second retry layer in chat and no saved-answer
substitution. The Qwen provider can occasionally fail strict-schema generation;
this surfaces as `provider_generation_failed` after the bounded retry.

## Verification commands

Recorded on 2026-10-18:

- **66/66 offline tests passed** against the published medication and Rabat data.
- The first complete live run passed **7/11** cases. Three cases returned
  `provider_generation_failed`; one returned `provider_timeout`, after the
  application's single bounded retry.
- A separate recheck passed **3/4** affected cases. The Arabic duty request still
  returned `provider_generation_failed`. Across both runs, **10 distinct flows**,
  including all five core user acceptance flows below, have passed. These are
  observed successes across runs, not a 100% live reliability result.
- A separate complete-JSON prompt experiment passed 3/4 probes, so it was not
  adopted. The deployed interpreter retains the previously validated `step2-v1`
  prompt. No model, key, or provider configuration was changed.

Evidence: [first live run](../reports/chat_smoke.json),
[targeted recheck](../reports/chat_smoke_recheck.json), and
[checkpoint summary](../reports/step3_validation.json). The initial timeout
preflight is preserved separately. Both live reports remain marked failed.
Provider reliability is unresolved and must be considered before relying on a
live presentation. All successful checked responses matched their stored facts.
Step 4 has not started; this checkpoint awaits user validation.

```powershell
# Offline regression, including mocked provider failures and real retrieval.
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Live acceptance: 11 real messages and the ABIP selection flow.
# Requires the running server, internet and the configured free Groq account.
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.evaluate_chat_smoke

# Run one live case separately without replacing the full report.
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.evaluate_chat_smoke --case darija-price-stock --output reports/chat_smoke_darija_recheck.json
```

The live checker spaces messages by 30 seconds, records every response/error,
checks required intents and resolution outcomes, and compares returned medication
records against the canonical lookup endpoint. It also checks ABIP's allowed
selection and rejection of an unrelated ID. Reports are development evidence,
not the held-out evaluation or a general accuracy guarantee.

## User acceptance

- Darija price/availability: `Wach kayn AIRCORT w bch7al?` → recorded 83 MAD;
  pharmacy stock unknown.
- Ambiguity: `Quel est le prix de ABIP ?` → both presentations; select ID 9080
  → recorded 372 MAD and `inference_performed: false`.
- Unknown product: `Quel est le prix du médicament XYZZZ999999 ?` → absent from
  this partial catalogue, without claiming nonexistence.
- Unknown price: `Quel est le prix de 18F PSMA RIM 250 MBQ / ML, BOITE D'UN FLACON MONODOSE DE 15 ML ?`
  → ID 9302, price null, no fabricated amount.
- Pharmacy: `Donne-moi le téléphone de la Pharmacie Ibn Nafis à Rabat.` → stored
  contact 0537720657 and source details. A duty request must state that verified
  dated duty data is unavailable.

Stop after this checkpoint for user validation. Step 4 adds the browser interface.
