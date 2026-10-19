"""Freeze cached observations and build an offline enrichment candidate, without publishing."""

import argparse
import copy
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pharmacy_assistant.build_reference_data import ATC_PATTERN, link_secondary
from pharmacy_assistant.catalog import DATASET
from pharmacy_assistant.collection_http import write_json
from pharmacy_assistant.expand_medications import quality
from pharmacy_assistant.expand_pharmacies import directory_quality
from pharmacy_assistant.models import Medication
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.quality_ammps import validate_records
from pharmacy_assistant.supplementary_sources import (
    parse_medicament_detail, parse_saydalia_listing, write_jsonl,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data/staging/demo_enrichment_v1"
ENRICHMENT_FIELDS = {"atc_code", "reimbursement_status", "source_observations", "data_conflicts"}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Source timestamps must include a timezone")
    return parsed


def merge_observations(previous: list[dict], current: list[dict], source: str):
    """Keep one entire latest observation per source ID; never blend snapshots."""
    selected = {}
    current_ids = set()
    for group in (previous, current):
        seen = set()
        for record in group:
            identifier = record["source_record_id"]
            if identifier in seen:
                raise ValueError("Duplicate source ID within an input snapshot")
            seen.add(identifier)
            if record["source"] != source or urlparse(record["source_url"]).netloc != source:
                raise ValueError("Source provenance does not match its dataset")
            timestamp = checked_time(record["fetched_at_utc"])
            old = selected.get(identifier)
            if old:
                old_time = checked_time(old["fetched_at_utc"])
                if timestamp == old_time and record != old:
                    raise ValueError("Conflicting observations with the same source ID and fetch time")
                if timestamp < old_time:
                    continue
            selected[identifier] = record
            if group is current:
                current_ids.add(identifier)
    return sorted(selected.values(), key=lambda r: r["source_record_id"]), {
        "previous_records": len(previous), "verified_collected_records": len(current),
        "selected_records": len(selected), "retained_previous_only": len(set(selected) - current_ids),
        "policy": "Latest complete observation per source ID, keeping earlier IDs not refreshed",
    }


def verify_collected(directory: Path, source: str):
    paths = sorted((directory / "parsed").glob("*.json"))
    if not paths:
        raise ValueError("No parsed collection units found")

    def verify(path):
        meta = json.loads((directory / "raw" / f"{path.stem}.meta.json").read_text(encoding="utf-8"))
        body = (directory / "raw" / f"{path.stem}.html").read_bytes()
        if hashlib.sha256(body).hexdigest() != meta["sha256"] or meta["status_code"] != 200:
            raise ValueError(f"Invalid source cache for {path.name}")
        if urlparse(meta["requested_url"]).netloc != source:
            raise ValueError("Collection unit has an unexpected source host")
        html = body.decode("utf-8-sig")
        parsed = ([parse_medicament_detail(html, meta["requested_url"], meta["fetched_at_utc"])]
                  if source == "medicament.ma" else parse_saydalia_listing(html, meta["fetched_at_utc"]))
        if parsed != json.loads(path.read_text(encoding="utf-8")):
            raise ValueError(f"Saved observations differ from reparsed raw content: {path.name}")
        evidence = {r["source_record_id"]: {"cache_unit": path.stem,
                    "collection_url": meta["source_url"], "raw_sha256": meta["sha256"],
                    "fetched_at_utc": meta["fetched_at_utc"]} for r in parsed}
        return parsed, evidence

    records, provenance = [], {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, (parsed, evidence) in enumerate(pool.map(verify, paths), 1):
            if set(evidence) & set(provenance):
                raise ValueError("Duplicate source IDs across parsed collection units")
            records.extend(parsed)
            provenance.update(evidence)
            if index % 100 == 0:
                print(f"Offline verification {source}: {index}/{len(paths)} cached units", flush=True)
    return records, provenance


def build_candidate(primary: list[dict], observations: list[dict]):
    candidate = copy.deepcopy(primary)
    for record in candidate:
        record.update(atc_code=None, reimbursement_status=None, source_observations=[], data_conflicts=[])
    matching = link_secondary(candidate, observations)
    validated = [Medication.model_validate(record).model_dump(mode="json") for record in candidate]
    quality_report = validate_records(validated, "ammps_medications_enriched_candidate.jsonl")
    if not quality_report["passed"]:
        raise ValueError("Enrichment candidate failed catalogue validation")
    # All official facts, identities and presentation boundaries must stay exact.
    if len(primary) != len(validated) or any(
        {k: v for k, v in old.items() if k not in ENRICHMENT_FIELDS} !=
        {k: v for k, v in new.items() if k not in ENRICHMENT_FIELDS}
        for old, new in zip(primary, validated)
    ):
        raise ValueError("Enrichment unexpectedly changed official catalogue facts")
    return validated, matching, quality_report


def prepare(output: Path = DEFAULT_OUTPUT):
    if (output / "manifest.json").exists():
        raise ValueError("Candidate exists; choose a new --output-directory to preserve evidence")
    output.mkdir(parents=True, exist_ok=True)
    source_root = ROOT / "data/staging/secondary_expansion_v1"
    official = rows(DATASET)
    before_hash = digest(DATASET)
    observations, source_reports, evidence = [], {}, {}
    for short, source in (("medicament", "medicament.ma"), ("saydalia", "saydalia.ma")):
        directory = source_root / short
        current, provenance = verify_collected(directory, source)
        previous_path = ROOT / f"data/processed/{short}_medications.jsonl"
        previous = rows(previous_path)
        selected, stats = merge_observations(previous, current, source)
        source_manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        write_json(output / "inputs" / f"original_{short}_manifest.json", source_manifest)
        write_jsonl(output / "inputs" / f"{short}_medications.jsonl", selected)
        write_jsonl(output / "inputs" / f"previous_{short}_medications.jsonl", previous)
        source_reports[short] = {**stats, "quality": quality(selected),
            "collection_complete": source_manifest["collection_complete"],
            "original_manifest_sha256": digest(directory / "manifest.json"),
            "prior_snapshot_sha256": digest(previous_path),
            "frozen_records_sha256": digest(output / "inputs" / f"{short}_medications.jsonl")}
        evidence[short] = provenance
        observations.extend(selected)
        # Recover completed units beyond the last 20-unit checkpoint, using only
        # raw bytes that have just been hashed and reparsed above.
        write_jsonl(directory / "medications.jsonl", sorted(current, key=lambda r: r["source_record_id"]))
        source_manifest.update(record_count=len(current), quality=quality(current),
            units_completed=len(list((directory / "parsed").glob("*.json"))),
            stop_reason="finished" if source_manifest["collection_complete"] else "user_agreed_cutoff",
            cutoff_accepted=True, frozen_at_utc=datetime.now(timezone.utc).isoformat())
        write_json(directory / "manifest.json", source_manifest)
    write_json(output / "inputs/source_provenance.json", evidence)
    candidate, matching, catalogue_quality = build_candidate(official, observations)
    candidate_path = output / "ammps_medications_enriched.jsonl"
    write_jsonl(candidate_path, candidate)
    write_json(output / "catalogue_quality.json", catalogue_quality)
    write_json(output / "reconciliation.json", matching)
    pharmacy_path = ROOT / "data/staging/pharmacy_expansion_v1/rabat/pharmacies.jsonl"
    directory = PharmacyDirectory.from_path(pharmacy_path)
    pharmacy_rows = [record.model_dump(mode="json") for record in directory.records]
    write_jsonl(output / "pharmacies_rabat.jsonl", pharmacy_rows)
    duty_path = ROOT / "data/staging/pharmacy_expansion_v1/rabat/duty_observations.jsonl"
    write_jsonl(output / "pharmacy_duty_observations.jsonl", rows(duty_path))
    if digest(DATASET) != before_hash:
        raise ValueError("Active catalogue changed during preparation; review before proceeding")
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_prepared_for_validation", "staging_only": True,
        "collection_cutoff_accepted": True, "inference_requests": 0,
        "source_records": source_reports, "official_records": len(candidate),
        "official_facts_unchanged": True, "active_catalogue_sha256": before_hash,
        "candidate_sha256": digest(candidate_path),
        "baseline_enriched_presentations": sum(bool(r["source_observations"]) for r in official),
        "enriched_presentations": sum(bool(r["source_observations"]) for r in candidate),
        "records_with_atc": sum(r["atc_code"] is not None for r in candidate),
        "records_with_reimbursement": sum(r["reimbursement_status"] is not None for r in candidate),
        "matched_observations": len(matching["matched_observations"]),
        "matched_by_source": dict(Counter(m["source"] for m in matching["matched_observations"])),
        "unmatched_observations": len(matching["unmatched_observations"]),
        "ambiguous_observations": len(matching["ambiguous_observations"]),
        "conflicts": len(matching["conflicts"]),
        "invalid_atc_observations": sum(bool(o.get("atc_code")) and not ATC_PATTERN.fullmatch(o["atc_code"])
                                        for o in observations),
        "pharmacies": directory_quality(pharmacy_rows),
        "pharmacy_candidate_sha256": digest(output / "pharmacies_rabat.jsonl"),
        "quality_passed": catalogue_quality["passed"],
        "policy": "Only unique exact normalized brand, dosage, form and package joins; official facts retained; unmatched observations remain separate",
        "publication": "Deferred pending user validation; no application data replaced",
    }
    write_json(output / "manifest.json", report)
    write_json(ROOT / "reports/demo_enrichment_candidate.json", report)
    print(json.dumps({key: report[key] for key in ("official_records", "enriched_presentations",
        "records_with_atc", "records_with_reimbursement", "matched_observations",
        "unmatched_observations", "ambiguous_observations", "conflicts", "quality_passed")}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    prepare(args.output_directory)


if __name__ == "__main__":
    main()
