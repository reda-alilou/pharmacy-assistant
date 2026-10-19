# Step 1: medication foundation

This checkpoint implements catalogue lookup only. Multilingual interpretation,
chat, and the browser interface belong to later validated steps.

## Run

From the project directory in PowerShell, install dependencies if needed:

```powershell
uv sync --locked
```

Start the local API (no API account or key required):

```powershell
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000
```

Open [interactive API documentation](http://127.0.0.1:8000/docs).
The catalogue is validated, loaded, and indexed at startup. Restart the API after
rebuilding the data; requests do not reread the catalogue file.

## Validate this checkpoint

| Request | Expected result |
| --- | --- |
| `/health` | `status: ok`, 2,640 records, 1,082 distinct normalized brands, `catalog_scope: partial` |
| `/medications/search?query=AIRCORT` | Results from the enriched catalogue, absent from the original 240-record dataset |
| `/medications/search?query=ABIP&strength=15mg` | Two presentations: box of 20 at 268 MAD and box of 30 at 372 MAD |
| `/medications/search?query=ABIP&strength=15%20mg&presentation=20` | Only the box of 20, record ID `9079`, at 268 MAD |
| `/medications/search?query=ABIP&form=comprim%C3%A9` | Both tablet presentations; accents and case are ignored |
| `/medications/search?query=aripiprazole` | Search by active substance |
| `/medications/search?query=ABPI` | No selected medications; `status: suggestions`, with ABIP offered for review |
| `/medications/search?query=ABIP&strength=5mg` | No matches; a different strength is never substituted |
| `/medications/search?query=zzzz_unmatched` | `status: not_found`, explicitly limited to the partial catalogue |
| `/medications/search?query=%20%20` | HTTP 422, rather than HTTP 500 |
| `/medications/9079` | Full validated ABIP presentation, including enrichment and source links |
| `/medications/999999999` | HTTP 404 saying the record was not found in this partial catalogue |

`query` remains a medication-name/substance substring search. Pass strength,
form, and presentation separately; understanding a sentence such as "ABIP 15"
will be handled by the later interpretation layer. Strength matching ignores
case, spacing, and decimal-comma differences; it does not convert between units.

Spelling suggestions are returned only when the name/substance query has no
direct match. They honor supplied filters and contain a term, field, string
similarity score, and candidate record IDs. The score is not a clinical confidence
estimate. A known name with an unmatched strength does not trigger spelling
substitution. Multiple presentations remain separate even when their names and
strengths are identical.

## Public interfaces

- `GET /medications/search?query=...&strength=...&form=...&presentation=...`
  retains `query`, `result_count`, `medications`, and `catalog_scope`, and adds
  `status`, `message`, and `suggestions`.
- `GET /medications/{record_id}` returns one full medication presentation.
- `GET /health` reports catalogue readiness and counts.
- Shared Pydantic catalogue/search/health models are in
  `src/pharmacy_assistant/models.py`. Search text is trimmed, nonblank, and at most
  200 characters. Invalid query parameters return HTTP 422.
- Existing Python callers can continue using
  `search_medications(query)` and receive a list of dictionaries; optional
  keyword arguments add the three filters.

## Reproduce verification

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.quality_ammps
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pharmacy_assistant.search_medications "ABIP" --strength "15 mg" --presentation "20"
```

The quality command validates the enriched schema, IDs, required fields, finite
nonnegative prices, and AMMPS source URLs. It accepts both listing formats and
preserves their separate pagination. Its report is
`reports/ammps_quality.json` and is replaced atomically. Invalid data produces a
failed report and nonzero exit code; malformed JSON also fails the command.

Expected snapshot results: **2,640 records, 2,640 unique IDs, 132 detailed source
pages, zero validation errors**. Public, hospital, and PFHT prices are each
unknown for 312 records. Unknown prices remain `null`. The report separately
counts missing RCP/NAF references and text labels that are not document URLs.

The automated checks use the real catalogue and exercise the API's ASGI routing,
request validation, and response serialization. They also cover invalid startup
data, source provenance, misspellings, filter boundaries, and repeated requests
without additional catalogue reads. Tests use Python's standard `unittest`
runner; no hosted inference or additional test dependency is needed.

Catalogue prices and commercialization statuses are recorded reference data.
They do not establish current pharmacy stock or complete national coverage.

## Validation gate

Stop after Step 1. Begin the hosted-model integration only after the user
validates this checkpoint and explicitly requests Step 2.
