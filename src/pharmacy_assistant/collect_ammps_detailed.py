import argparse
import json
import time
from pathlib import Path

import requests

from pharmacy_assistant.parse_ammps_detailed import parse_page


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/raw/ammps_detailed"

BASE_URL = (
    "https://www.ammps.gov.ma/basesdedonnes/"
    "liste_marocaine_des_medicaments"
)

REQUEST_DELAY_SECONDS = 10


def save_atomic(path: Path, content: str):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def collect_page(session: requests.Session, page: int) -> bool:
    html_path = DATA_DIR / f"page_{page}.html"
    json_path = DATA_DIR / f"page_{page}.json"

    # Already collected: validate the cached data and skip the request.
    if html_path.exists() and json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))

        if (
            payload["source_page"] != page
            or payload["record_count"] != len(payload["records"])
            or not payload["records"]
        ):
            raise ValueError(f"Invalid cached page {page}")

        ids = [
            record["source_record_id"]
            for record in payload["records"]
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate IDs on cached page {page}")

        print(f"Page {page}: cached ({len(ids)} records)")
        return False

    url = f"{BASE_URL}?page={page}"

    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
    else:
        response = session.get(url, timeout=(10, 45))
        response.raise_for_status()
        html = response.text

    # Validate before saving either output.
    records = parse_page(html)

    if not records:
        raise ValueError(f"Empty results on page {page}")

    ids = [record["source_record_id"] for record in records]

    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate IDs on page {page}")

    payload = {
        "source": "AMMPS",
        "source_page": page,
        "source_url": url,
        "record_count": len(records),
        "records": records,
    }

    save_atomic(html_path, html)
    save_atomic(
        json_path,
        json.dumps(payload, ensure_ascii=False, indent=2),
    )

    print(f"Page {page}: collected ({len(records)} records)")
    return True


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)

    args = parser.parse_args()

    if args.start < 1 or args.end < args.start:
        parser.error("Invalid page range.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    session.headers.update({
        "User-Agent": "pharmacy-assistant-academic/0.1",
    })

    last_download = None

    for page in range(args.start, args.end + 1):
        # Space out actual requests, including after cached pages.
        html_path = DATA_DIR / f"page_{page}.html"

        if not html_path.exists() and last_download is not None:
            elapsed = time.monotonic() - last_download
            time.sleep(max(0, REQUEST_DELAY_SECONDS - elapsed))

        try:
            downloaded = collect_page(session, page)
        except (requests.RequestException, ValueError, KeyError) as error:
            print(f"Stopped at page {page}: {error}")
            raise SystemExit(1)

        if downloaded:
            last_download = time.monotonic()


if __name__ == "__main__":
    main()