"""Publish the validated official snapshot and conservative secondary-source links."""

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pharmacy_assistant.catalog import DATASET, normalize, normalize_strength
from pharmacy_assistant.collection_http import write_json
from pharmacy_assistant.models import Medication
from pharmacy_assistant.process_ammps import normalize_price, normalize_text, process_record
from pharmacy_assistant.quality_ammps import validate_records
from pharmacy_assistant.supplementary_sources import write_jsonl


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data/raw/ammps_snapshot"
ATC_PATTERN = re.compile(r"[A-Z]\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?")


def dose_key(value: str | None) -> str | None:
    if not value or normalize(value) in {"-", "na", "n/a", "non renseigne"}:
        return None
    value = normalize_strength(value).replace("mcg", "ug").replace("u.i.", "ui").replace("|", "/")
    return re.sub(r"\d+(?:\.\d+)?", lambda m: format(Decimal(m.group()).normalize(), "f"), value)


def form_key(value: str | None) -> str | None:
    if not value or normalize(value) in {"-", "na", "n/a", "non renseigne"}:
        return None
    value = re.sub(r"\[[^\]]*\]", "", normalize(value))
    return " ".join(word[:-1] if len(word) > 4 and word.endswith("s") else word
                    for word in re.findall(r"\w+", value))


def presentation_key(value: str | None):
    if not value:
        return None
    value = normalize(value).replace(",", ".")
    numbers = tuple(format(Decimal(n).normalize(), "f") for n in re.findall(r"\d+(?:\.\d+)?", value))
    if not numbers:
        return None  # Never guess an unstated package quantity.
    container = next((kind for kind in ("boite", "flacon", "tube", "sachet", "ampoule", "blister")
                      if re.search(r"\b" + kind + r"s?\b", value)), None)
    if container is None:
        return None
    units = tuple((format(Decimal(n).normalize(), "f"), unit) for n, unit in
                  re.findall(r"(\d+(?:\.\d+)?)\s*(ml|mg|g|l)\b", value))
    return container, numbers, units


def matching_key(record: dict):
    key = (normalize(record["brand_name"]), dose_key(record.get("dosage")),
           form_key(record.get("form")), presentation_key(record.get("presentation")))
    return key if all(part is not None and part != "" for part in key) else None


def snapshot_records(directory: Path = SNAPSHOT) -> tuple[list[dict], dict]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise ValueError("The fresh AMMPS snapshot is not complete; existing dataset is preserved")
    paths = sorted((p for p in directory.glob("page_*.json") if re.fullmatch(r"page_\d+\.json", p.name)),
                   key=lambda p: int(p.stem.split("_")[1]))
    if [int(p.stem.split("_")[1]) for p in paths] != list(range(1, manifest["expected_pages"] + 1)):
        raise ValueError("Missing or extra snapshot pages")
    records, ids = [], set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        page = int(path.stem.split("_")[1])
        if (payload["source_page"] != page or payload["record_count"] != len(payload["records"])
                or payload["advertised_total"] != manifest["advertised_total"]):
            raise ValueError(f"Invalid snapshot payload: {path.name}")
        link_soup = None
        for raw in payload["records"]:
            record_id = raw["source_record_id"]
            if record_id in ids:
                raise ValueError(f"Duplicate official record: {record_id}")
            ids.add(record_id)
            record = process_record({**raw, "source": "AMMPS", "source_page": page,
                                     "source_url": payload["source_url"]})
            details = raw["details"]
            reference = normalize_text(details["Lien RCP / NAF"])
            if reference and reference != "-":
                if link_soup is None:
                    link_soup = BeautifulSoup(path.with_suffix(".html").read_text(encoding="utf-8"), "html.parser")
                modal = link_soup.find(id=f"medicamentModal{record_id}")
                if modal is not None:
                    for item in modal.select(".ammps-modal-item"):
                        label = item.select_one(".ammps-modal-label")
                        anchor = item.select_one(".ammps-modal-value a[href]")
                        if label and label.get_text(" ", strip=True) == "Lien RCP / NAF" and anchor:
                            candidate = urljoin(payload["source_url"], anchor["href"])
                            if candidate.startswith("https://"):
                                reference = candidate
            record.update({
                "authorization_status": normalize_text(details["Statut AMM"]),
                "therapeutic_class": normalize_text(details["Classe thérapeutique"]),
                "pp_gn_raw": normalize_text(details["PP / GN"]),
                "pfht_price_mad": normalize_price(details["PFHT"]),
                "vat_raw": normalize_text(details["TVA"]),
                "rcp_naf_reference": None if reference == "-" else reference,
                "detailed_source_url": payload["source_url"],
                "source_fetched_at_utc": payload["fetched_at_utc"],
                "atc_code": None, "reimbursement_status": None,
                "source_observations": [], "data_conflicts": [],
            })
            records.append(record)
    if len(records) != manifest["advertised_total"]:
        raise ValueError("Official dataset count does not equal the source-advertised count")
    return records, manifest


def link_secondary(records: list[dict], observations: list[dict]) -> dict:
    index = defaultdict(list)
    for record in records:
        key = matching_key(record)
        if key:
            index[key].append(record)
    matches, unmatched, ambiguous, conflicts = [], [], [], []
    for observed in observations:
        if observed.get("product_nature") and normalize(observed["product_nature"]) != "medicament":
            unmatched.append({"source": observed["source"], "source_url": observed["source_url"],
                              "reason": "Non-medication product; not merged into the official drug catalogue"})
            continue
        key = matching_key(observed)
        candidates = index.get(key, []) if key else []
        if len(candidates) != 1:
            entry = {"source": observed["source"], "source_url": observed["source_url"],
                     "candidate_ids": [r["source_record_id"] for r in candidates],
                     "reason": "Incomplete or unmatched presentation" if not candidates else "Ambiguous presentation"}
            (ambiguous if candidates else unmatched).append(entry)
            continue
        target = candidates[0]
        observation = {field: observed.get(field) for field in (
            "source", "source_record_id", "source_url", "fetched_at_utc", "source_updated_at_raw",
            "atc_code", "reimbursement_raw", "ppv_price_mad", "hospital_price_mad", "commercialization_status",
        )}
        target["source_observations"].append(observation)
        matches.append({"source": observed["source"], "source_url": observed["source_url"],
                        "ammps_record_id": target["source_record_id"]})
        for field in ("ppv_price_mad", "hospital_price_mad", "commercialization_status"):
            value, primary = observed.get(field), target[field]
            if value is None or primary is None:
                continue
            same = normalize(value) == normalize(primary) if isinstance(value, str) else value == primary
            if not same:
                conflict = {"field": field, "reference_value": primary, "observed_value": value,
                            "source": observed["source"], "source_url": observed["source_url"]}
                target["data_conflicts"].append(conflict)
                conflicts.append({"ammps_record_id": target["source_record_id"], **conflict})
    for target in records:
        codes = {o["atc_code"] for o in target["source_observations"]
                 if o["atc_code"] and ATC_PATTERN.fullmatch(o["atc_code"])}
        target["atc_code"] = next(iter(codes)) if len(codes) == 1 else None
        reimbursement = {normalize(o["reimbursement_raw"]) for o in target["source_observations"]
                         if o["reimbursement_raw"] and normalize(o["reimbursement_raw"]) in {"oui", "non"}}
        target["reimbursement_status"] = ({"oui": "yes", "non": "no"}[next(iter(reimbursement))]
                                          if len(reimbursement) == 1 else None)
        for field, values in (("atc_code", codes), ("reimbursement_status", reimbursement)):
            if len(values) > 1:
                conflict = {"ammps_record_id": target["source_record_id"], "field": field,
                            "values": sorted(values), "reason": "Secondary sources disagree; canonical value remains unknown"}
                conflicts.append(conflict)
                for observation in target["source_observations"]:
                    value = observation["atc_code"] if field == "atc_code" else observation["reimbursement_raw"]
                    if value is not None:
                        target["data_conflicts"].append({
                            "field": field, "reference_value": None, "observed_value": value,
                            "source": observation["source"], "source_url": observation["source_url"],
                        })
    return {"matched_observations": matches, "unmatched_observations": unmatched,
            "ambiguous_observations": ambiguous, "conflicts": conflicts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-directory", type=Path, default=SNAPSHOT)
    args = parser.parse_args()
    records, manifest = snapshot_records(args.snapshot_directory)
    observations = []
    counts = {}
    for source in ("medicament", "saydalia"):
        path = ROOT / f"data/processed/{source}_medications.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows:
            raise ValueError(f"Secondary source sample is empty: {source}")
        observations.extend(rows)
        counts[source] = len(rows)
    matching = link_secondary(records, observations)
    # Validate everything before replacing the dataset used by the API.
    validated = [Medication.model_validate(r).model_dump(mode="json") for r in records]
    quality = validate_records(validated)
    if not quality["passed"]:
        raise ValueError("Built catalogue failed quality validation")
    if DATASET.exists():
        previous = DATASET.read_bytes()
        previous_count = sum(bool(line.strip()) for line in previous.splitlines())
        digest = hashlib.sha256(previous).hexdigest()[:12]
        archive = ROOT / f"data/processed/archive/ammps_medications_enriched_{previous_count}_{digest}.jsonl"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(DATASET, archive)
    write_jsonl(DATASET, validated)
    write_json(ROOT / "reports/ammps_quality.json", quality)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "official_snapshot_complete": True, "official_records": len(records),
        "official_pages": manifest["expected_pages"], "secondary_scope": "bounded_samples",
        "secondary_records": counts,
        "matching_policy": "Unique exact normalized brand, strength, form and package signature; no fuzzy auto-merge",
        "price_status_policy": "AMMPS retained; differing secondary observations preserved and flagged",
        "records_with_secondary_sources": sum(bool(r["source_observations"]) for r in records),
        "records_with_atc": sum(r["atc_code"] is not None for r in records),
        "records_with_reimbursement": sum(r["reimbursement_status"] is not None for r in records),
        "matched_by_source": dict(Counter(m["source"] for m in matching["matched_observations"])),
        "invalid_secondary_atc_codes": [
            {"source": row["source"], "source_url": row["source_url"], "atc_code": row["atc_code"]}
            for row in observations if row.get("atc_code") and not ATC_PATTERN.fullmatch(row["atc_code"])
        ],
        **matching,
    }
    write_json(ROOT / "reports/reference_data_quality.json", report)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"matched_observations", "unmatched_observations", "ambiguous_observations", "conflicts"}},
                     ensure_ascii=True, indent=2))
    print(f"Conflicts flagged: {len(matching['conflicts'])}; quality: PASS")


if __name__ == "__main__":
    main()
