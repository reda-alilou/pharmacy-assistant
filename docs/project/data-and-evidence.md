# Data and evidence

The running services use PostgreSQL. Two byte-preserved JSONL inputs remain for
explicit setup/import, reconstruction checks and offline fixtures:

| Active input | Records |
| --- | ---: |
| `data/imports/ammps_medications_enriched.jsonl` | 9,936 medication presentations |
| `data/imports/pharmacies_rabat.jsonl` | 327 pharmacy records |

The relational importer groups medication identities conservatively while
retaining every original presentation ID, exact stored prices, sources and
conflicts. Current input reconstruction produces 7,302 medication groups, 3,128
linked source observations and 1,260 conflict rows. Of the presentations, 1,126
have no recorded public price; absence is not zero. Source prices and pharmacy
contacts are historical observations rather than current guarantees.

`data/evaluation/` holds the active interpretation smoke cases, the 80-case
development/held-out annotations and later development regressions. Annotation
files and their manifests are preserved. The catalogue hash in an older dataset
manifest identifies its annotation snapshot; it is not silently replaced with
the newer enriched input hash.

Raw snapshots, historical secondary datasets, public ledgers/reports/screenshots
and earlier walkthroughs are under `archive/historical/` with their original
relative subtrees. [The manifest](../../archive/manifest.json) records exact
checkout hashes, original Git identities and both active input relocations.
`pharmacy-archive` verifies all 1,004 mapped files. Historical embedded paths and
contents are preserved; [the archive guide](../../archive/README.md) explains
how maintained tools resolve old input paths and reject changed evidence.

After R6, the user authorized local housekeeping. Obsolete builds, test exports,
logs and bytecode caches were removed; previously ignored raw downloads and
staging data were preserved with hashes under ignored `archive/local/`. They are
not current application inputs or part of the tracked archive manifest. Private
configuration, ledgers, backups and database volumes remain private and in place.
Collection/scraping/enrichment commands are retired;
runtime lookup never collects source data. Attribution and timestamps preserve
provenance without implying a blanket license over third-party source material.

## Evaluation interpretation

The historical frozen held-out run measured 34/40 backend cases, intent F1
92.86%, entity slot F1 95.91% and 48/48 schema-valid completions. A later correction
run measured 14/14 backend cases and 20/20 schema-valid completions, with raw
slot F1 85.71%. The latter combines seen failures with development variations;
it is not a new independent benchmark or proof of perfect overall accuracy.

Source reports and metrics are preserved in `archive/historical/reports/`,
including `held_out_qwen_frozen_v1.json`, `held_out_qwen_frozen_metrics.json`,
`matching_package_live_v2.json` and `matching_package_metrics_complete.json`.
Maintained tools can score the recorded outputs without inference. Old freezes
cannot authorize a current live run after code/data changes.

The small synthetic dataset was assistant-authored/reviewed. Independent human
or native-speaker review, population representativeness and universal extraction
accuracy are not claimed. Cleanup's deterministic oracle checks and mocked
provider tests measure engineering behavior, not fresh hosted-model accuracy.
