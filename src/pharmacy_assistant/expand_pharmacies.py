"""Stage a configurable city's public pharmacy map grid, with explicit gaps."""

import argparse
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

from pharmacy_assistant.collect_rabat_pharmacies import API_URL, normalize_pharmacies
from pharmacy_assistant.collection_http import CollectionBudgetReached, SourceClient, write_json
from pharmacy_assistant.expand_medications import safe_failure
from pharmacy_assistant.supplementary_sources import write_jsonl

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "data/collection/cities.json"
DEFAULT_DIRECTORY = ROOT / "data/staging/pharmacy_expansion_v1"


def grid_points(bounds: list[float], step: float) -> list[tuple[float, float]]:
    south, north, west, east = bounds
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180 and step > 0):
        raise ValueError("Invalid city search bounds or grid spacing")
    # Round division noise so an exact boundary does not create a duplicate row.
    rows = math.ceil(round((north - south) / step, 9))
    columns = math.ceil(round((east - west) / step, 9))
    if (rows + 1) * (columns + 1) > 10000:
        raise ValueError("City grid exceeds 10,000 points; review configuration")
    return [(round(min(south + row * step, north), 6),
             round(min(west + column * step, east), 6))
            for row in range(rows + 1) for column in range(columns + 1)]


def name_key(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(c))).split())


def phone_key(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00212"):
        digits = "0" + digits[5:]
    elif digits.startswith("212"):
        digits = "0" + digits[3:]
    return digits if re.fullmatch(r"0[5-8]\d{8}", digits) else None


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a, b = math.radians(lat1), math.radians(lat2)
    value = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(
        math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(value, 1)))


def refinement_origins(origin, step, bounds):
    south, north, west, east = bounds
    lat, lon = origin
    return [(round(lat + y * step / 4, 6), round(lon + x * step / 4, 6))
            for y in (-1, 1) for x in (-1, 1)
            if south <= lat + y * step / 4 <= north and west <= lon + x * step / 4 <= east]


def directory_quality(records: list[dict]) -> dict:
    duplicates = []
    by_identity = {}
    for record in records:
        # Review candidates across IDs; never collapse distinct pharmacies by name alone.
        key = (name_key(record["name"]), phone_key(record["phone"]))
        if key[1]:
            by_identity.setdefault(key, []).append(record["pharmacy_id"])
    duplicates = [ids for ids in by_identity.values() if len(ids) > 1]
    return {
        "records": len(records), "unique_ids": len({r["pharmacy_id"] for r in records}),
        "missing_phone": sum(not r["phone"] for r in records),
        "invalid_phone_format": sum(bool(r["phone"]) and phone_key(r["phone"]) is None for r in records),
        "missing_address": sum(not r["address"] for r in records),
        "possible_duplicate_id_groups": duplicates,
        "verified_duty_records": 0, "verified_opening_hours": 0, "stock_available": False,
    }


def collect(city_key: str = "rabat", directory: Path = DEFAULT_DIRECTORY,
            config_path: Path = DEFAULT_CONFIG, max_requests: int | None = None,
            delay: float = 2) -> dict:
    config_bytes = config_path.read_bytes()
    configs = json.loads(config_bytes)
    if city_key not in configs or not re.fullmatch(r"[a-z0-9_-]+", city_key):
        raise ValueError("City must be present in the reviewed city configuration")
    config = configs[city_key]
    city = config["city"]
    points = grid_points(config["bounds"], config["grid_step_degrees"])
    base_point_count = len(points)
    point_depths = [0] * base_point_count
    planned_origins = set(points)
    directory = directory / city_key
    directory.mkdir(parents=True, exist_ok=True)
    state = {
        "source": "saydalia.ma", "city": city, "scope": "systematic_city_map_grid",
        "collector_version": "grid-refine-v2", "base_grid_points": base_point_count,
        "configuration": config, "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "search_points_planned": len(points), "point_results": [], "errors": [],
        "record_conflicts": [], "collection_complete": False,
        "complete_city_directory": False, "staging_only": True,
        "coverage_limitation": "A completed grid is not proof of complete city coverage. "
                               "The source supplies no authoritative total or pagination.",
        "stop_reason": "running",
    }
    # A changed config cannot quietly reuse an incompatible coordinate cache.
    config_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    by_id, duty = {}, {}
    previous_manifest = directory / "manifest.json"
    if previous_manifest.exists():
        previous = json.loads(previous_manifest.read_text(encoding="utf-8"))
        if previous.get("configuration") != config:
            raise ValueError("Use a new staging directory when changing city configuration")
        for path, target, key in ((directory / "pharmacies.jsonl", by_id, "pharmacy_id"),
                                  (directory / "duty_observations.jsonl", duty, "pharmacy_id")):
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        record = json.loads(line)
                        target[record[key]] = record
        if set(by_id) != set(duty):
            raise ValueError("Previous pharmacy records and observations are inconsistent")
    with SourceClient("https://saydalia.ma", directory / "raw" / config_id,
                      delay=delay, max_requests=max_requests) as client:
        def checkpoint():
            records = sorted(by_id.values(), key=lambda r: r["pharmacy_id"])
            write_jsonl(directory / "pharmacies.jsonl", records)
            write_jsonl(directory / "duty_observations.jsonl", [duty[r["pharmacy_id"]] for r in records])
            state.update(
                updated_at_utc=datetime.now(timezone.utc).isoformat(),
                search_points_planned=len(points),
                refinement_points_planned=len(points) - base_point_count,
                search_points_completed=len(state["point_results"]),
                network_requests_this_run=client.request_count,
                possibly_truncated_points=sum(p["possibly_truncated"] for p in state["point_results"]),
                unresolved_dense_points=sum(p["dense_cell_needs_refinement"] and
                    p["refinement_depth"] >= config.get("max_refinement_depth", 1)
                    for p in state["point_results"]),
                quality=directory_quality(records), record_count=len(records))
            write_json(directory / "manifest.json", state)

        try:
            home, _ = client.get("https://saydalia.ma/fr/", "home")
            match = re.search(r"var\s+nearestSaydaliaData\s*=\s*(\{[^;]+\})", home)
            if match is None:
                raise ValueError("Public browser map configuration missing")
            token = json.loads(match.group(1))["api_key"]
            consecutive_failures = 0
            seen_ids = set()
            for index, (lat, lon) in enumerate(points):
                try:
                    cache_name = (f"point_{index:04d}" if index < base_point_count else
                                  f"refine_{index - base_point_count:04d}")
                    payload, meta = client.get(API_URL, cache_name, params={
                        "origin": f"{lat:.6f},{lon:.6f}",
                        "limit": config["requested_limit"], "api_key": token})
                    raw = json.loads(payload)
                    records, observations = normalize_pharmacies(
                        raw, meta, city=city, directory_scope="systematic_city_map_grid")
                    raw_ids = [r.get("id") for r in raw]
                    if len(set(raw_ids)) != len(raw_ids):
                        raise ValueError("Duplicate pharmacy IDs in one map response")
                    distances = [distance_km(lat, lon, float(r["lat"]), float(r["lng"])) for r in raw]
                    step = config["grid_step_degrees"] / (2 ** point_depths[index])
                    cell_radius = distance_km(lat, lon, lat + step / 2, lon + step / 2)
                    capped = len(raw) >= min(config["requested_limit"], config["observed_result_cap"])
                    needs_refinement = bool(records) and capped and max(distances, default=0) < cell_radius
                    if needs_refinement and point_depths[index] < config.get("max_refinement_depth", 1):
                        for origin in refinement_origins((lat, lon), step, config["bounds"]):
                            if origin not in planned_origins:
                                planned_origins.add(origin)
                                points.append(origin)
                                point_depths.append(point_depths[index] + 1)
                    added = 0
                    for record, observation in zip(records, observations):
                        identifier = record["pharmacy_id"]
                        seen_ids.add(identifier)
                        if identifier in by_id:
                            changed = [field for field in
                                       ("name", "city", "address", "phone", "latitude", "longitude")
                                       if record[field] != by_id[identifier][field]]
                            if changed:
                                state["record_conflicts"].append({"pharmacy_id": identifier,
                                    "point": index, "fields": changed, "observation": record})
                        else:
                            by_id[identifier], duty[identifier] = record, observation
                            added += 1
                    state["point_results"].append({
                        "index": index, "cache_name": cache_name,
                        "origin": [lat, lon], "raw_count": len(raw),
                        "city_records": len(records), "other_city_records": len(raw) - len(records),
                        "new_ids": added,
                        "possibly_truncated": capped, "refinement_depth": point_depths[index],
                        "outer_result_radius_km": round(max(distances, default=0), 4),
                        "grid_cell_radius_km": round(cell_radius, 4),
                        "dense_cell_needs_refinement": needs_refinement,
                        "distance_order_observed": all(distances[n] <= distances[n + 1] + 0.001
                                                       for n in range(len(distances) - 1)),
                        "fetched_at_utc": meta["fetched_at_utc"],
                    })
                    consecutive_failures = 0
                except CollectionBudgetReached:
                    raise
                except (ValueError, KeyError, TypeError, requests.RequestException) as error:
                    state["errors"].append({"point": index, **safe_failure(error)})
                    consecutive_failures += 1
                    if (isinstance(error, requests.HTTPError) and error.response is not None
                            and error.response.status_code in {401, 403, 429}):
                        state["stop_reason"] = "source_rejected_requests"
                        break
                    if consecutive_failures >= 3:
                        state["stop_reason"] = "consecutive_source_failures"
                        break
                if index % 10 == 0:
                    checkpoint()
                    print(f"{city}: {len(state['point_results'])}/{len(points)} points, "
                          f"{len(by_id)} unique pharmacies", flush=True)
            else:
                state["stop_reason"] = "finished" if not state["errors"] else "finished_with_errors"
            state["collection_complete"] = len(state["point_results"]) == len(points) and not state["errors"]
            if state["collection_complete"]:
                by_id = {key: record for key, record in by_id.items() if key in seen_ids}
        except CollectionBudgetReached:
            state["stop_reason"] = "request_budget_reached"
        except KeyboardInterrupt:
            state["stop_reason"] = "interrupted"
        except (ValueError, KeyError, requests.RequestException) as error:
            state["errors"].append({"phase": "discovery", **safe_failure(error)})
            state["stop_reason"] = "discovery_failed"
        finally:
            checkpoint()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="rabat")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--delay", type=float, default=2)
    args = parser.parse_args()
    if args.delay < 2 or (args.max_requests is not None and args.max_requests < 0):
        parser.error("Delay must be at least 2 seconds; request budget must be nonnegative")
    state = collect(args.city, args.directory, args.config, args.max_requests, args.delay)
    print(json.dumps({key: state.get(key) for key in
                      ("city", "record_count", "search_points_completed", "search_points_planned",
                       "possibly_truncated_points", "collection_complete", "stop_reason")}), flush=True)
    raise SystemExit(0 if state["collection_complete"] else 2)


if __name__ == "__main__":
    main()
