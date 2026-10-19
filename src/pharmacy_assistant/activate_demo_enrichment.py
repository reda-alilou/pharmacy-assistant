"""Activate the user-approved frozen data, with verified backups and rollback."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pharmacy_assistant.collection_http import atomic_replace, write_json
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.prepare_demo_enrichment import DEFAULT_OUTPUT, ROOT, digest, rows
from pharmacy_assistant.quality_ammps import validate_records


def activate(candidate_dir: Path = DEFAULT_OUTPUT):
    candidate = json.loads((candidate_dir / "manifest.json").read_text(encoding="utf-8"))
    if candidate["status"] != "validated_pending_user_review" or not candidate["quality_passed"]:
        raise ValueError("Candidate has not passed validation")
    sources = {
        "ammps_medications_enriched.jsonl": candidate_dir / "ammps_medications_enriched.jsonl",
        "medicament_medications.jsonl": candidate_dir / "inputs/medicament_medications.jsonl",
        "saydalia_medications.jsonl": candidate_dir / "inputs/saydalia_medications.jsonl",
        "pharmacies_rabat.jsonl": candidate_dir / "pharmacies_rabat.jsonl",
        "pharmacy_duty_observations.jsonl": candidate_dir / "pharmacy_duty_observations.jsonl",
    }
    expected = {
        "ammps_medications_enriched.jsonl": candidate["candidate_sha256"],
        "pharmacies_rabat.jsonl": candidate["pharmacy_candidate_sha256"],
        **{f"{name}_medications.jsonl": item["frozen_records_sha256"]
           for name, item in candidate["source_records"].items()},
    }
    for name, checksum in expected.items():
        if digest(sources[name]) != checksum:
            raise ValueError(f"Candidate fingerprint mismatch: {name}")
    data = rows(sources["ammps_medications_enriched.jsonl"])
    quality = validate_records(data, "ammps_medications_enriched.jsonl")
    if not quality["passed"] or len(data) != candidate["official_records"]:
        raise ValueError("Candidate catalogue failed validation")
    directory = PharmacyDirectory.from_path(sources["pharmacies_rabat.jsonl"])
    duties = rows(sources["pharmacy_duty_observations.jsonl"])
    if ({r.pharmacy_id for r in directory.records} != {r["pharmacy_id"] for r in duties}
            or len(duties) != len(directory.records)
            or any(r["duty_verified"] or r["valid_from"] is not None or r["valid_until"] is not None for r in duties)):
        raise ValueError("Pharmacy duty evidence is inconsistent or claims verified dates")
    report_path = ROOT / "reports/demo_enrichment_activation.json"
    if all(digest(ROOT / "data/processed" / name) == digest(path) for name, path in sources.items()):
        if not report_path.exists():
            raise ValueError("Data already matches but activation evidence is missing; review manually")
        return json.loads(report_path.read_text(encoding="utf-8"))
    active_catalogue = ROOT / "data/processed/ammps_medications_enriched.jsonl"
    if digest(active_catalogue) != candidate["active_catalogue_sha256"]:
        raise ValueError("Active catalogue changed after candidate validation")
    for name, source in candidate["source_records"].items():
        if digest(ROOT / f"data/processed/{name}_medications.jsonl") != source["prior_snapshot_sha256"]:
            raise ValueError("Active source observations changed after candidate validation")

    matching = json.loads((candidate_dir / "reconciliation.json").read_text(encoding="utf-8"))
    reference = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "official_snapshot_complete": True, "official_records": len(data),
        "official_pages": len(quality["detailed_source_pages"]),
        "secondary_scope": "user_accepted_cutoff", "collection_cutoff_accepted": True,
        "secondary_records": {name: item["selected_records"] for name, item in candidate["source_records"].items()},
        "records_with_secondary_sources": candidate["enriched_presentations"],
        "records_with_atc": candidate["records_with_atc"],
        "records_with_reimbursement": candidate["records_with_reimbursement"],
        "matched_by_source": candidate["matched_by_source"],
        "matching_policy": candidate["policy"],
        "price_status_policy": "AMMPS retained; differing secondary observations preserved and flagged",
        "candidate_report": "reports/demo_enrichment_candidate.json", **matching,
    }
    pharmacy_quality = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "saydalia.ma", "city": "Rabat", **candidate["pharmacies"],
        "scope": "systematic_city_map_grid", "complete_city_directory": False,
        "undated_duty_observations": len(duties), "passed": True}
    payloads = {ROOT / "data/processed" / name: path.read_bytes() for name, path in sources.items()}
    for name, report in (("ammps_quality", quality), ("reference_data_quality", reference),
                         ("pharmacies_rabat_quality", pharmacy_quality)):
        payloads[ROOT / f"reports/{name}.json"] = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = ROOT / "data/processed/archive" / f"demo_before_enrichment_{stamp}"
    previous = {path: path.read_bytes() if path.exists() else None for path in payloads}
    backup_manifest = {}
    for path, content in previous.items():
        relative = path.relative_to(ROOT)
        if content is not None:
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            checksum = hashlib.sha256(content).hexdigest()
            if digest(target) != checksum:
                raise ValueError("Backup integrity check failed")
            backup_manifest[str(relative)] = checksum
    write_json(backup / "manifest.json", {"files": backup_manifest, "candidate_sha256": candidate["candidate_sha256"]})
    changed = []
    try:
        for path, content in payloads.items():
            temporary = path.with_suffix(path.suffix + ".activation.tmp")
            temporary.write_bytes(content)
            atomic_replace(temporary, path)
            changed.append(path)
            if digest(path) != hashlib.sha256(content).hexdigest():
                raise ValueError(f"Activated file fingerprint mismatch: {path.name}")
    except BaseException:
        for path in reversed(changed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
                continue
            temporary = path.with_suffix(path.suffix + ".rollback.tmp")
            temporary.write_bytes(previous[path])
            atomic_replace(temporary, path)
        raise
    report = {"status": "activated", "activated_at_utc": datetime.now(timezone.utc).isoformat(),
        "backup_directory": str(backup.relative_to(ROOT)), "backup_checksums": backup_manifest,
        "active_dataset_sha256": {name: digest(ROOT / "data/processed" / name) for name in sources},
        "medication_records": len(data), "enriched_presentations": candidate["enriched_presentations"],
        "source_records": reference["secondary_records"], "rabat_pharmacies": len(directory.records),
        "services_started_or_stopped": False, "inference_requests": 0,
        "restart_required": True, "collection_cutoff_accepted": True,
        "candidate_manifest": str((candidate_dir / "manifest.json").relative_to(ROOT))}
    write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = activate(args.candidate_directory)
    print(json.dumps({key: report[key] for key in
        ("status", "medication_records", "enriched_presentations", "rabat_pharmacies", "backup_directory")}))


if __name__ == "__main__":
    main()
