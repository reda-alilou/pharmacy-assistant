"""Collect a partial Rabat directory from Saydalia's public map requests."""

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pharmacy_assistant.collection_http import SourceClient, write_json
from pharmacy_assistant.supplementary_sources import text, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "data/raw/saydalia_rabat"
API_URL = "https://saydalia.ma/api/siteweb_api.php"
# Approximate map-search points, not user locations or pharmacy coordinates.
SEARCH_POINTS = {"center": "34.0209,-6.8416", "south": "33.9949,-6.8499",
                 "southwest": "33.9617,-6.8750"}


class PharmacyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pharmacy_id: str
    name: str = Field(min_length=1)
    city: str
    address: str | None
    phone: str | None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    opening_information: str | None = None
    source: str = "saydalia.ma"
    source_url: str
    source_request_url: str
    fetched_at_utc: str
    directory_scope: str = "partial_rabat_map_sample"


def normalize_pharmacies(raw: list[dict], meta: dict, city: str = "Rabat",
                        directory_scope: str = "partial_rabat_map_sample") -> tuple[list[dict], list[dict]]:
    if not isinstance(raw, list):
        raise ValueError("Saydalia pharmacy response must be a list")
    records, observations = [], []
    for item in raw:
        if (text(item.get("Ville")) or "").casefold() != city.casefold():
            continue
        identifier = str(item.get("id", ""))
        if not identifier.isdigit():
            raise ValueError("Missing pharmacy identifier")
        phone = text(item.get("Phone"))
        record = PharmacyRecord(
            pharmacy_id=f"saydalia:{identifier}", name=text(item.get("title")),
            city=city, address=text(item.get("address")), phone=phone,
            latitude=float(item["lat"]), longitude=float(item["lng"]),
            source_url="https://saydalia.ma/fr/", source_request_url=meta["source_url"],
            fetched_at_utc=meta["fetched_at_utc"],
            directory_scope=directory_scope,
        ).model_dump(mode="json")
        records.append(record)
        observations.append({
            "pharmacy_id": record["pharmacy_id"], "source": "saydalia.ma",
            "source_url": "https://saydalia.ma/fr/", "source_request_url": meta["source_url"],
            "fetched_at_utc": meta["fetched_at_utc"],
            "observed_garde_raw": item.get("garde"), "observed_special_raw": item.get("special"),
            "observed_marker_url": item.get("marker"),
            "valid_from": None, "valid_until": None, "duty_verified": False,
            "reason": "No dated duty interval is supplied in the map response",
        })
    return records, observations


def main():
    by_id, duty = {}, {}
    with SourceClient("https://saydalia.ma", DIRECTORY) as client:
        home, _ = client.get("https://saydalia.ma/fr/", "home")
        match = re.search(r"var\s+nearestSaydaliaData\s*=\s*(\{[^;]+\})", home)
        if match is None:
            raise ValueError("Public map request configuration was not found")
        # This is the site's public browser-map token, never the user's Groq key.
        token = json.loads(match.group(1))["api_key"]
        for name, origin in SEARCH_POINTS.items():
            payload, meta = client.get(API_URL, f"rabat_{name}",
                                       params={"origin": origin, "limit": 35, "api_key": token})
            records, observations = normalize_pharmacies(json.loads(payload), meta)
            for record, observation in zip(records, observations):
                identifier = record["pharmacy_id"]
                if identifier in by_id:
                    for field in ("name", "city", "address", "phone", "latitude", "longitude"):
                        if record[field] != by_id[identifier][field]:
                            raise ValueError(f"Conflicting pharmacy data for {identifier}: {field}")
                else:
                    by_id[identifier] = record
                    duty[identifier] = observation
            print(f"Rabat map point {name}: {len(records)} Rabat records, {len(by_id)} unique", flush=True)
    if not by_id:
        raise ValueError("No Rabat pharmacies found")
    write_jsonl(ROOT / "data/processed/pharmacies_rabat.jsonl", list(by_id.values()))
    write_jsonl(ROOT / "data/processed/pharmacy_duty_observations.jsonl", list(duty.values()))
    write_json(DIRECTORY / "manifest.json", {
        "source": "saydalia.ma", "city": "Rabat", "scope": "partial_map_sample",
        "search_points": SEARCH_POINTS, "unique_pharmacies": len(by_id),
        "verified_duty_records": 0, "complete_city_directory": False,
    })
    write_json(ROOT / "reports/pharmacies_rabat_quality.json", {
        "source": "saydalia.ma", "city": "Rabat", "records": len(by_id),
        "unique_ids": len(by_id), "missing_phone": sum(not r["phone"] for r in by_id.values()),
        "missing_address": sum(not r["address"] for r in by_id.values()),
        "undated_duty_observations": len(duty), "verified_duty_records": 0,
        "scope": "partial_map_sample", "passed": bool(by_id),
    })


if __name__ == "__main__":
    main()
