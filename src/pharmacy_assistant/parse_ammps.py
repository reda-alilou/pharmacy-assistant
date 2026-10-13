import json
from datetime import datetime, timezone
from pathlib import Path
import sys

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "ammps"


def parse_ammps(html: bytes) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records = []

    for card in soup.select(".medicament-card"):
        target = card.get("data-bs-target")

        if not target or not target.startswith("#medicamentModal"):
            raise ValueError("Medication card has no details reference.")

        modal = soup.select_one(target)

        if modal is None:
            raise ValueError(f"Details popup not found: {target}")

        name = card.select_one(".medicament-title")

        if name is None:
            raise ValueError(f"Medication name missing: {target}")

        details = {}

        for item in modal.select(".ammps-modal-item"):
            label = item.select_one(".ammps-modal-label")
            value = item.select_one(".ammps-modal-value")

            if label is None or value is None:
                raise ValueError(f"Malformed details: {target}")

            details[label.get_text(" ", strip=True)] = (
                value.get_text(" ", strip=True)
            )

        records.append({
            "source_record_id": target.removeprefix("#medicamentModal"),
            "brand_name": name.get_text(" ", strip=True),
            "details": details,
        })

    if not records:
        raise ValueError("No medication records found.")

    return records


def main():
    page = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    if page < 1:
        raise ValueError("Page number must be positive.")

    input_file = DATA_DIR / f"page_{page}.html"
    output_file = DATA_DIR / f"page_{page}.json"

    html = input_file.read_bytes()
    records = parse_ammps(html)

    result = {
        "source": "AMMPS",
        "source_url": (
            f"https://www.ammps.gov.ma/recherche-medicaments?page={page}"
        ),
        "parsed_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
    }

    output_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Page: {page}")
    print(f"Extracted: {len(records)} medications")
    print(f"Saved to: {output_file}")

    for record in records[:3]:
        print(record["brand_name"], "→", record["details"]["Dosage"])

if __name__ == "__main__":
    main()