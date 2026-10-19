# Secondary medication collection and Rabat pharmacy expansion

**Current decision: exhaustive collection stopped by user agreement.**
Saydalia finished all 442 medication pages (5,299 records), Medicament.ma was
stopped after 988 parsed details, and the Rabat sweep finished with 327 pharmacies.
All saved data is retained. Medicament.ma coverage remains partial; no collection
process should be restarted for the current demo checkpoint.

Offline preparation is documented in [the cutoff guide](demo-enrichment-cutoff.md).
This is a **collection/enrichment candidate checkpoint**, before publication.
The application continues to read `data/processed/`; these collectors write only
to `data/staging/`. No inference provider, API key, or demo server is needed.

## Optional future complete-collection runner (deferred)

```powershell
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.run_collection_expansion
```

The runner resumes the two medication collectors and Rabat grid, then performs
the offline audit after the downloads stop. An OS lock prevents duplicate runners.
Do not start individual collectors while this runner is active. The previous
background run was explicitly stopped; this command is only for a later decision
to resume exhaustive collection, not the current demo workflow.

Read `reports/collection_expansion_run.json` for status:

- `running`: at least one collector is still working; detailed counts live in
  its staging manifest and `reports/collection_<source>.log`.
- `auditing`: source collection stopped and offline checks are running.
- `ready_for_review`: all collectors finished successfully, cache/provenance
  checks and pharmacy retrieval checks passed, and active dataset hashes did not change.
- `needs_attention`, `runner_failed`, or `interrupted`: the step is incomplete;
  inspect the report/logs, resolve the problem, then resume the same command.
- `stopped_by_user_agreement`: an intentional cutoff; keep the collected data and
  continue offline preparation without resuming downloads.

Completion evidence is written to `reports/collection_expansion_checkpoint.json`.
The runner does not merge, publish, launch the demo, or invoke an inference model.
Its processes/logs continue independently of this chat. A later resume reuses the
verified cache. Medicament.ma has thousands of individual detail URLs, so a full
run takes hours at the source interval. Keep the machine awake for downloads to
continue; interrupted work can resume.

## Medication sources

`expand_medications` replaces the sample caps for this new collection. The old
`supplementary_sources` command remains a bounded sample collector for reproducing
the earlier checkpoint; it should not be used to publish this expansion.

- **Medicament.ma:** read the public medication sitemaps, then enumerate the
  current A–Z listings and all advertised pages. Fetch each unique current detail
  URL. The first sitemap contains obsolete URLs returning 404, so sitemap presence
  alone does not establish that a medication page is accessible.
- **Saydalia:** discover the last page from the public medication pagination and
  collect every listing page. Each card provides the structured source fields;
  repeated desktop/mobile attributes remain one observation per source ID.
- Raw HTML, requested URL, fetch time and SHA-256 are cached. Repeated pages,
  duplicate IDs, changing pagination totals, parser failures and HTTP errors are
  recorded or stop the run. Missing values stay unknown.
- Medicament.ma repeats two URLs across different E listing pages in the current
  snapshot. Unique URLs are visited once; this discrepancy remains in
  `listing_warnings` and prevents `advertised_counts_reconciled` from becoming true.
- `collection_complete` means every discovered collection unit was parsed; it does
  **not** assert a complete national catalogue, fresh market availability, or
  agreement with another source.

Run from the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.expand_medications --source medicament
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.expand_medications --source saydalia
```

These commands can take hours for thousands of detail pages. Each source client
uses a minimum two-second interval, sequential requests, and bounded retries.
Public-source HTTP 401/403/429 stops the run rather than bypassing restrictions.
Individual 404/410 detail pages remain explicit gaps. Three consecutive other
unit failures stop the run.

For a short invocation, add `--max-requests 100`; retry attempts count toward that
budget. An omitted budget runs until completion or a source error. Rerun the
same command to resume from verified cache. Use `--max-requests 0` for a cache-only
replay. An incomplete run exits with code 2 and preserves staged records.
Run only one collector per source/directory at a time.
Checkpoint replacement retries Windows sharing violations for a bounded period;
if the file remains locked, the previous checkpoint and downloaded cache survive.

Medication outputs:

```text
data/staging/secondary_expansion_v1/medicament/
data/staging/secondary_expansion_v1/saydalia/
  manifest.json       # progress, completion, errors and missing-field counts
  medications.jsonl   # source observations, not merged application records
  raw/                # HTML and provenance metadata
  parsed/             # parsed observations per page/detail
```

For a later fresh snapshot, pass `--directory data/staging/secondary_expansion_v2`
to both medication commands. Existing caches retain their original fetch dates;
rerunning a cached snapshot does not make it fresh.

## Rabat pharmacies and future cities

The collector reads `data/collection/cities.json`. Rabat is the first reviewed
configuration; another city requires its own source label, search bounds, spacing,
and validation. No changes to collector logic are needed to collect it. The
application directory currently remains explicitly scoped to Rabat.

The Rabat rectangle is a collection search area, **not an administrative boundary**.
Only records labelled Rabat by the source are retained. The base grid searches 143
distinct origins with a maximum 0.015-degree spacing and includes all four bounds.
Saydalia's browser client requests a limit of 35 but the API returned 40 records
per origin. Each response at or above the requested/observed threshold is flagged
as potentially truncated. No offset/pagination contract is exposed by that client.

If a capped response containing Rabat records has an outer result radius smaller
than its grid cell radius, the collector adds quarter-step origins inside that
cell, to a default maximum refinement depth of one. This is a sampling heuristic,
not a guarantee about the API's unseen results. The current run completed 149
distinct origins (143 base plus six refinements), retained 327 unique pharmacies,
and left zero dense cells requiring further refinement under that heuristic.
All 149 responses remain flagged as potentially capped, so city completeness is
still unknown. All 115 previous pharmacy IDs are retained; 212 IDs are additional.
All 327 phones have a recognized Moroccan format; 11 addresses are missing.

```powershell
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.expand_pharmacies --city rabat
```

The same cache, request-budget and `--directory` options apply. A completed grid
does not prove complete city coverage; `complete_city_directory` remains false.
The report lists origins, response counts, neighbouring-city exclusions, and
new IDs per origin. Repeat observations are deduplicated by source ID; conflicting
fields and possible duplicate identities under different IDs are retained for
review. Coordinates and source addresses are preserved. Phone formats are checked
without inventing or replacing source contact information.

Outputs are under `data/staging/pharmacy_expansion_v1/rabat/`:
`pharmacies.jsonl`, `duty_observations.jsonl`, `manifest.json`, and `raw/`.
There are no verified current duty intervals, opening hours, live stock, or
distance-based retrieval guarantees. Raw undated duty markers never establish
that a pharmacy is on duty today.

## Offline validation and review

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_collection_expansion.py -v
.\.venv\Scripts\python.exe -m pharmacy_assistant.review_collection_expansion
```

Run the standalone audit after the collectors finish. The checkpoint runner
already performs it automatically and records completion independently.

`reports/collection_expansion_checkpoint.json` contains source counts, cache hash
checks, missing fields, collection gaps, Rabat baseline-ID retention, and grounded
retrieval checks on the staged directory. These checks use structured input and
make **zero model requests**; they do not measure multilingual model accuracy.
The report also fingerprints the active application datasets.

Do not feed the staged files directly to `build_reference_data`: its current
inputs are the earlier processed samples. Publication, reconciliation of unmatched
records and conflicts, and application regression checks follow user validation
of this collection checkpoint.
