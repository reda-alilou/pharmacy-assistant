# Attributed pharmaceutical CSV sample

`pharmaceutical-presentations.csv` is an explicit offline export from the
preserved `data/imports/ammps_medications_enriched.jsonl`, collected 2026-10-18.
AMMPS supplies reference identities/presentations/prices; linked Medicament.ma
and Saydalia observations/conflicts retain their own attribution in JSON text
columns. Each record retains source URL, source timestamp and source identity.
The sample combines the first 24 records, 8 missing-price records and 8 records
with linked observations, deduplicated by original source record ID.

Unknown source prices become empty CSV cells, never zero. In the wizard retain
the empty-cell missing marker, choose text for `source_record_id`, check the
suggested numeric fields and use ISO date/time for the timezone-bearing source
timestamp. Nested provenance remains JSON text, not additional imported records.
These are dated observations, not current prices, stock or clinical comparisons.
Source attribution does not establish a blanket redistribution license.

The file uses the same upload/validation/publication workflow as other CSVs.
Reproduce to a **new** path from the repository root (no inference or database):

```powershell
node tools/samples/export-pharmaceutical-csv.mjs --sample --output artifacts/pharmaceutical-sample.csv
```

Omit `--sample` to explicitly export all 9,936 source presentations for local
testing. The command refuses to overwrite existing output or alter source inputs.
