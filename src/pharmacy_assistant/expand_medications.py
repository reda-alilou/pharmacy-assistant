"""Discover and stage secondary medication catalogues without publishing them.

The default is a complete, sequential, resumable run. --max-requests bounds a
single invocation, including retries; it never changes the intended coverage.
"""

import argparse
import hashlib
import json
import re
import string
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from pharmacy_assistant.collection_http import (
    CollectionBudgetReached, SourceClient, write_json,
)
from pharmacy_assistant.supplementary_sources import (
    parse_medicament_detail, parse_saydalia_listing, text, write_jsonl,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIRECTORY = ROOT / "data/staging/secondary_expansion_v1"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_failure(error: Exception) -> dict:
    """HTTP exceptions can contain browser tokens: never serialize their text."""
    result = {"type": type(error).__name__}
    if isinstance(error, ValueError):
        result["reason"] = str(error)[:200]
    if isinstance(error, requests.HTTPError) and error.response is not None:
        result["http_status"] = error.response.status_code
    return result


def source_url(url: str, origin: str, prefix: str) -> str:
    parsed = urlparse(urljoin(origin, url))
    if (parsed.scheme != "https" or parsed.netloc != urlparse(origin).netloc
            or not parsed.path.startswith(prefix)):
        raise ValueError("Discovered URL is outside the expected public source")
    return urlunparse(parsed._replace(query="", fragment=""))


def sitemap_locations(body: str) -> list[str]:
    root = ET.fromstring(body)
    if root.tag.rsplit("}", 1)[-1] not in {"sitemapindex", "urlset"}:
        raise ValueError("Unexpected sitemap document")
    return [node.text.strip() for node in root.findall(".//{*}loc") if node.text]


def saydalia_page_count(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    # A block/challenge/error page is not an empty or single-page catalogue.
    if not soup.select("article.w-grid-item.product"):
        raise ValueError("Saydalia listing structure missing")
    pages = [1]
    for anchor in soup.select(".pagination a, a.page-numbers"):
        href = anchor.get("href", "")
        match = re.search(r"/fr/medicaments/page/(\d+)/", href)
        if match:
            source_url(href, "https://saydalia.ma", "/fr/medicaments/")
            pages.append(int(match.group(1)))
    return max(pages)


def medicament_listing(html: str, url: str) -> tuple[list[str], int]:
    soup = BeautifulSoup(html, "html.parser")
    header = text(soup.select_one("h3")) or ""
    count = re.fullmatch(r"([\d\s\u00a0]+)\s+résultats?", header, re.I)
    if not count:
        raise ValueError("Medicament.ma listing result count missing")
    advertised = int(re.sub(r"\s", "", count.group(1)))
    urls = [source_url(a["href"], "https://medicament.ma", "/medicament/")
            for a in soup.select('.listing-item a[href*="/medicament/"]')]
    if (advertised > 0 and not urls) or len(urls) != len(set(urls)):
        raise ValueError("Missing or duplicate medication listing links")
    return urls, advertised


def quality(records: list[dict]) -> dict:
    fields = ("dosage", "form", "presentation", "active_substance", "ppv_price_mad",
              "atc_code", "reimbursement_raw")
    return {
        "records": len(records),
        "unique_ids": len({r["source_record_id"] for r in records}),
        "unique_source_urls": len({r["source_url"] for r in records}),
        "missing_fields": {field: sum(r.get(field) is None for r in records) for field in fields},
        "non_full_atc_observations": sum(bool(r.get("atc_code")) and not re.fullmatch(
            r"[A-Z]\d{2}[A-Z]{2}\d{2}", r["atc_code"]) for r in records),
        "invalid_atc_observations": sum(bool(r.get("atc_code")) and not re.fullmatch(
            r"[A-Z]\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?", r["atc_code"]) for r in records),
    }


def collect(source: str, directory: Path = DEFAULT_DIRECTORY,
            max_requests: int | None = None, delay: float = 2) -> dict:
    if source not in {"medicament", "saydalia"}:
        raise ValueError("Unknown source")
    directory = directory / source
    directory.mkdir(parents=True, exist_ok=True)
    origin = "https://medicament.ma" if source == "medicament" else "https://saydalia.ma"
    previous_path = directory / "medications.jsonl"
    previous = ([json.loads(line) for line in previous_path.read_text(encoding="utf-8").splitlines()
                 if line.strip()] if previous_path.exists() else [])
    records, errors, units = {r["source_record_id"]: r for r in previous}, [], []
    started = utc_now()
    state = {
        "source": source, "scope": "full_discovered_catalogue",
        "started_at_utc": started, "collection_complete": False,
        "discovery_complete": False, "staging_only": True,
        "delay_seconds": delay, "stop_reason": "running",
        "retained_previous_records": len(previous),
    }

    with SourceClient(origin, directory / "raw", delay=delay,
                      max_requests=max_requests) as client:
        def checkpoint():
            values = sorted(records.values(), key=lambda r: r["source_record_id"])
            write_jsonl(directory / "medications.jsonl", values)
            state.update(updated_at_utc=utc_now(), network_requests_this_run=client.request_count,
                         units_completed=len(units), record_count=len(values),
                         errors=errors, quality=quality(values))
            write_json(directory / "manifest.json", state)

        try:
            if source == "medicament":
                index, _ = client.get(origin + "/wp-sitemap.xml", "sitemap_index")
                maps = [source_url(u, origin, "/wp-sitemap-posts-medicament-")
                        for u in sitemap_locations(index)
                        if re.fullmatch(r"/wp-sitemap-posts-medicament-\d+\.xml", urlparse(u).path)]
                if not maps:
                    raise ValueError("No medication sitemaps discovered")
                sitemap_urls = []
                for index, url in enumerate(maps, 1):
                    body, _ = client.get(url, f"sitemap_{index}")
                    discovered = [source_url(u, origin, "/medicament/")
                                  for u in sitemap_locations(body)]
                    if not discovered:
                        raise ValueError("Empty medication sitemap")
                    sitemap_urls.extend(discovered)
                if len(sitemap_urls) != len(set(sitemap_urls)):
                    raise ValueError("Duplicate URLs across medication sitemaps")
                write_json(directory / "sitemap_urls.json", sitemap_urls)
                # The sitemap includes obsolete 404 URLs. Enumerate the current
                # advertised catalogue through every letter and listing page.
                urls = []
                state.update(sitemap_count=len(maps), sitemap_medication_urls=len(sitemap_urls),
                             listing_letters={}, listing_warnings=[])
                for letter in string.ascii_uppercase:
                    first_url = origin + f"/listing-des-medicaments/?lettre={letter}"
                    first, _ = client.get(first_url, f"listing_{letter}_1")
                    first_urls, advertised = medicament_listing(first, first_url)
                    letter_urls = list(first_urls)
                    if advertised and len(first_urls) != min(20, advertised):
                        raise ValueError("Unexpected Medicament.ma page size")
                    pages = max(1, (advertised + 19) // 20)
                    page_signatures = {tuple(first_urls)}
                    for page in range(2, pages + 1):
                        page_url = origin + f"/listing-des-medicaments/page/{page}/?lettre={letter}"
                        body, _ = client.get(page_url, f"listing_{letter}_{page}")
                        page_urls, page_advertised = medicament_listing(body, page_url)
                        expected = min(20, advertised - (page - 1) * 20)
                        if page_advertised != advertised or len(page_urls) != expected:
                            raise ValueError("Medicament.ma count changed or listing page incomplete")
                        signature = tuple(page_urls)
                        if signature in page_signatures:
                            raise ValueError("Medicament.ma repeated a complete listing page")
                        page_signatures.add(signature)
                        letter_urls.extend(page_urls)
                    if len(set(letter_urls)) != advertised:
                        state["listing_warnings"].append({
                            "letter": letter, "reason": "Repeated URLs across different listing pages",
                            "advertised_records": advertised, "unique_urls": len(set(letter_urls)),
                            "duplicates": {url: count for url, count in Counter(letter_urls).items() if count > 1},
                        })
                    urls.extend(letter_urls)
                    state["listing_letters"][letter] = {"advertised_records": advertised,
                                                        "pages": pages, "unique_urls": len(set(letter_urls))}
                    checkpoint()
                    print(f"medicament discovery: {letter}, {advertised} URLs, "
                          f"{len(urls)} total active URLs", flush=True)
                if len(set(urls)) != len(urls):
                    state["listing_warnings"].append({
                        "reason": "Duplicate discovery URLs retained once, original listings cached",
                        "listing_slots": len(urls), "unique_urls": len(set(urls))})
                urls = list(dict.fromkeys(urls))
                write_json(directory / "discovered_urls.json", urls)
                state.update(discovery_complete=True, sitemap_count=len(maps),
                             discovered_units=len(urls), discovered_medication_urls=len(urls))
                state["advertised_counts_reconciled"] = not state["listing_warnings"]
                checkpoint()
                work = list(enumerate(urls, 1))
            else:
                body, _ = client.get(origin + "/fr/medicaments/", "page_1")
                total_pages = saydalia_page_count(body)
                state.update(discovery_complete=True, discovered_units=total_pages,
                             discovered_listing_pages=total_pages)
                work = [(page, origin + "/fr/medicaments/" +
                         (f"page/{page}/" if page > 1 else ""))
                        for page in range(1, total_pages + 1)]
                checkpoint()

            consecutive_failures = 0
            seen_pages = set()
            seen_ids = set()
            # Prune obsolete observations only after current discovery succeeded.
            if source == "medicament":
                discovered_set = {url for _, url in work}
                records = {key: r for key, r in records.items() if r["source_url"] in discovered_set}
            for number, url in work:
                name = ("detail_" + hashlib.sha256(url.encode()).hexdigest()[:20]
                        if source == "medicament" else f"page_{number}")
                try:
                    html, meta = client.get(url, name)
                    if source == "medicament":
                        parsed = [parse_medicament_detail(html, url, meta["fetched_at_utc"])]
                    else:
                        parsed = parse_saydalia_listing(html, meta["fetched_at_utc"])
                        signature = tuple(r["source_record_id"] for r in parsed)
                        if signature in seen_pages:
                            raise ValueError("Repeated listing page; pagination may be ignored")
                        seen_pages.add(signature)
                        if saydalia_page_count(html) > total_pages:
                            raise ValueError("Catalogue page count changed during collection")
                    new_ids = [r["source_record_id"] for r in parsed]
                    if len(set(new_ids)) != len(new_ids) or any(i in seen_ids for i in new_ids):
                        raise ValueError("Duplicate source IDs across collection units")
                    for record in parsed:
                        source_url(record["source_url"], origin,
                                   "/medicament/" if source == "medicament" else "/fr/produit/")
                    records.update((r["source_record_id"], r) for r in parsed)
                    seen_ids.update(new_ids)
                    write_json(directory / "parsed" / f"{name}.json", parsed)
                    units.append(number)
                    consecutive_failures = 0
                except CollectionBudgetReached:
                    raise
                except (ValueError, requests.RequestException) as error:
                    errors.append({"unit": number, "url": url, **safe_failure(error)})
                    # A stale individual 404 is a coverage error, not an outage.
                    individual_missing = (isinstance(error, requests.HTTPError)
                                          and error.response is not None
                                          and error.response.status_code in {404, 410})
                    consecutive_failures = 0 if individual_missing else consecutive_failures + 1
                    # Do not hammer a source that is blocking or failing.
                    if isinstance(error, requests.HTTPError) and error.response is not None:
                        if error.response.status_code in {401, 403, 429}:
                            state["stop_reason"] = "source_rejected_requests"
                            break
                    if consecutive_failures >= 3:
                        state["stop_reason"] = "consecutive_source_failures"
                        break
                if number % 20 == 0:
                    checkpoint()
                    print(f"{source}: {len(units)}/{len(work)} units, {len(records)} records, "
                          f"{len(errors)} errors", flush=True)
            else:
                state["stop_reason"] = "finished" if not errors else "finished_with_errors"
            state["collection_complete"] = len(units) == len(work) and not errors
            if state["collection_complete"]:
                # A fully verified replay replaces a previous partial stage exactly.
                records = {key: r for key, r in records.items() if key in seen_ids}
        except CollectionBudgetReached:
            state["stop_reason"] = "request_budget_reached"
        except KeyboardInterrupt:
            state["stop_reason"] = "interrupted"
        except (ValueError, ET.ParseError, requests.RequestException) as error:
            errors.append({"phase": "discovery", **safe_failure(error)})
            state["stop_reason"] = "discovery_failed"
        finally:
            checkpoint()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=["medicament", "saydalia"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--delay", type=float, default=2)
    args = parser.parse_args()
    if args.delay < 2 or (args.max_requests is not None and args.max_requests < 0):
        parser.error("Delay must be at least 2 seconds; request budget must be nonnegative")
    state = collect(args.source, args.directory, args.max_requests, args.delay)
    print(json.dumps({key: state.get(key) for key in
                      ("source", "record_count", "discovered_units", "units_completed",
                       "collection_complete", "stop_reason", "network_requests_this_run")}), flush=True)
    raise SystemExit(0 if state["collection_complete"] else 2)


if __name__ == "__main__":
    main()
