import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]

PAGE = 1

BASE_URL = (
    "https://www.ammps.gov.ma/basesdedonnes/"
    "liste_marocaine_des_medicaments"
)

INPUT = ROOT / f"data/raw/ammps_detailed/page_{PAGE}.html"
OUTPUT = ROOT / f"data/raw/ammps_detailed/page_{PAGE}.json"


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.select("#medicamentsTable tbody > tr")

    if not rows:
        raise ValueError("No medication rows found.")

    records = []
    seen_ids = set()

    for row in rows:
        cells = row.find_all("td", recursive=False)

        if len(cells) != 8:
            raise ValueError(
                f"Expected 8 columns, found {len(cells)}."
            )

        button = row.select_one("button[data-bs-target]")
        target = button.get("data-bs-target", "") if button else ""

        match = re.fullmatch(
            r"#medicamentModal(\d+)",
            target,
        )

        if not match:
            raise ValueError(f"Invalid detail target: {target!r}")

        record_id = match.group(1)

        if record_id in seen_ids:
            raise ValueError(f"Duplicate ID: {record_id}")

        seen_ids.add(record_id)

        modal = soup.find(id=f"medicamentModal{record_id}")

        if modal is None:
            raise ValueError(
                f"Missing details for medication {record_id}"
            )

        details = {}

        for item in modal.select(".ammps-modal-item"):
            label = item.select_one(".ammps-modal-label")
            value = item.select_one(".ammps-modal-value")

            if label is None or value is None:
                raise ValueError(
                    f"Incomplete details for medication {record_id}"
                )

            details[label.get_text(" ", strip=True)] = (
                value.get_text(" ", strip=True)
            )

        # Confirm that table data agrees with the detail modal.
        for label, column in (
            ("Substance active", 3),
            ("Classe thérapeutique", 4),
            ("EPI", 5),
            ("Statut commercialisation", 6),
        ):
            table_value = cells[column].get_text(" ", strip=True)

            if details.get(label) != table_value:
                raise ValueError(
                    f"Table/detail mismatch: {record_id}, {label}"
                )

        details["Dosage"] = cells[1].get_text(" ", strip=True)
        details["Forme"] = cells[2].get_text(" ", strip=True)

        records.append(
            {
                "source_record_id": record_id,
                "brand_name": cells[0].get_text(" ", strip=True),
                "details": details,
            }
        )

    return records


def main():
    html = INPUT.read_text(encoding="utf-8")

    records = parse_page(html)

    payload = {
        "source": "AMMPS",
        "source_page": PAGE,
        "source_url": f"{BASE_URL}?page={PAGE}",
        "record_count": len(records),
        "records": records,
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Parsed: {len(records)} records")
    print(
        f"Unique IDs: "
        f"{len({record['source_record_id'] for record in records})}"
    )
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()