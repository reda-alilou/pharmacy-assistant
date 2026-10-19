# Improvement Step 5: quantity totals

## Follow-up correction after user validation

The user's three-turn browser run exposed a context-selection failure: the last
request correctly extracted `quantity: "deux boites"`, but its effective context
contained only the original `name: "abip"`, with no remembered presentation.
The UI had reached an earlier conversation branch rather than the resolved box-30
state. The screenshots alone did not identify why the separately cached token
lagged; the supplied JSON established that extraction and arithmetic were not the
cause of this failure.

New typed messages now derive their session token directly from the most recent
successful response in the visible conversation. They do not read the separate
cached token. Explicit restart still sends text without any previous token.
Provider-error retries preserve the exact original payload.

`tests/test_demo_conversation_chain.py` exercises the user's exact lowercase/
unaccented sequence through Streamlit and the FastAPI HTTP contract, with only
inference mocked. It deliberately sets the cache back to the initial ambiguous
reply before the third message. Both the normal path and a quota-error/retry path
must use the latest response token, retain record 9080 and return **744.00 MAD**.
This correction sends no live provider requests and starts no services. The
separate correction report is `reports/session_followup_fix.json`. All **185**
offline regression tests pass after this correction, including the new test with
normal and quota-retry subcases; see `reports/session_followup_fix_tests.log`.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_demo_conversation_chain.py -v
```

Reload the Streamlit page and start a new conversation after updating. The running
API does not need a code change for this correction. For a full restart, use the
startup command below yourself.

## Quantity calculation

Chat now calculates requested package totals locally from the selected catalogue
presentation and its recorded public price. The model still only extracts intent
and raw entity spans; it never supplies a price or performs the arithmetic.
No API/UI service was started or stopped. The catalogue, provider configuration,
prompt and local key were left unchanged.

## Implemented behavior

- Parse reviewed French, Arabic and Darija package quantities, including
  `deux boîtes`, `علبتين`, `جوج علب`, `jouj l3lab`, Arabic/Persian digits and mixed
  language phrases. Support digit counts from 1 to 1000; number-word coverage is
  deliberately limited to the reviewed dictionary in `pricing.py`.
- Keep purchase quantity separate from presentation size. A 30-tablet box without
  an explicit purchase quantity receives a unit price, never a total for 30 boxes.
- Treat generic boxes/packages as complete selected catalogue presentations. For
  example, two packages of AIRCORT mean two of the recorded `FLACON DE 200 DOSES`
  presentations, not two doses. The full presentation label stays visible.
- Accept specific flacon/tube counts only if the stored retail presentation itself
  starts with that singular container. Never divide a multipack into loose units.
- Ask for a clear package count for tablet/dose/volume quantities, bare numbers,
  fractions, ranges, nonpositive counts, counts above 1000 or unsupported wording.
  These return `needs_clarification`; a clear typed follow-up can replace the quantity.
- Wait for medication/presentation confirmation before publishing a line total.
  Buttons calculate the total after selection without another inference request.
- Preserve missing prices as unknown. Never replace missing data with zero.
  Source conflicts continue to use the retained AMMPS price with the conflict notice.
- Sum an order only when **every medication line** has an explicit valid quantity,
  confirmed presentation and known price. An incomplete order has no global total;
  known line totals remain labelled individually. Missing quantities never default to one.
- Show the unit price, counted presentations, multiplication and total in the answer,
  medication cards and expandable calculation JSON. Stock remains unknown.

Money arithmetic uses `Decimal(str(stored_price))`, rounded to cents with
`ROUND_HALF_UP`, then multiplied by the integer count. Unit-price display uses the
same rounding rule. Amounts in calculation JSON are exact two-decimal strings,
with currency `MAD`. These are calculations over stored prices, not live quotes,
discounts or an order placed with a pharmacy.

## API additions

Each medication now has `pricing`. An example after selecting ABIP box 30 and
requesting two complete packages is:

```json
{
  "status": "calculated",
  "requested_quantity": "deux boîtes",
  "presentation_count": 2,
  "unit_price_mad": "372.00",
  "total_price_mad": "744.00",
  "currency": "MAD",
  "basis": "per_catalogue_presentation",
  "clarification_reason": null
}
```

Other statuses are `not_requested`, `awaiting_medication`,
`needs_quantity_clarification` and `price_unavailable`. The response-level
`order_pricing` has status `not_requested`, `calculated` or `incomplete`; its
`total_price_mad` is null unless the whole order is calculable. Existing request
and continuation formats are unchanged. Client-supplied price fields are rejected.

## Measured offline results

The frozen development annotations and outcome criteria are unchanged.
Extraction is supplied by annotations for these checks; this is backend evidence,
not a Gemini accuracy score.

| Development check | Step 4 | Step 5 |
|---|---:|---:|
| Requested total cases correct | 0/7 | 7/7 |
| Complete contextual outcomes | 4/8 | 8/8 |
| Standalone outcomes | 28/32 | 31/32 |
| Overall complete outcomes | 32/40 | 39/40 |
| Standalone medication decisions | 21/21 | 21/21 |
| Contextual medication decisions | 8/8 | 8/8 |

The remaining case is `dev-ar-05`, a pharmacy-name matching failure with two failed
checks. It is outside this quantity step. Held-out data was validated for integrity
only, not executed or used for tuning. The examples remain synthetic and
assistant-reviewed without independent human/native-speaker review.

Evidence: [verified development report](../reports/development_backend_step5_verified.json),
[checkpoint](../reports/improvement_step5_quantity_totals.json).
The initial Step 5 report is an intermediate run. Previous checkpoint reports are
preserved rather than overwritten.

The new tests cover explicit package counts, ambiguity, missing data, exact cents,
container mismatches, changed stored prices, source conflicts, presentation choice,
quantity corrections, multilingual answers, API validation and real Streamlit
metrics/payloads with mocked inference. The live-check runner also has a budgeted
three-turn quantity scenario; its orchestration is tested offline.

The final full offline suite passed **184 tests**, including 16 new pricing tests.
An earlier run loaded an old module while the source was being edited and had one
import error; the final fresh-process run passed all tests in 74.277 seconds.
See `reports/step5_offline_tests_verified.log` and
`reports/step5_pricing_tests_final.log`.

## Live verification

The [three-turn live check](../reports/quantity_live_step5.json) passed using the
existing Gemini key and model. It asked the French ABIP price question, narrowed
to box 30 in Darija, then asked `Et pour deux boîtes ?`. The final response used
record 9080, retained its **372.00 MAD** unit price, counted two complete
presentations and returned **744.00 MAD**. Exactly **three provider attempts** were
reserved; no new key was needed. This is one live demonstration, not a full
multilingual extraction evaluation. Adapter latency includes local quota waiting.

## Commands and manual validation

Stop your own existing API/UI processes with Ctrl+C, then start the updated demo:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501>. Try:

1. `Quel est le prix de ABIP ?`
2. `Lboita dyal 30 3afak.` → recorded unit price **372 MAD**.
3. `Et pour deux boîtes ?` → **2 × 372 = 744 MAD**.
4. `Et pour trois boîtes ?` → **3 × 372 = 1116 MAD**.

Typed messages still use inference and respect the normal quota delay. Choice,
refinement and reference buttons require no extra inference. Arithmetic itself
uses no model tokens or additional API request.

Offline verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_pricing.py -v
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluation_dataset
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_baseline offline --output reports/development_backend_step5_recheck.json
```

Optional live recheck, capped at three provider attempts and sharing quota spacing:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_conversation_smoke --quantity-check --max-requests 3 --output reports/quantity_live_step5_recheck.json
```

Choose new report filenames on subsequent runs; existing evidence is protected
from overwrite. No new key is inherently required for these changes. Live checks
use the existing configured provider and must report any provider failure visibly.

Stop here for user validation. The outstanding pharmacy-matching case and wider
live extraction evaluation remain separate work.
