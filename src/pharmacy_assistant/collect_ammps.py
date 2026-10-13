import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from pharmacy_assistant.parse_ammps import parse_ammps


BASE_URL = "https://www.ammps.gov.ma/recherche-medicaments"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "ammps"

START_PAGE = 1
END_PAGE = 20

REQUEST_DELAY_SECONDS = 10


def collect_page(page: int, session: requests.Session) -> list[dict]:
    url = f"{BASE_URL}?page={page}"

    html_path = DATA_DIR / f"page_{page}.html"
    json_path = DATA_DIR / f"page_{page}.json"

    if html_path.exists():
        html = html_path.read_bytes()
        origin = "cached"
    else:
        response = session.get(url, timeout=30)
        response.raise_for_status()

        html = response.content
        origin = "downloaded"

        # Validate the content before saving it.
        parse_ammps(html)

        html_path.write_bytes(html)

        time.sleep(REQUEST_DELAY_SECONDS)

    records = parse_ammps(html)

    result = {
        "source": "AMMPS",
        "source_url": url,
        "parsed_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
    }

    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Page {page:>3}: {len(records):>2} records ({origin})")

    return [
        {
            **record,
            "source": "AMMPS",
            "source_page": page,
            "source_url": url,
        }
        for record in records
    ]


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    completed_pages = 0

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "ChallengeCampResearch/0.1"
        })

        for page in range(START_PAGE, END_PAGE + 1):
            try:
                collect_page(page, session)

            except requests.RequestException as error:
                print(f"\nNetwork error on page {page}: {error}")
                print("Stopping collection. Previous pages are preserved.")
                break

            except ValueError as error:
                print(f"\nParsing error on page {page}: {error}")
                print("Stopping to avoid collecting incorrect data.")
                break

            completed_pages += 1

    print(f"\nPages successfully processed: {completed_pages}")
    print("Run build_ammps_dataset to rebuild the combined dataset.")

if __name__ == "__main__":
    main()