import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "ammps"
OUTPUT_FILE = DATA_DIR / "medications_combined.jsonl"


def main():
    pages = sorted(
        (
            path
            for path in DATA_DIR.glob("page_*.json")
            if re.fullmatch(r"page_\d+\.json", path.name)
        ),
        key=lambda path: int(path.stem.split("_")[1]),
    )

    if not pages:
        raise RuntimeError("No parsed AMMPS pages found.")

    records_by_id = {}

    for path in pages:
        payload = json.loads(path.read_text(encoding="utf-8"))
        page_number = int(path.stem.split("_")[1])

        records = payload["records"]

        if len(records) != payload["record_count"]:
            raise ValueError(f"Invalid record count in {path.name}")

        for record in records:
            record_id = record["source_record_id"]

            if record_id in records_by_id:
                raise ValueError(f"Duplicate medication ID: {record_id}")

            records_by_id[record_id] = {
                **record,
                "source": "AMMPS",
                "source_page": page_number,
                "source_url": payload["source_url"],
            }

        print(f"Page {page_number}: {len(records)} records")

    # Write atomically: a failed write won't corrupt the existing dataset.
    temporary_file = OUTPUT_FILE.with_suffix(".jsonl.tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        for record in records_by_id.values():
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    temporary_file.replace(OUTPUT_FILE)

    print("\nDataset built successfully")
    print(f"Pages processed: {len(pages)}")
    print(f"Unique medications: {len(records_by_id)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()