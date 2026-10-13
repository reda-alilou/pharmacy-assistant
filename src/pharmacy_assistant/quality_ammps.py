import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "data/processed/ammps_medications.jsonl"
OUTPUT = ROOT / "reports/ammps_quality.json"

REQUIRED = [
    "source_record_id",
    "brand_name",
    "active_substance",
    "dosage",
    "form",
    "presentation",
    "commercialization_status",
]


def main():
    records = [
        json.loads(line)
        for line in INPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if not records:
        raise ValueError("Dataset is empty.")

    errors = []
    ids = set()

    for index, record in enumerate(records, start=1):
        for field in REQUIRED:
            if not record.get(field):
                errors.append(f"Row {index}: missing {field}")

        record_id = record.get("source_record_id")

        if record_id in ids:
            errors.append(f"Duplicate ID: {record_id}")

        ids.add(record_id)

        for field in ("ppv_price_mad", "hospital_price_mad"):
            price = record.get(field)

            if price is not None and (
                not isinstance(price, (int, float))
                or isinstance(price, bool)
                or not 0 <= price < float("inf")
            ):
                errors.append(f"Row {index}: invalid {field}")

        page = record.get("source_page")
        expected_url = (
            f"https://www.ammps.gov.ma/recherche-medicaments?page={page}"
        )

        if record.get("source_url") != expected_url:
            errors.append(f"Row {index}: incorrect source URL")

    pages = sorted(set(r["source_page"] for r in records))

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "unique_ids": len(ids),
        "pages": pages,
        "records_per_page": dict(
            sorted(Counter(r["source_page"] for r in records).items())
        ),
        "missing_ppv": sum(
            r["ppv_price_mad"] is None for r in records
        ),
        "commercialization_statuses": dict(
            Counter(r["commercialization_status"] for r in records)
        ),
        "missing_ppv_by_status": dict(
            Counter(
                r["commercialization_status"]
                for r in records
                if r["ppv_price_mad"] is None
            )
        ),
        "errors": errors,
        "passed": not errors,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Records: {report['total_records']}")
    print(f"Unique IDs: {report['unique_ids']}")
    print(f"Pages: {len(pages)}")
    print(f"Missing PPV: {report['missing_ppv']}")
    print(f"Errors: {len(errors)}")
    print(f"Quality check: {'PASS' if report['passed'] else 'FAIL'}")
    print(f"Report: {OUTPUT}")

    if errors:
        raise ValueError("Data-quality verification failed.")


if __name__ == "__main__":
    main()