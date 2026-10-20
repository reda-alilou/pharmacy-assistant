# Demo data: accepted cutoff and validated enrichment candidate

**Update:** the user approved testing the new data and the candidate was activated.
Use the [browser test guide](test-expanded-demo.md) to restart and test it.
The counts and validation below describe the preserved candidate checkpoint.

The user agreed to stop the long medication download and use the saved data.
All collection processes were stopped. Further exhaustive scraping is deferred.
No inference API was called for this preparation or validation.

## Data retained

| Data | Retained scope |
| --- | --- |
| AMMPS | 9,936 official presentations; all existing official facts preserved |
| Saydalia medications | All 442 advertised listing pages, 5,299 records |
| Medicament.ma | 988 verified new detail records; collection intentionally partial |
| Earlier Medicament.ma records | 20 unrefreshed records retained, giving 1,008 selected observations |
| Rabat pharmacies | 327 unique source IDs, including all previous 115 |

The 988 Medicament.ma details include eight completed units beyond the last
980-record progress checkpoint. They were recovered by checking cached SHA-256
values, reparsing the raw pages, and comparing them with the saved parsed records.
The same full raw/parsed verification was performed for all 442 Saydalia pages.

An observation is selected as a whole by source ID and latest fetch time.
Unknown values in a new observation are not filled from an older snapshot.
Earlier IDs not refreshed by this cutoff remain available with their original
timestamps. Prior input snapshots and provenance are stored with the candidate.

Saydalia completion describes its advertised listing at collection time, not
complete national medication coverage or real pharmacy stock. Medicament.ma's
full A–Z discovery found 5,036 unique current detail URLs; the uncollected details
remain deferred. Rabat's map sweep is systematic but cannot prove city completeness.

## Reconciliation results

The candidate is in `data/staging/demo_enrichment_v1/`.

| Measure | Before | Candidate |
| --- | ---: | ---: |
| Official presentations | 9,936 | 9,936 |
| Presentations linked to secondary observations | 27 | 2,700 |
| Presentations with a sourced ATC value | 27 | 2,662 |
| Presentations with a sourced reimbursement status | 20 | 1,979 |
| Rabat pharmacies | 115 | 327 |

Of 6,307 selected secondary observations, 3,128 link to official presentations.
The remaining 3,179 stay separate because of non-medication product types,
missing information, or unmatched presentation signatures. No fuzzy merge is used;
zero ambiguous presentation signatures were automatically joined.

There are 1,258 flagged disagreements: 701 commercialization statuses, 540 public
prices, 15 hospital prices, and two ATC conflicts. Official facts and prices are
unchanged. Conflicting canonical ATC values remain unknown. Source observations,
URLs, fetch timestamps, unmatched entries and conflicts remain inspectable.

Example of newly enriched data: ACOL 1000 MG, box of 30, official price 18.30 MAD,
now has source-reported ATC/reimbursement observations. These observations are not
individual reimbursement eligibility decisions. ABIP still has distinct boxes
of 20 at 268 MAD and 30 at 372 MAD.

## Verification

- All **219 offline tests passed**: `reports/demo_enrichment_offline_tests.log`.
- All **40 development backend scenarios passed** against the candidate catalogue
  and 327-pharmacy directory: 32 standalone cases and eight conversation cases.
  Medication decisions passed 21/21 standalone and 8/8 conversational checks.
- All cached-response hash checks passed; the staged pharmacy directory passed
  eight French/Arabic name, neighbourhood, ambiguity and coverage checks.
- The full Pydantic/catalogue quality checks passed for all 9,936 presentations.
- All official catalogue facts remain identical, including unknown prices.
- The active application datasets remain unchanged.

The development scenarios use annotated extraction, not hosted inference. These
results establish backend regression behaviour; they do not measure Qwen accuracy.
No held-out examples were executed. All 327 phone values have recognized Moroccan
formats; actual phone reachability is not verified. Eleven addresses are missing.
Stock, opening hours and dated duty coverage remain unknown/unverified.

Reproduce the offline scenario check with a fresh output filename:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_baseline offline --catalogue data/staging/demo_enrichment_v1/ammps_medications_enriched.jsonl --pharmacy-directory data/staging/demo_enrichment_v1/pharmacies_rabat.jsonl --output reports/development_backend_enrichment_candidate_recheck.json
```

To rebuild from the same saved raw pages into a new candidate directory:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.prepare_demo_enrichment --output-directory data/staging/demo_enrichment_v2
```

Both commands are offline. Existing evidence is preserved rather than overwritten.

## Review checkpoint

Review `reports/demo_enrichment_candidate.json`,
`reports/development_backend_enrichment_candidate_v1.json`,
`reports/collection_expansion_checkpoint.json`, and the candidate's
`reconciliation.json`. The collection audit correctly reports
`all_collections_finished: false` because Medicament.ma was intentionally stopped;
this is an accepted scope cutoff, not a claim of exhaustive collection.

The candidate was subsequently activated after user approval. The demo now reads
the expanded files under `data/processed/`; a running server must be restarted
by the user to reload them. The earlier datasets and quality reports are archived.
`reports/demo_enrichment_activation.json` records the active hashes and backup.
