import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT / "data/raw/ammps/medications_combined.jsonl"
)

OUTPUT_FILE = (
    PROJECT_ROOT / "data/processed/ammps_medications.jsonl"
)


def normalize_text(value):
    if value is None:
        return None

    return re.sub(r"\s+", " ", value).strip() or None


def normalize_price(raw_price):
    """
    Examples:
        '10,70 DH'     -> 10.70
        '10.411.00 DH' -> 10411.00
        'SANS PPV DH'  -> None

    Unknown formats raise an error instead of producing
    potentially incorrect medication prices.
    """

    if not raw_price:
        return None

    value = normalize_text(raw_price).upper()
    value = re.sub(r"\s*DH$", "", value).strip()

    if re.fullmatch(r"SANS\s*(?:PPV|PH|PFHT)", value):
        return None

    # Thousands separators followed by two decimal digits.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+\.\d{2}", value):
        whole, decimals = value.rsplit(".", 1)
        value = f"{whole.replace('.', '')}.{decimals}"

    # French decimal comma.
    elif re.fullmatch(r"\d+,\d{2}", value):
        value = value.replace(",", ".")

    # Ordinary decimal or integer.
    elif not re.fullmatch(r"\d+(?:\.\d{2})?", value):
        raise ValueError(f"Unknown price format: {raw_price!r}")

    return float(Decimal(value))


def process_record(record):
    details = record["details"]

    required_fields = {
        "Substance active",
        "EPI",
        "Dosage",
        "Forme",
        "Présentation",
        "Statut commercialisation",
        "PPV",
        "PH",
    }

    missing = required_fields - details.keys()

    if missing:
        raise ValueError(
            f"Record {record['source_record_id']} "
            f"is missing fields: {missing}"
        )

    return {
        "source_record_id": record["source_record_id"],
        "brand_name": normalize_text(record["brand_name"]),
        "active_substance": normalize_text(details["Substance active"]),
        "epi": normalize_text(details["EPI"]),
        "dosage": normalize_text(details["Dosage"]),
        "form": normalize_text(details["Forme"]),
        "presentation": normalize_text(details["Présentation"]),
        "commercialization_status": normalize_text(
            details["Statut commercialisation"]
        ),
        "ppv_price_mad": normalize_price(details["PPV"]),
        "hospital_price_mad": normalize_price(details["PH"]),
        "source": record["source"],
        "source_page": record["source_page"],
        "source_url": record["source_url"],
    }


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    processed = []
    seen_ids = set()

    with INPUT_FILE.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            raw_record = json.loads(line)
            record = process_record(raw_record)

            record_id = record["source_record_id"]

            if record_id in seen_ids:
                raise ValueError(f"Duplicate ID: {record_id}")

            seen_ids.add(record_id)
            processed.append(record)

    # Do not overwrite the output with an empty dataset.
    if not processed:
        raise ValueError("No records to process.")

    temporary_file = OUTPUT_FILE.with_suffix(".jsonl.tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        for record in processed:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    temporary_file.replace(OUTPUT_FILE)

    statuses = Counter(
        record["commercialization_status"]
        for record in processed
    )

    missing_prices = sum(
        record["ppv_price_mad"] is None
        for record in processed
    )

    print(f"Processed records: {len(processed)}")
    print(f"Unique IDs: {len(seen_ids)}")
    print(f"Missing PPV prices: {missing_prices}")
    print(f"Commercialization statuses: {dict(statuses)}")
    print(f"Output: {OUTPUT_FILE}")

    print("\nExample:")
    print(json.dumps(processed[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()