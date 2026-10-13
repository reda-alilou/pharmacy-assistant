# Patient–Pharmacy Assistant

Multilingual patient–pharmacy assistant for Morocco, designed to understand requests written or spoken in **French, Arabic, Darija, and code-switching**, extract structured information from them, and answer using verified medication and pharmacy data.

Developed as part of **Challenge Camp Data Science – Challenge 1**.

## Team

- Reda ALILOU
- Abdessamad BOULKADI

---

## 1. Project Goal

The goal of the project is to build an end-to-end conversational assistant capable of handling common pharmacy-related requests such as:

- Medication price
- Medication information
- Commercialization status
- Medication availability requests
- Pharmacy search
- Pharmacy contact information
- Opening hours
- Pharmacies on duty
- Medication dosage and form identification
- Multilingual and code-mixed patient requests

Example user request:

> Wach kayn ABIP 15 mg w bch7al ?

The system should understand that the patient is asking about both availability and price, and should extract the relevant medication and dosage.

Example structured interpretation:

```json
{
  "intents": [
    "availability",
    "price"
  ],
  "entities": {
    "medication": "ABIP",
    "dosage": "15 mg"
  }
}
```

The language model is responsible for **understanding the request**.

Factual information such as prices, commercialization status, pharmacy information, or stock must come from verified data sources and not from the language model itself.

---

## 2. Main Design Principle

The central architectural principle of the project is:

> **The LLM understands the request, the backend executes the request, and the databases provide the facts.**

The LLM must not invent:

- Medication prices
- Medication commercialization statuses
- Pharmacy stock
- Pharmacy-duty information
- Pharmacy contact information

If reliable data is unavailable, the system should state that the information cannot be confirmed.

---

## 3. Target Architecture

The target application follows the following architecture:

```text
Patient
   |
   |---- Text
   |
   |---- Voice
           |
           v
     Speech-to-Text
           |
           v
+-------------------------+
| Multilingual LLM / NLU  |
| Arabic / Darija / French|
| Intent + Entities       |
+-------------------------+
           |
           v
     Structured JSON
           |
           v
+--------------------------+
| Validation & Resolution  |
| - JSON validation        |
| - medication matching    |
| - ambiguity detection    |
| - entity normalization   |
+--------------------------+
           |
           v
+-------------------+
| FastAPI Backend   |
+-------------------+
      |         |
      |         |
      v         v
 Medication   Pharmacy
 Service      Service
      |         |
      +----+----+
           |
           v
   Reference Databases
           |
           v
    Grounded Response
```

The application therefore separates:

1. **Language understanding**
2. **Validation**
3. **Business logic**
4. **Data retrieval**
5. **Response generation**

---

## 4. Conversation Processing Flow

A typical request should eventually follow this path:

```text
User request
    |
    v
Text or Voice
    |
    v
Speech-to-Text if necessary
    |
    v
LLM understanding
    |
    v
Intent + Entity extraction
    |
    v
Structured JSON
    |
    v
Schema validation
    |
    v
Medication / Pharmacy entity resolution
    |
    v
Backend service selection
    |
    v
Database query
    |
    v
Verified result
    |
    v
Natural-language response
```

For example:

```text
User:
"Bch7al ABIP 15 mg?"
```

The LLM should extract:

```json
{
  "intents": [
    "price"
  ],
  "entities": {
    "medication": "ABIP",
    "dosage": "15 mg"
  }
}
```

The backend then searches the medication database.

If several presentations correspond to `ABIP 15 mg`, the system should not arbitrarily choose one.

Instead, it should request clarification.

---

## 5. Data Architecture

The conversational system depends on a separate data engineering pipeline.

```text
Data Sources
     |
     v
Raw Collection
HTML / JSON
     |
     v
Parsing
     |
     v
Normalization
     |
     v
Quality Checks
     |
     v
Enrichment / Matching
     |
     v
Processed Dataset
     |
     v
Backend Services
```

The project keeps raw and processed data separate so that the transformation process remains reproducible.

---

## 6. Main Medication Data Source

The main medication source currently used is:

**AMMPS — Agence Marocaine du Médicament et des Produits de Santé**

AMMPS is used as the primary source for medication information.

The medication database includes information such as:

- Medication name
- Active substance
- Dosage
- Pharmaceutical form
- Presentation
- Commercialization status
- Public price
- Hospital price
- Therapeutic class
- Authorization status
- Additional pricing information

Additional external sources may later be investigated for enrichment when AMMPS does not provide certain information.

---

## 7. Medication Data Model

A medication is not represented only by its brand name.

Each **specific presentation** is stored as a separate record.

For example:

```text
ABIP 15 mg
```

can exist in several package presentations.

Two presentations may differ in:

- Package size
- Price
- Commercialization status
- Pricing information

Therefore, they must remain separate records.

### Example

A product such as:

```text
ABIP 15 mg — Box of 20
```

and:

```text
ABIP 15 mg — Box of 30
```

must not be merged into a single row.

---

## 8. Current Medication Fields

The processed medication dataset currently contains fields such as:

```text
source_record_id
brand_name
active_substance
epi
dosage
form
presentation
commercialization_status
ppv_price_mad
hospital_price_mad
source
source_page
source_url
```

The richer AMMPS source adds fields including:

```text
authorization_status
therapeutic_class
pp_gn_raw
pfht_price_mad
vat_raw
rcp_naf_reference
detailed_source_url
```

---

## 9. Work Completed So Far

### 9.1 Project Architecture

The overall architecture of the final application has been defined.

It includes:

- Text input
- Voice input
- Speech-to-Text
- Multilingual LLM
- Intent extraction
- Entity extraction
- Structured JSON
- Validation
- Entity resolution
- FastAPI backend
- Medication services
- Pharmacy services
- Reference databases
- Grounded responses

---

### 9.2 Initial AMMPS Collector

A first AMMPS collection pipeline was implemented using:

- Python
- `requests`
- BeautifulSoup
- HTML caching
- JSON output

This collector was used to validate the complete data pipeline.

The initial collection contained:

```text
20 pages
240 medication presentations
```

---

### 9.3 Detailed AMMPS Collector

A richer AMMPS medication listing was then identified.

A second collector was implemented for this source.

The detailed collector supports:

- Page-by-page collection
- HTML caching
- JSON caching
- Duplicate-ID checks
- Request error handling
- Resuming interrupted collection
- Reusing already downloaded pages

At the current repository snapshot:

```text
Detailed pages collected: 132
Detailed records processed: 2,640
```

---

## 10. Parsing

Two main parsers have been implemented:

```text
parse_ammps.py
parse_ammps_detailed.py
```

### Basic parser

The initial parser extracts fields from the first AMMPS medication listing.

### Detailed parser

The detailed parser extracts data from:

- The medication table
- The corresponding medication detail modal

It also performs consistency checks between information displayed in different parts of the AMMPS page.

---

## 11. Data Cleaning and Normalization

The processing pipeline normalizes text and pricing information.

It handles:

- Extra whitespace
- Inconsistent price formatting
- Missing price markers
- French decimal notation
- AMMPS-specific number formatting

Examples of supported prices:

```text
268 DH
10,70 DH
10.411.00 DH
```

These can be converted into normalized numeric values.

Missing-value formats such as:

```text
SANSPPV
SANS PPV
SANSPH
SANSPFHT
SANS PH
SANS PFHT
```

are converted to null values instead of being interpreted as valid prices.

---

## 12. Dataset Enrichment

The initial medication dataset and the detailed AMMPS dataset can be merged.

The enrichment process uses the AMMPS medication record identifier.

Before merging, overlapping fields are compared to detect possible inconsistencies.

The most recent enrichment produced:

```text
Original records: 240
Detailed records processed: 2,640
New records: 2,400
Final unique records: 2,640
```

The current enriched dataset is located at:

```text
data/processed/ammps_medications_enriched.jsonl
```

---

## 13. Data Quality

A data-quality validation pipeline has also been implemented.

The initial validated dataset produced:

```text
Records: 240
Unique IDs: 240
Errors: 0
Quality check: PASS
```

The quality checks include:

- Record counts
- Duplicate IDs
- Invalid page data
- Missing prices
- Commercialization-status distribution
- Structural consistency
- Cross-source consistency

Quality reports are stored in:

```text
reports/
```

Current report:

```text
reports/ammps_quality.json
```

---

## 14. Medication Search

A local medication search module has been implemented.

It supports searching by:

- Brand name
- Active substance

Example:

```powershell
uv run python -m pharmacy_assistant.search_medications "ABIP"
```

The search engine preserves multiple medication presentations.

For example, if several `ABIP 15 mg` products exist, all matching presentations can be returned instead of collapsing them into one result.

---

## 15. FastAPI Backend

A first backend service has been implemented using **FastAPI**.

The API can be started with:

```powershell
uv run uvicorn pharmacy_assistant.api:app --reload
```

Current implemented endpoint:

```http
GET /medications/search
```

Example request:

```text
http://127.0.0.1:8000/medications/search?query=ABIP
```

The endpoint returns structured JSON containing matching medication presentations.

This validates the current pipeline:

```text
Processed Dataset
        |
        v
Medication Search
        |
        v
FastAPI
        |
        v
JSON Response
```

---

## 16. Current Project Structure

```text
pharmacy-assistant/
|
|-- data/
|   |
|   |-- raw/
|   |   |
|   |   |-- ammps/
|   |   |
|   |   `-- ammps_detailed/
|   |
|   `-- processed/
|       |
|       |-- ammps_medications.jsonl
|       |
|       `-- ammps_medications_enriched.jsonl
|
|-- reports/
|   |
|   `-- ammps_quality.json
|
|-- src/
|   |
|   `-- pharmacy_assistant/
|       |
|       |-- __init__.py
|       |-- ammps.py
|       |-- api.py
|       |-- build_ammps_dataset.py
|       |-- collect_ammps.py
|       |-- collect_ammps_detailed.py
|       |-- enrich_ammps.py
|       |-- parse_ammps.py
|       |-- parse_ammps_detailed.py
|       |-- process_ammps.py
|       |-- quality_ammps.py
|       `-- search_medications.py
|
|-- .gitignore
|-- .python-version
|-- pyproject.toml
|-- uv.lock
`-- README.md
```

---

## 17. Running the Project

The project uses `uv` for Python dependency and environment management.

### Install dependencies

```powershell
uv sync
```

### Search for a medication

```powershell
uv run python -m pharmacy_assistant.search_medications "ABIP"
```

### Start the API

```powershell
uv run uvicorn pharmacy_assistant.api:app --reload
```

The API can then be accessed locally through:

```text
http://127.0.0.1:8000
```

FastAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

## 18. Work Still To Be Done

The current repository represents the first functional foundation of the system.

Several important components are still under development.

---

## 18.1 Complete the AMMPS Medication Collection

The complete AMMPS detailed medication listing contains approximately:

```text
9,908 medication presentations
```

The current project snapshot contains:

```text
2,640 detailed medication presentations
```

The remaining pages still need to be collected.

The detailed collector supports resuming collection.

Example:

```powershell
uv run python -m pharmacy_assistant.collect_ammps_detailed --start <next_page> --end 496
```

After completing the collection, the enriched dataset must be rebuilt:

```powershell
uv run python -m pharmacy_assistant.enrich_ammps
```

A new full quality-validation pass must then be performed.

---

## 18.2 Build the Pharmacy Dataset

A reference dataset for Moroccan pharmacies still needs to be prepared.

Expected fields include:

```text
pharmacy_id
name
city
address
phone
latitude
longitude
opening_information
source
```

The pharmacy dataset should support requests such as:

```text
"Fin kayna pharmacie qriba lia?"
```

or:

```text
"Donne-moi une pharmacie à Rabat."
```

---

## 18.3 Pharmacy-Duty Data

Pharmacy-duty information must be treated separately from the static pharmacy directory.

Possible fields include:

```text
pharmacy_id
date
start_time
end_time
city
duty_type
source
```

The system must only return duty information if a reliable source is available.

---

## 18.4 Real Stock Availability

The project must distinguish between:

```text
Commercialisé
```

and:

```text
Available in a specific pharmacy right now
```

These are not equivalent.

A medication being commercially available in Morocco does not prove that a specific pharmacy currently has it in stock.

Therefore, real-time stock must remain:

```text
unknown
```

unless a reliable pharmacy-specific source is available.

---

## 18.5 Build the Multilingual NLP Dataset

A dataset of realistic patient requests must be created.

The dataset should contain examples in:

- French
- Arabic
- Moroccan Darija
- French/Darija code-switching
- Arabic/French code-switching

Each example should contain annotations such as:

```text
text
language_style
intent
entities
```

Possible intents include:

```text
price
availability
medication_information
medication_request
pharmacy_search
pharmacy_contact
opening_hours
pharmacy_on_duty
```

Possible entities include:

```text
medication
dosage
quantity
form
date
time
city
pharmacy
symptom
```

---

## 18.6 Integrate the LLM

The final system will use an LLM as the main natural-language understanding component.

The LLM will transform an unstructured patient request into a controlled structured representation.

Example:

```json
{
  "intents": [
    "price",
    "availability"
  ],
  "entities": {
    "medication": "ABIP",
    "dosage": "15 mg"
  }
}
```

The LLM output must follow a strict schema.

It must then pass through validation before the backend uses it.

---

## 18.7 JSON Validation

The structured LLM output must be checked before execution.

Validation should verify:

- Valid JSON
- Allowed intent names
- Allowed entity fields
- Correct data types
- Missing required information
- Invalid dosage formats
- Unsupported requests

Invalid LLM outputs should not directly reach backend services.

---

## 18.8 Medication Entity Resolution

The medication name extracted by the LLM must be matched against the real medication catalogue.

The entity-resolution layer should eventually handle:

- Exact names
- Case differences
- Accent differences
- Typographical errors
- Partial names
- Multiple dosages
- Multiple presentations
- Ambiguous products

Example:

```text
User:
"ABIP 15"
```

Possible matches may include multiple presentations.

The system should then request clarification instead of automatically selecting one.

---

## 18.9 Complete Backend Orchestration

The backend will become responsible for coordinating the complete application.

Planned API endpoints include:

```http
POST /chat

GET /medications/search

GET /medications/{id}

GET /pharmacies/search

GET /pharmacies/on-duty
```

The main route will eventually be:

```http
POST /chat
```

It will orchestrate:

```text
User Request
    |
    v
LLM
    |
    v
Validation
    |
    v
Entity Resolution
    |
    v
Service Selection
    |
    v
Database Query
    |
    v
Response Construction
```

---

## 18.10 Speech-to-Text

Voice input will eventually be supported.

The voice pipeline should be:

```text
Audio
  |
  v
Speech-to-Text
  |
  v
Transcribed text
  |
  v
Same LLM pipeline as normal text
```

Voice input should therefore reuse the same backend and NLU components.

---

## 18.11 User Interface

A simple conversational interface should eventually allow users to:

- Type requests
- Record voice requests
- Receive natural-language responses
- View medication information
- View pharmacy information
- Resolve ambiguities
- Continue a conversation

The frontend is not currently implemented.

---

## 19. Evaluation Strategy

The final project should not only function.

Its performance should also be measured.

---

## 19.1 NLP Evaluation

A manually reviewed test dataset should be created.

Metrics should include:

- Intent precision
- Intent recall
- Intent F1-score
- Entity precision
- Entity recall
- Entity F1-score
- JSON validity rate
- Medication-resolution accuracy

Results should also be analyzed by language:

```text
French
Arabic
Darija
Code-switching
```

This will help determine whether the system performs equally well across the supported language styles.

---

## 19.2 Data Quality Evaluation

The medication and pharmacy datasets should be evaluated for:

- Duplicate records
- Missing fields
- Invalid prices
- Invalid identifiers
- Conflicting source information
- Coverage
- Data freshness
- Parsing failures

---

## 19.3 End-to-End Evaluation

Realistic complete scenarios should test the entire architecture.

### Example 1 — Medication price

```text
User:
"Bch7al ABIP 15mg?"
```

Expected flow:

```text
User Request
    |
    v
LLM Extraction
    |
    v
Medication Resolution
    |
    v
Multiple Presentations Detected
    |
    v
Clarification
    |
    v
Database Lookup
    |
    v
Verified Price
    |
    v
Grounded Response
```

### Example 2 — Pharmacy search

```text
User:
"Fin kayna pharmacie f Agdal?"
```

Expected flow:

```text
Location extraction
    |
    v
Pharmacy search
    |
    v
Matching pharmacies
    |
    v
Structured result
```

### Example 3 — Pharmacy on duty

```text
User:
"Chkon pharmacie de garde lyoma f Rabat?"
```

Expected flow:

```text
Intent extraction
    |
    v
City extraction
    |
    v
Date resolution
    |
    v
Duty dataset query
    |
    v
Verified pharmacies
```

If reliable duty information is unavailable, the application should say that it cannot confirm it.

---

## 20. Safety and Reliability

Because the project operates in a healthcare-related context, the system should follow several safety principles.

### The assistant should not:

- Invent medication prices
- Invent pharmacy stock
- Invent pharmacy-duty information
- Pretend commercialization status means live stock
- Give unsupported medical diagnoses
- Give unsafe treatment recommendations
- Hide uncertainty

### The assistant should:

- Use structured reference data
- State when information is unavailable
- Cite or preserve data provenance when possible
- Ask for clarification when a medication is ambiguous
- Separate language understanding from factual retrieval

---

## 21. Definition of Done

The project will be considered complete when a user can successfully interact with the entire system from start to finish.

A complete final prototype should be able to:

- [ ] Accept text input in French
- [ ] Accept text input in Arabic
- [ ] Accept text input in Darija
- [ ] Accept code-switched requests
- [ ] Accept voice input
- [ ] Convert voice into text
- [ ] Detect one or more pharmacy-related intents
- [ ] Extract relevant entities
- [ ] Produce valid structured JSON
- [ ] Validate LLM output
- [ ] Match medication names against the real catalogue
- [ ] Handle multiple medication presentations
- [ ] Ask for clarification when necessary
- [ ] Retrieve verified medication prices
- [ ] Retrieve commercialization information
- [ ] Search pharmacies
- [ ] Retrieve pharmacy contact/location information
- [ ] Retrieve pharmacy-duty information when a reliable source exists
- [ ] Avoid fabricating unavailable stock information
- [ ] Return a clear natural-language response
- [ ] Expose the main system through an API
- [ ] Include automated or reproducible data-quality checks
- [ ] Include NLP evaluation results
- [ ] Include end-to-end test scenarios
- [ ] Demonstrate the complete application

The final goal is therefore not simply to create a chatbot.

The target is:

> **A multilingual conversational pharmacy assistant connected to structured Moroccan pharmaceutical data, capable of understanding patient requests, resolving them against real reference data, and returning traceable and grounded answers through an API.**

---

## 22. Current Status

### Completed

- [x] Project scope defined
- [x] Target architecture defined
- [x] Main AMMPS medication source identified
- [x] Basic AMMPS collector implemented
- [x] Detailed AMMPS collector implemented
- [x] Resumable page collection implemented
- [x] HTML caching implemented
- [x] JSON caching implemented
- [x] Basic AMMPS parser implemented
- [x] Detailed AMMPS parser implemented
- [x] Text normalization implemented
- [x] Price normalization implemented
- [x] Missing-price handling implemented
- [x] Dataset-building pipeline implemented
- [x] Dataset enrichment implemented
- [x] Duplicate-ID checks implemented
- [x] Data-quality checks implemented
- [x] Medication search implemented
- [x] FastAPI backend initialized
- [x] Medication search API implemented
- [x] 132 detailed AMMPS pages collected
- [x] 2,640 detailed medication presentations collected
- [x] 2,640 unique enriched medication records produced

### In Progress / Remaining

- [ ] Complete all AMMPS medication pages
- [ ] Reach approximately 9,908 medication presentations
- [ ] Rebuild the final enriched medication dataset
- [ ] Run full-dataset quality validation
- [ ] Build pharmacy dataset
- [ ] Build pharmacy-duty dataset
- [ ] Create multilingual NLP dataset
- [ ] Annotate intents and entities
- [ ] Integrate LLM
- [ ] Implement strict structured-output validation
- [ ] Implement medication entity resolution
- [ ] Implement ambiguity handling
- [ ] Complete backend orchestration
- [ ] Implement `/chat`
- [ ] Add Speech-to-Text
- [ ] Add user interface
- [ ] Build evaluation suite
- [ ] Test complete end-to-end scenarios
- [ ] Prepare final demonstration

---

## 23. Immediate Next Steps

The next development priorities are:

### 1. Complete AMMPS collection

Continue collecting the remaining detailed medication pages until the complete catalogue is available.

Target:

```text
~9,908 medication presentations
```

### 2. Rebuild and validate the complete dataset

After collection:

```powershell
uv run python -m pharmacy_assistant.enrich_ammps
```

Then run full quality validation.

### 3. Prepare pharmacy data

Build the pharmacy directory and investigate reliable sources for pharmacy-duty information.

### 4. Build the NLP dataset

Create realistic multilingual patient requests with annotated intents and entities.

### 5. Integrate an LLM

Use the LLM to convert natural-language requests into strict structured JSON.

### 6. Add validation and entity resolution

Connect extracted medication names to real medication records.

### 7. Build the `/chat` pipeline

Connect:

```text
User
  ->
LLM
  ->
Validation
  ->
Entity Resolution
  ->
Backend
  ->
Database
  ->
Response
```

### 8. Add voice and interface

Complete the final user-facing prototype.

---

## 24. Project Status Summary

The project is currently **in active development**.

The current repository already contains a functional technical foundation:

- Real AMMPS medication data
- Raw-data collection
- Structured parsing
- Data cleaning
- Data normalization
- Dataset enrichment
- Quality validation
- Medication search
- FastAPI backend
- A growing medication catalogue containing 2,640 detailed records

The next major phase consists of completing the medication dataset and building the conversational intelligence layer around the LLM, pharmacy data, entity resolution, and full backend orchestration.