# How our pharmacy assistant works

Architecture update: checkpoints 1–4 are implemented and reviewed. Checkpoint 5
adds a French React chat served by Nginx, with temporary transcript restoration
and inline result cards. Core and language are separate HTTP services using
service-owned PostgreSQL schemas. Read [the checkpoint 5 guide](docs/architecture-checkpoint-5.md)
and [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for current startup, storage,
ownership, and recovery behavior. The detailed conversation examples below remain
relevant; the Streamlit diagram and memory-only descriptions describe the earlier
demo, which remains available until checkpoint 6 review.

This explains the application implemented today, from startup to the answer you
see. It is written for understanding the project, rather than as an agent handoff.

## 1. What we have built

Our application helps someone express a pharmacy-related request in French,
Arabic, Darija or a mixture of languages. It identifies what they want, finds
matching information in our collected data, and displays an answer.

For example, it can understand a request for two boxes of a particular medication,
identify the correct box, retrieve its recorded price, and calculate the total.
It can also search the partial Rabat pharmacy directory for contact details.

There are three main parts:

| Part | Its job | Where it runs |
| --- | --- | --- |
| Streamlit interface | Shows the conversation, accepts input, displays answers and choices. | On your laptop; you access it through your browser. |
| FastAPI backend | Coordinates understanding, conversation context, searches, calculations and responses. | On your laptop, in a separate process. |
| Qwen through Groq | Reads the current message and extracts its language, intent and useful details. | On Groq's hosted infrastructure, accessed over the internet. |

Our medication and pharmacy data are already stored on your laptop. The backend
uses those local records during a conversation.

```text
YOU
 |
 | type a message
 v
STREAMLIT INTERFACE                 your laptop, port 8501
 |
 | sends a request
 v
FASTAPI BACKEND                     your laptop, port 8000
 |
 |---- asks GROQ / QWEN to interpret the message ---- internet
 |<--- receives an interpretation ------------------
 |
 |---- combines it with the conversation context
 |---- searches local medication / pharmacy records
 |---- calculates any requested totals
 |---- builds the answer using language templates
 |
 | returns the answer, results, choices and sources
 v
STREAMLIT -> YOUR BROWSER
```

## 2. What happens when you start it

The launcher is `run_demo.py`. When you run it, it:

1. Checks whether the chosen ports are available.
2. Starts FastAPI if an API is not already running on its port. If a compatible
   API is already there, it can reuse it.
3. Waits for the API's health endpoint to respond.
4. Starts Streamlit and tells it where to find the API.
5. Prints the local address you can open in your browser.

During FastAPI startup, the backend loads and validates the medication catalogue
and pharmacy directory. It builds lookup structures in memory so searches can
find records without reloading the files for every message.

It also reads the local configuration, creates the selected inference adapter,
and creates the object that manages conversations.

The configuration currently selects Groq and `qwen/qwen3.8-27b`. The Groq API key
stays in the server's local environment configuration. It is not sent to the
browser or included in answers.

The interface checks `/health` to show whether it can reach FastAPI. Therefore,
"API connectee" means the local backend is reachable. It does not prove that
Groq has available quota or that the next model request will succeed.

## 3. A message goes through the system

Consider a message asking for the price of two ABIP 15 mg boxes, each containing
30 tablets. This is how a successfully understood request is processed.

### A. The interface sends your message

You type in Streamlit, or press an example button. The interface sends an HTTP
request to the backend's `/chat` endpoint. HTTP is simply how these two running
programs communicate.

For a follow-up, it also sends the conversation token from the latest successful
reply. The token tells the backend which earlier context belongs to this message.

The interface itself does not call Groq, search the data, or calculate the price.
Those operations happen behind the API.

### B. The backend checks the request

FastAPI and Pydantic check the request's structure. Pydantic is the validation
library that checks whether incoming information has the expected fields and
types. Empty or invalid text and incompatible request modes are rejected.

Text is limited to 2,000 characters. The API also supports special requests for
clicking a presentation or selecting an offered clarification; these follow a
different path explained below.

### C. The backend asks Qwen what the message means

The inference adapter sends the current message and our extraction instructions
to Groq. Groq runs Qwen and returns the model's interpretation.
Here, "inference" means using an already-trained model to process a new input.

The model's job is to identify details such as:

| Detail | Meaning in this example |
| --- | --- |
| Intent | Asking about a price and/or requesting medication. |
| Medication | ABIP. |
| Strength | 15 mg. |
| Presentation | The box containing 30 tablets. |
| Requested quantity | Two complete boxes. |
| Language and reply language | The detected language and how the answer should be written. |

An **intent** is the action the person is asking for. An **entity** is a useful
piece of information in that request, such as a medication name or city.

The model receives the current message, not our entire local medication catalogue
or a copy of the full conversation. The backend handles conversation memory.

Qwen does not supply the medication's factual price. Its role here is language
understanding. A message normally requires one model call, with at most one
bounded retry for certain temporary failures.

### D. The backend validates the interpretation

The model returns structured information internally. Our backend checks it
against the expected schema and verifies that extracted names, quantities and
other non-empty entity values occur in the current message.

For example, an extracted medication name that was never mentioned is rejected
by the evidence check. Unknown information must remain unknown.

This does not guarantee perfect understanding: a model can extract a word that
really appears in the message but assign it the wrong meaning. Our tests and
local handling cover particular mistakes; the model can still make errors.

### E. The backend adds relevant conversation context

If this is a follow-up, the backend combines the current interpretation with
appropriate details from the previous successful interaction.

For example, "Et pour deux boites ?" does not contain a medication name. If the
conversation has one clearly established medication and presentation, the backend
can carry those details forward.

It keeps two separate views:

- **Current-message extraction:** what Qwen extracted from the message just sent.
- **Effective interpretation:** the information actually used after adding context
  and applying narrowly defined corrections.

This distinction lets us see whether a name came from your current words or from
the conversation. If several medications could be meant, the assistant asks which
one instead of selecting one silently.

### F. It finds the matching medication record

The medication resolver searches the loaded catalogue. It considers the name or
substance, then checks the stated strength, form and presentation.

These terms describe different things:

| Term | Example |
| --- | --- |
| Medication name | ABIP. |
| Strength | 15 mg. |
| Form | Film-coated tablet. |
| Presentation | A box containing 30 tablets. |
| Requested quantity | Two of those boxes. |

The catalogue stores distinct presentations separately. ABIP's 20-tablet box and
30-tablet box have different record IDs and recorded prices.

Reviewed Arabic spellings and other normalization rules can help match a name.
Possible spelling corrections are offered for confirmation. A wrong strength or
ambiguous presentation should produce a clarification rather than an automatic
substitution.

If a record is missing, the assistant reports that it was not found in the
available catalogue. That does not establish that the medication does not exist.

### G. It retrieves facts and calculates the total

Once the correct record is established, the backend reads its stored facts:
strength, form, presentation, recorded price, commercialization status and sources.

For ABIP's 30-tablet presentation, the stored public price is **372.00 MAD**.
For an explicit request for two complete boxes, local Python code calculates:

```text
2 x 372.00 MAD = 744.00 MAD
```

The calculation uses decimal arithmetic with money rounded to two decimal places.
The model does not perform this calculation for us.

The system does not assume that a missing quantity means one box, or divide a
box's price into guessed tablet prices. If the quantity or container is unclear,
it asks for clarification. If a price is missing, the price remains unknown.

For several medications, it calculates a grand total only when every line can
be calculated. It does not present an incomplete sum as the full order price.

### H. It builds an answer in the appropriate language

`answer_templates.py` contains reviewed wording for French, Arabic and Darija in
Latin or Arabic script. The backend selects the appropriate wording and inserts
the retrieved facts and calculated amounts.

There is no second model call to write the answer. This makes the response's
factual values traceable to our data and calculations. It also explains why some
answers have a consistent or repetitive sentence structure.

The backend attaches the relevant source links and available collection dates.
If secondary sources disagree with the reference record, the stored observations
and conflicts remain available rather than silently replacing the official value.

### I. The interface displays the response

FastAPI returns the answer together with medication cards, pharmacy results,
clarification choices, pricing information, sources and conversation tokens.

Streamlit displays the readable answer and available cards. The implemented UI
also has expandable extraction/context and source details, including technical
JSON. Arabic-script answers use right-to-left text direction.

Streamlit keeps the latest 20 conversation turns in its session state. The next
message uses the token from the latest successful backend response.

## 4. What happens when clarification is needed

Suppose you ask only:

> Quel est le prix de ABIP ?

There are at least two relevant stored presentations:

| Presentation | Recorded public price |
| --- | ---: |
| ABIP 15 mg, 20 tablets | 268.00 MAD |
| ABIP 15 mg, 30 tablets | 372.00 MAD |

The assistant needs to know which presentation you mean. It returns choices and
a continuation token. That token connects the displayed choices to the backend's
saved clarification state.

If you click the 30-tablet choice, the interface sends the selected record ID and
continuation token. The backend verifies that this record was actually offered
for that medication. It retrieves the record and produces the updated answer.

**Clicking an offered selection or refinement does not need another model call.**
A typed clarification is still a new natural-language message and normally does.

After selecting the 30-tablet box, a follow-up asking for two boxes can reuse that
confirmed presentation and calculate 744.00 MAD.

Conversation and clarification state are held in API memory. They expire after
15 minutes and can also be evicted if the state capacity is reached. Restarting
the API loses them. The visible conversation history in Streamlit and the context
remembered by FastAPI are separate pieces of state.

The "Nouvelle conversation" button clears the interface history and stops using
the previous conversation token. Old backend state expires normally; the button
does not delete the medication data or restart the API.

## 5. How pharmacy questions work

The model extracts the pharmacy-related intent and details such as the pharmacy
name, city or neighborhood. The backend then searches the local Rabat directory.

For example, it can look up a named Rabat pharmacy and return its recorded phone
number and address. Reviewed Arabic aliases help with some name variants.
If several pharmacies match the name, the answer asks for clarification.

When no city is supplied, the demo uses Rabat and discloses that default. An
explicit request for another city is outside the current coverage.

Results are ordered by name, with at most five displayed and the total match
count reported. Although stored records have coordinates, the application does
not currently rank pharmacies by distance from you.

A question about opening hours or duty can be understood without the factual
answer being available. The response makes that limitation explicit. Undated map
markers are not treated as verified duty schedules.

## 6. Where the data come from

Collection and preparation happened before normal conversations. During a chat,
the application does not visit each website or scrape a new price.

| Source or file | Role in the current application |
| --- | --- |
| AMMPS | Reference medication listing. The active catalogue contains 9,936 distinct presentations. |
| Medicament.ma | 1,008 collected secondary observations. |
| Saydalia medication data | 5,299 collected secondary observations. |
| Saydalia pharmacy data | The active partial Rabat directory contains 327 pharmacies. |

The medication catalogue is
`data/processed/ammps_medications_enriched.jsonl`. Each line is one stored record.
The pharmacy directory is `data/processed/pharmacies_rabat.jsonl`.

**2,700 medication presentations have matched secondary-source observations.**
Secondary counts overlap with the official catalogue; they are not extra unique
medications to add to the 9,936 total.

The preparation code links secondary observations only when name, strength, form
and package match uniquely after normalization. It preserves source information
and disagreements. AMMPS reference prices and commercialization statuses are
retained rather than automatically replaced by another source.

There are **1,126 catalogue records without a public price**. Those gaps remain
visible in application behavior.

The raw HTML files you see in the editor are collection artifacts. Their roles are:

- `page_12.html`: the saved website page.
- `page_12.meta.json`: information about the HTTP retrieval, such as its source
  and collection metadata.
- `page_12.json`: the medication records parsed from that page.

The processed enriched catalogue is what normal medication lookup loads. The raw
files are useful for checking sources and parsing, rather than being the live
conversation's search database. Several raw caches are local and excluded from Git.

## 7. What each important code file does

All files below are under `src/pharmacy_assistant/`.

| File | Plain-language responsibility |
| --- | --- |
| `run_demo.py` | Starts the local interface and API; manages the processes it starts. |
| `demo.py` | Builds the Streamlit screens and conversation display. |
| `demo_client.py` | Sends interface requests to FastAPI and translates errors for display. |
| `api.py` | Defines the API endpoints and loads application components at startup. |
| `config.py` | Reads configuration and keeps credentials out of public responses. |
| `inference.py` | Selects the configured model-provider adapter. |
| `nlu.py` | Sends extraction requests to Groq/Qwen and validates the returned interpretation. |
| `nlu_models.py`, `chat_models.py`, `models.py` | Define the expected shapes of interpretations, chat messages, records and results. |
| `chat.py` | Coordinates the whole request and holds conversation/clarification state. |
| `conversation.py` | Determines which previous details can be carried into a follow-up. |
| `catalog.py` | Loads and indexes medication records and supports direct search. |
| `resolution.py`, `medication_normalization.py` | Resolve a medication mention, compare its details and build clarification options. |
| `pharmacy_directory.py`, `pharmacy_normalization.py` | Search the Rabat directory and handle reviewed name/neighborhood variants. |
| `pricing.py` | Interprets package quantities and calculates line/order totals. |
| `answer_templates.py` | Builds the final wording from retrieved results. |
| `quota.py` | Tracks local request reservations, provider cooldowns and evaluation budgets. |

These backend modules are Python code inside the same running FastAPI process.
They are not separate running medication, pharmacy or language servers.

## 8. What is remembered and where

| Information | Current storage |
| --- | --- |
| Collected medication/pharmacy records | Local processed files; loaded into backend memory at startup. |
| Visible conversation history | Streamlit session memory. |
| Follow-up context and offered choices | FastAPI process memory, with expiration and capacity limits. |
| Model request counters and cooldowns | Local SQLite file: `.runtime/inference_quota.sqlite3`. |
| Test/evaluation outputs | Files under `reports/`. |
| API key | Local server configuration, normally `.env`; excluded from Git. |

The SQLite file tracks quota bookkeeping; it is not where medications or
conversations are stored. Evaluation reports are evidence of previous tests;
the application does not use them as prewritten answers.

## 9. What happens when something fails

If the model times out, returns invalid extraction, rejects authentication or
hits a provider limit, the API returns a structured error and the interface
displays an explanation. It does not invent a medication answer or silently
switch to a different provider.

The local quota tracker respects provider cooldowns and prevents repeated early
requests. It does not grant more allowance or guarantee Groq availability.

If the model cannot be used, new natural-language questions cannot complete the
understanding stage. Local medication search endpoints and suitable already-issued
selection actions do not themselves require a model request.

If clarification state has expired or the API restarted, the interface cannot
resume that old choice. The user must start again with a complete question.

The distinction between three commonly confused facts is essential:

| Fact | What the application actually knows |
| --- | --- |
| Recorded public price | The value stored from the collected source, if available. |
| Commercialization status | The status recorded in the catalogue. |
| Stock in a particular pharmacy | Unknown. A catalogue entry or commercialization status does not establish stock. |

## 10. How we checked that it works

The project has an offline automated suite using mocked inference, so those tests
do not spend model quota. The last verified run passed **236 tests**, including a
clean export of the tracked files without `.env` or ignored collection caches.

Separate live evaluations check the actual model:

- The original frozen 40-scenario evaluation passed **34/40 backend scenarios**.
  Intent F1 was 92.86% and entity-slot F1 was 95.91% on that earlier version.
- After specific corrections, a targeted set of **14 scenarios passed 14/14**.
  It covers six known failures and eight fresh variations; it is not proof of
  perfect performance on arbitrary questions.

The offline tests check our code's behavior. The live evaluations check how actual
model outputs work with that code. Both matter because an accurate interpretation
can still be mishandled by the backend, and a correct backend cannot reliably
recover every incorrect interpretation.
