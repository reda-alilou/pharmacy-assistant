from pathlib import Path
from datetime import datetime, timezone
import sys

import requests
from bs4 import BeautifulSoup


URL = "https://www.ammps.gov.ma/recherche-medicaments?page=1"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ammps"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    page = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    url = f"https://www.ammps.gov.ma/recherche-medicaments?page={page}"

    response = requests.get(
        url,
        headers={"User-Agent": "ChallengeCampResearch/0.1"},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")

    if "SUBSTANCE ACTIVE" not in soup.get_text().upper():
        raise RuntimeError("AMMPS medication records not found in response.")

    output_file = OUTPUT_DIR / f"page_{page}.html"
    output_file.write_bytes(response.content)

    print(f"Status: {response.status_code}")
    print(f"Page title: {soup.title.get_text(strip=True)}")
    print(f"Size: {len(response.content):,} bytes")
    print(f"Saved to: {output_file}")
    print(f"Collected at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()