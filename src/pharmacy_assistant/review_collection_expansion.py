"""Offline staging audit; never publishes records or invokes an inference API."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from pharmacy_assistant.collection_http import write_json
from pharmacy_assistant.expand_medications import quality
from pharmacy_assistant.expand_pharmacies import directory_quality
from pharmacy_assistant.nlu_models import ExtractedEntities
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory

ROOT = Path(__file__).resolve().parents[2]


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cache_audit(directory: Path) -> dict:
    errors, dates, total = [], [], 0
    paths = sorted(directory.rglob("*.meta.json"))
    print(f"Cache audit: {directory.parent.name}, {len(paths)} responses", flush=True)
    def verify(path):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        raw = path.with_name(path.name.replace(".meta.json", ".html"))
        valid = raw.exists() and hashlib.sha256(raw.read_bytes()).hexdigest() == metadata["sha256"]
        return path, valid, metadata["fetched_at_utc"]
    # Local disk reads only. HTTP collection remains sequential per source.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for path, valid, fetched_at in pool.map(verify, paths):
            total += 1
            if not valid:
                errors.append(str(path.relative_to(directory)))
            dates.append(fetched_at)
            if total % 100 == 0:
                print(f"Cache audit: {directory.parent.name}, {total}/{len(paths)} verified", flush=True)
    return {"cached_responses": total, "sha256_errors": errors,
            "earliest_fetch_utc": min(dates, default=None), "latest_fetch_utc": max(dates, default=None)}


def medication_audit(directory: Path, source: str) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    records = jsonl(directory / "medications.jsonl")
    expected_host = "medicament.ma" if source == "medicament" else "saydalia.ma"
    provenance_errors = []
    for record in records:
        if (record.get("source") != expected_host or not record.get("source_record_id")
                or not record.get("fetched_at_utc") or
                urlparse(record.get("source_url", "")).netloc != expected_host):
            provenance_errors.append(record.get("source_record_id"))
    return {"manifest": manifest, "quality": quality(records),
            "cache_integrity": cache_audit(directory / "raw"),
            "provenance_errors": provenance_errors,
            "records_sha256": hashlib.sha256((directory / "medications.jsonl").read_bytes()).hexdigest()}


def pharmacy_audit(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    records = jsonl(directory / "pharmacies.jsonl")
    old_records = jsonl(ROOT / "data/processed/pharmacies_rabat.jsonl")
    old_ids = {r["pharmacy_id"] for r in old_records}
    ids = {r["pharmacy_id"] for r in records}
    directory_index = PharmacyDirectory.from_path(directory / "pharmacies.jsonl")
    checks = []
    for name, entities, expected_status, expected_id in [
        ("french_name", {"pharmacy": "Pharmacie Ibn Nafis", "city": "Rabat"}, "matches", "saydalia:5256"),
        ("arabic_name", {"pharmacy": "صيدلية ابن نفيس", "city": "الرباط"}, "matches", "saydalia:5256"),
        ("area_french", {"city": "Rabat", "area": "Agdal"}, "matches", None),
        ("area_arabic", {"city": "الرباط", "area": "اكدال"}, "matches", None),
        ("explicit_other_city", {"city": "Casablanca"}, "outside_coverage", None),
        ("unknown_name", {"pharmacy": "NoSuchPharmacyZXQ"}, "not_found", None),
        ("ambiguous_name", {"pharmacy": "Bab", "city": "Rabat"}, "ambiguous", None),
        ("browse_is_truncated", {"city": "Rabat"}, "matches", None),
    ]:
        base_entities = {field: None for field in ExtractedEntities.model_fields}
        base_entities.update(medications=[], **entities)
        result = directory_index.search(ExtractedEntities(**base_entities))
        checks.append({"name": name, "entities": entities, "result": result.model_dump(mode="json"),
                       "passed": result.status == expected_status and
                       (expected_id is None or [r.pharmacy_id for r in result.pharmacies] == [expected_id]) and
                       (name != "browse_is_truncated" or result.results_truncated)})
    phone_check = next((r["phone"] == "0537720657" for r in records if r["pharmacy_id"] == "saydalia:5256"), False)
    south, north, west, east = manifest["configuration"]["bounds"]
    return {"manifest": manifest, "quality": directory_quality(records),
            "cache_integrity": cache_audit(directory / "raw"),
            "baseline_records": len(old_records), "added_ids": sorted(ids - old_ids),
            "missing_baseline_ids": sorted(old_ids - ids), "ibn_nafis_phone_unchanged": phone_check,
            "records_outside_search_rectangle": [r["pharmacy_id"] for r in records if not
                (south <= r["latitude"] <= north and west <= r["longitude"] <= east)],
            "retrieval_checks": checks,
            "records_sha256": hashlib.sha256((directory / "pharmacies.jsonl").read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--medication-directory", type=Path, default=ROOT / "data/staging/secondary_expansion_v1")
    parser.add_argument("--pharmacy-directory", type=Path, default=ROOT / "data/staging/pharmacy_expansion_v1/rabat")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/collection_expansion_checkpoint.json")
    args = parser.parse_args()
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "staging_only": True, "inference_requests": 0,
              "medications": {source: medication_audit(args.medication_directory / source, source)
                              for source in ("medicament", "saydalia")},
              "pharmacies": pharmacy_audit(args.pharmacy_directory)}
    report["active_dataset_sha256"] = {name: hashlib.sha256((ROOT / "data/processed" / name).read_bytes()).hexdigest()
        for name in ("ammps_medications_enriched.jsonl", "medicament_medications.jsonl",
                     "saydalia_medications.jsonl", "pharmacies_rabat.jsonl", "pharmacy_duty_observations.jsonl")}
    report["all_collections_finished"] = all(
        item["manifest"]["collection_complete"] for item in
        [*report["medications"].values(), report["pharmacies"]])
    report["offline_integrity_passed"] = all(not item["cache_integrity"]["sha256_errors"]
        for item in [*report["medications"].values(), report["pharmacies"]]) and all(
            not item["provenance_errors"] for item in report["medications"].values())
    write_json(args.output, report)
    print(json.dumps({"all_collections_finished": report["all_collections_finished"],
                      "offline_integrity_passed": report["offline_integrity_passed"],
                      "medications": {key: item["quality"]["records"] for key, item in report["medications"].items()},
                      "pharmacies": report["pharmacies"]["quality"]["records"],
                      "pharmacy_retrieval_checks": [r["passed"] for r in report["pharmacies"]["retrieval_checks"]]}))


if __name__ == "__main__":
    main()
