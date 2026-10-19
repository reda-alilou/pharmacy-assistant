# Data checkpoint: three sources and a Rabat directory

This is the historical October 18 snapshot. Expanded data is now active; see the
[current demo test guide](test-expanded-demo.md) and [accepted cutoff](demo-enrichment-cutoff.md).

Collection and validation completed on 2026-10-18. The user subsequently approved
continuation; integration is documented in the [Step 3 guide](step-3-validation.md).

## Collected data and scope

| Source | Collected | Scope |
| --- | --- | --- |
| AMMPS detailed listing | 497 pages, 9,936 unique presentations | Complete fresh snapshot of the source-advertised catalogue |
| Medicament.ma | 60 detail records, first listing pages for A, B and D | Bounded enrichment sample |
| Saydalia medications | Three listing pages, 36 records | Bounded enrichment sample |
| Saydalia pharmacy map | Three Rabat search points, 115 unique Rabat pharmacies | Partial city directory |

The live AMMPS catalogue advertised 9,936 records, compared with 9,908 in the old
cached pages. A separate fresh snapshot was collected to avoid mixing pagination
from different versions. Every page's declared total, expected row count, and IDs
were checked; all 9,936 IDs are unique. The earlier 2,640-record processed dataset
was archived before the replacement was published.

The two secondary medication samples are not complete national catalogues.
Rabat's directory is not complete city coverage. Static pharmacy records have
names, source-provided phone numbers/addresses, coordinates and collection dates.
All 115 records have phones; four have no address. Missing addresses remain null.

## Enrichment and conflicts

An external record is linked only when its normalized brand, strength, form and
package signature identify exactly one AMMPS presentation. Package sizes and
volume units remain significant. Missing strengths/packages, ambiguous matches,
and products explicitly labelled as supplements/devices are not auto-merged.

Results:

- 22 Medicament.ma observations and 13 Saydalia observations linked to 27 distinct
  official presentations. All 96 secondary records remain in their own datasets.
- 27 presentations gained a sourced ATC code and 20 gained a sourced reimbursement
  status. These are source-reported values, not individual eligibility decisions.
- 61 observations remain separate for review. No ambiguous candidates were merged.
- Five price/status differences were flagged. Canonical AMMPS prices and statuses
  were preserved; secondary values remain in `source_observations` and
  `data_conflicts` with their URLs and timestamps.
- Two secondary records contain the incomplete ATC value `L02BX0`. It is preserved
  as observed and is not promoted to a canonical ATC code.
- 98 actual RCP/NAF document URLs were recovered from AMMPS HTML. The documents
  themselves were not downloaded or interpreted in this checkpoint.

The published medication dataset remains
`data/processed/ammps_medications_enriched.jsonl`. New optional fields are
`source_fetched_at_utc`, `atc_code`, `reimbursement_status`, `source_observations`,
and `data_conflicts`. The existing search endpoint remains available. Its scope
continues to be labelled partial because coverage across the three sources is
partial, despite the complete dated AMMPS snapshot.

AMMPS has 1,126 unknown public prices, hospital prices and PFHT prices each.
`NA` and `SANS ...` markers become null, never zero. Other unrecognized formats
still fail validation. Source placeholders for some other fields remain preserved
verbatim; missing/unknown strengths cannot be used for automatic cross-source joins.

## Pharmacy duty and stock

The public Saydalia map results provide no dated duty intervals. Their raw duty
markers are retained separately in
`data/processed/pharmacy_duty_observations.jsonl`, with `duty_verified: false` and
unknown validity dates. None of the 115 observations establishes that a pharmacy
is on duty today. Ordinary opening information is also left unknown when absent.

The directory is `data/processed/pharmacies_rabat.jsonl`. It will support pharmacy
service integration in the next application step. It supplies no pharmacy stock
data; national commercialization status remains distinct from local stock.

## Reproduce

From the project directory in PowerShell:

```powershell
# Resume the existing AMMPS snapshot using verified cached pages.
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.collect_ammps_snapshot --delay 2

# Resume the bounded secondary medication samples.
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.supplementary_sources --source medicament
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.supplementary_sources --source saydalia

# Resume the three-point Rabat directory sample.
.\.venv\Scripts\python.exe -u -m pharmacy_assistant.collect_rabat_pharmacies

# Validate and publish the complete official snapshot and conservative source links.
.\.venv\Scripts\python.exe -m pharmacy_assistant.build_reference_data
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Collectors use sequential requests, a two-second minimum request interval, bounded
retries, raw-response caching, collection timestamps and SHA-256 cache checks.
Rerunning resumes the same cached snapshot; it does not assert freshness on a
later date. For a new AMMPS snapshot use `collect_ammps_snapshot --directory <new-dir>`,
then `build_reference_data --snapshot-directory <new-dir>` after reviewing completion.
Secondary raw caches similarly preserve their original collection dates.

Source requests were identified from public pages and their normal listing/map
requests. The map collector uses Saydalia's public browser-map configuration and
normal result-limit parameter. Browser-map tokens are excluded from cache request
metadata and pharmacy records. No Google Maps API requests are made by the collector.

## Verify through the API

Restart the server after rebuilding data:

```powershell
.\.venv\Scripts\python.exe -m uvicorn pharmacy_assistant.api:app --host 127.0.0.1 --port 8000
```

- `/health`: 9,936 medication records; model configuration still available.
- `/medications/search?query=ZINNAT`: eight presentations from the expanded catalogue.
- `/medications/search?query=ABIP&strength=15mg`: two ABIP tablet presentations,
  retaining 268 MAD for the box of 20 and 372 MAD for the box of 30.
- `/medications/9080`: the box-of-30 ABIP record now includes Medicament.ma's
  `N05AX12` observation, its source URL, and collection/update dates.
- `/medications/2128`: official price retained, with differing Saydalia price/status
  values explicitly flagged rather than silently substituted.

Raw search is still substring-based: `ABIP` alone also finds `RABIPUR` in the larger
catalogue. Strength filters distinguish the tablet presentations. Exact-name
priority and conversational entity resolution belong to Step 3.

Evidence:

- `reports/ammps_quality.json`: full official dataset validation, zero schema/ID/price/provenance errors.
- `reports/reference_data_quality.json`: source matches, unmatched records, invalid ATC values and conflicts.
- `reports/pharmacies_rabat_quality.json`: Rabat counts, missing fields and unverified duty status.
- `data/raw/ammps_snapshot/manifest.json`: advertised totals and complete page coverage.

All 49 offline tests passed against the published catalogue, including parser,
cache integrity, conservative matching, conflict preservation, missing prices,
API compatibility and unverified duty handling.
