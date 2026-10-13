import json
from pathlib import Path

from pharmacy_assistant.process_ammps import (
    normalize_price,
    normalize_text,
    process_record,
)


ROOT = Path(__file__).resolve().parents[2]

ORIGINAL = ROOT / "data/processed/ammps_medications.jsonl"
DETAILED_DIR = ROOT / "data/raw/ammps_detailed"
OUTPUT = ROOT / "data/processed/ammps_medications_enriched.jsonl"

COMPARE_FIELDS = (
    "brand_name",
    "active_substance",
    "epi",
    "dosage",
    "form",
    "presentation",
    "commercialization_status",
    "ppv_price_mad",
    "hospital_price_mad",
)

NEW_FIELDS = (
    "authorization_status",
    "therapeutic_class",
    "pp_gn_raw",
    "pfht_price_mad",
    "vat_raw",
    "rcp_naf_reference",
    "detailed_source_url",
)


def main():
    records = [
        json.loads(line)
        for line in ORIGINAL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    original_count = len(records)

    by_id = {record["source_record_id"]: record for record in records}

    if len(by_id) != original_count:
        raise ValueError("Duplicate IDs in original dataset.")

    # Give every record the same schema.
    for record in records:
        for field in NEW_FIELDS:
            record[field] = None

    files = sorted(
        DETAILED_DIR.glob("page_*.json"),
        key=lambda path: int(path.stem.removeprefix("page_")),
    )

    if not files:
        raise ValueError("No detailed AMMPS JSON pages found.")

    detailed_ids = set()
    new_count = 0

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))

        page = int(path.stem.removeprefix("page_"))

        if payload["source_page"] != page:
            raise ValueError(f"Incorrect page number in {path}")

        if payload["record_count"] != len(payload["records"]):
            raise ValueError(f"Incorrect record count in {path}")

        for raw in payload["records"]:
            record_id = raw["source_record_id"]

            if record_id in detailed_ids:
                raise ValueError(f"Duplicate detailed ID: {record_id}")

            detailed_ids.add(record_id)

            normalized = process_record({
                **raw,
                "source": "AMMPS",
                "source_page": page,
                "source_url": payload["source_url"],
            })

            existing = by_id.get(record_id)

            if existing is not None:
                differences = [
                    field
                    for field in COMPARE_FIELDS
                    if existing[field] != normalized[field]
                ]

                if differences:
                    raise ValueError(
                        f"Conflicting data for ID {record_id}: "
                        f"{differences}"
                    )

                target = existing

            else:
                target = normalized

                for field in NEW_FIELDS:
                    target[field] = None

                records.append(target)
                by_id[record_id] = target
                new_count += 1

            details = raw["details"]

            reference = normalize_text(details["Lien RCP / NAF"])

            target.update({
                "authorization_status": normalize_text(
                    details["Statut AMM"]
                ),
                "therapeutic_class": normalize_text(
                    details["Classe thérapeutique"]
                ),
                "pp_gn_raw": normalize_text(
                    details["PP / GN"]
                ),
                "pfht_price_mad": normalize_price(
                    details["PFHT"]
                ),
                "vat_raw": normalize_text(
                    details["TVA"]
                ),
                "rcp_naf_reference": (
                    None if reference == "-" else reference
                ),
                "detailed_source_url": payload["source_url"],
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    temporary = OUTPUT.with_suffix(".jsonl.tmp")

    with temporary.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    temporary.replace(OUTPUT)

    print(f"Original records: {original_count}")
    print(f"Detailed records processed: {len(detailed_ids)}")
    print(f"New records: {new_count}")
    print(f"Final unique records: {len(by_id)}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()