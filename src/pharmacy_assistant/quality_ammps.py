"""Validate the enriched catalogue without treating unknown prices as zero."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from pharmacy_assistant.catalog import DATASET
from pharmacy_assistant.models import DETAILED_SOURCE, Medication


ROOT = Path(__file__).resolve().parents[2]
INPUT = DATASET
OUTPUT = ROOT / "reports/ammps_quality.json"
PRICE_FIELDS = ("ppv_price_mad", "hospital_price_mad", "pfht_price_mad")


def validate_records(records: list[dict], dataset_name: str = INPUT.name) -> dict:
    errors = []
    valid_records = []
    ids = set()
    if not records:
        errors.append("Dataset is empty")

    for index, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            errors.append(f"Row {index}: expected a JSON object")
            continue
        record_id = raw.get("source_record_id")
        if isinstance(record_id, str):
            if record_id in ids:
                errors.append(f"Row {index}: duplicate ID {record_id}")
            ids.add(record_id)
        try:
            valid_records.append(Medication.model_validate(raw))
        except ValidationError as error:
            for problem in error.errors(include_url=False, include_input=False):
                field = ".".join(map(str, problem["loc"])) or "record"
                errors.append(f"Row {index}: {field}: {problem['msg']}")

    pages_by_listing = defaultdict(set)
    records_per_listing = defaultdict(Counter)
    detailed_pages = set()
    for record in valid_records:
        listing = "detailed" if record.source_url.startswith(DETAILED_SOURCE) else "basic"
        pages_by_listing[listing].add(record.source_page)
        records_per_listing[listing][record.source_page] += 1
        if record.detailed_source_url:
            detailed_pages.add(int(record.detailed_source_url.rsplit("=", 1)[1]))

    statuses = Counter(r.commercialization_status for r in valid_records)
    missing_prices = {
        field: sum(getattr(record, field) is None for record in valid_records)
        for field in PRICE_FIELDS
    }
    references = [r.rcp_naf_reference for r in valid_records]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_name,
        "catalog_scope": "partial",
        "total_records": len(records),
        "validated_records": len(valid_records),
        "unique_ids": len(ids),
        "pages_by_listing": {k: sorted(v) for k, v in pages_by_listing.items()},
        "records_per_page_by_listing": {
            k: dict(sorted(v.items())) for k, v in records_per_listing.items()
        },
        "detailed_source_pages": sorted(detailed_pages),
        "missing_ppv": missing_prices["ppv_price_mad"],
        "missing_prices": missing_prices,
        "commercialization_statuses": dict(statuses),
        "missing_ppv_by_status": dict(Counter(
            r.commercialization_status for r in valid_records if r.ppv_price_mad is None
        )),
        "rcp_naf_references": {
            "missing": sum(value is None for value in references),
            "text_only": sum(
                value is not None and not value.startswith(("https://", "http://"))
                for value in references
            ),
            "http_links": sum(
                value is not None and value.startswith(("https://", "http://"))
                for value in references
            ),
        },
        "errors": errors,
        "passed": not errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate the enriched AMMPS catalogue.")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    records = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = validate_records(records, args.input.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)

    print(f"Dataset: {report['dataset']}")
    print(f"Records: {report['total_records']}")
    print(f"Unique IDs: {report['unique_ids']}")
    print(f"Detailed source pages: {len(report['detailed_source_pages'])}")
    print(f"Missing PPV (unknown, not zero): {report['missing_ppv']}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Quality check: {'PASS' if report['passed'] else 'FAIL'}")
    print(f"Report: {args.output}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
