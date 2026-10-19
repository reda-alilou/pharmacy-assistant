# Test the expanded demo data

The validated data is now active in `data/processed/`:
9,936 AMMPS presentations, 2,700 enriched presentations, 1,008 Medicament.ma
observations, 5,299 Saydalia observations, and 327 Rabat pharmacies.
Official prices and presentation identities are unchanged. Secondary disagreements
remain visible. No scraper or demo server was started during activation.

## Restart and open

Stop both existing FastAPI and Streamlit processes in their terminals with Ctrl+C.
If both were launched together, stop that launcher. If FastAPI was started
separately, stop its terminal too: the launcher can reuse an already running API,
whose in-memory catalogue would still be the earlier data.

Then run from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.run_demo
```

Open <http://127.0.0.1:8501> and choose **Nouvelle conversation**.
No API key change is needed. Do not restart the deferred collection runner.

## Manual checks

| Ask / action | Expected recorded result |
| --- | --- |
| `Quel est le prix de ACOL 1000 mg, boîte de 30 ?` | 18.30 MAD. Expand **Sources et détails**: Saydalia should be among the references. |
| `Quel est le prix de ABIP ?` | Offer both presentations: box 20 at 268 MAD and box 30 at 372 MAD. |
| Select ABIP box 30, then type `et pour deux boites ?` | Keep box 30 and return a calculated total of 744.00 MAD. |
| `أعطني رقم هاتف صيدلية ابن نفيس في الرباط` | Arabic answer with the stored phone 0537720657. |
| `Donne-moi le numéro de la pharmacie Tour Hassan à Rabat.` | Pharmacie de la Tour Hassan, phone 0537720250. |
| `Bch7al ACOL 1000 mg, boite de 30 ?` | Darija/mixed-language price request resolves the same presentation at 18.30 MAD. |

These live questions exercise the configured hosted model. The prior API checks
used mocked extraction, with the real active catalogue, matching, context,
calculation and response construction. They did not spend inference quota.

For a zero-inference check of whether the API loaded the new data, open
<http://127.0.0.1:8000/medications/4262>. The ACOL record should include
`atc_code: "A10BA02"`, `reimbursement_status: "yes"`, and a Saydalia source
observation. The chat interface does not currently display every record field;
ATC/reimbursement values are available in the API record. Source-reported
reimbursement does not establish individual eligibility.

If a check fails, keep the exact question and answer. **Extraction JSON** helps
distinguish model extraction from lookup/context errors. A source-conflict message
is expected where observations disagree; AMMPS prices remain canonical. Stock,
current opening hours and dated duty schedules remain unverified.

## Activation evidence and recovery

- `reports/demo_enrichment_activation.json`: active hashes and verified backup path.
- `reports/demo_enrichment_activation_api_checks.json`: API health, enrichment,
  ABIP choices, follow-up total and pharmacy checks; zero live provider requests.
- `reports/development_backend_enrichment_candidate_v1.json`: all 40 development
  backend scenarios passed with annotated extraction before activation.

The earlier data and quality reports were backed up under
`data/processed/archive/demo_before_enrichment_20261019T185854238193Z/`.
The backup manifest records their SHA-256 hashes. Activation uses verified
per-file replacement and restores earlier files if replacement fails.
