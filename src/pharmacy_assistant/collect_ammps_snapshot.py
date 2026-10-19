"""Collect one complete fresh AMMPS snapshot without mixing older pagination."""

import argparse
import json
import math
import re
from pathlib import Path

from bs4 import BeautifulSoup

from pharmacy_assistant.collection_http import SourceClient, write_json
from pharmacy_assistant.parse_ammps_detailed import BASE_URL, parse_page


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "data/raw/ammps_snapshot"


def advertised_total(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    counter = soup.select_one(".ammps-results-count strong")
    if counter is None or not re.fullmatch(r"[\d\s]+", counter.get_text(strip=True)):
        raise ValueError("AMMPS total-record count is missing or invalid")
    return int(re.sub(r"\s+", "", counter.get_text()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--delay", type=float, default=2)
    args = parser.parse_args()
    if not 1 <= args.delay <= 60:
        parser.error("--delay must be between 1 and 60 seconds")

    ids = set()
    with SourceClient("https://www.ammps.gov.ma", args.directory, args.delay) as client:
        first, _ = client.get(f"{BASE_URL}?page=1", "page_1")
        total = advertised_total(first)
        page_size = len(parse_page(first))
        pages = math.ceil(total / page_size)
        print(f"AMMPS snapshot: {total} presentations, {pages} pages", flush=True)
        manifest = {"source": "AMMPS", "source_url": BASE_URL,
                    "advertised_total": total, "expected_pages": pages,
                    "completed_pages": 0, "unique_records": 0, "complete": False}
        write_json(args.directory / "manifest.json", manifest)
        for page in range(1, pages + 1):
            html, meta = client.get(f"{BASE_URL}?page={page}", f"page_{page}")
            if advertised_total(html) != total:
                raise ValueError("AMMPS catalogue changed during collection; snapshot needs review")
            records = parse_page(html)
            expected = min(page_size, total - (page - 1) * page_size)
            if len(records) != expected:
                raise ValueError(f"Unexpected record count on page {page}")
            page_ids = {record["source_record_id"] for record in records}
            if len(page_ids) != len(records) or ids.intersection(page_ids):
                raise ValueError(f"Duplicate IDs in snapshot at page {page}")
            ids.update(page_ids)
            write_json(args.directory / f"page_{page}.json", {
                "source": "AMMPS", "source_page": page,
                "source_url": f"{BASE_URL}?page={page}",
                "fetched_at_utc": meta["fetched_at_utc"],
                "advertised_total": total, "record_count": len(records), "records": records,
            })
            manifest.update(completed_pages=page, unique_records=len(ids),
                            complete=page == pages and len(ids) == total)
            write_json(args.directory / "manifest.json", manifest)
            print(f"AMMPS {page}/{pages}: {len(ids)}/{total} unique presentations", flush=True)


if __name__ == "__main__":
    main()
