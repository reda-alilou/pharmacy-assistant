from __future__ import annotations

import json
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from .config import MATCH_FIELDS
from .logging_config import get_logger
from .models import MedicationRecord
from .normalization import extract_dosage_terms, normalize_text

logger = get_logger("catalog")


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Catalog:
    records: tuple[MedicationRecord, ...]
    normalized: Mapping[str, tuple[str, ...]]
    dosage_terms: tuple[frozenset[str], ...]
    source_path: str
    duplicate_count: int = 0

    @property
    def size(self) -> int:
        return len(self.records)

    def field_values(self, field: str) -> tuple[str, ...]:
        return self.normalized[field]


def _read_catalog(path: Path) -> Catalog:
    started = perf_counter()
    records: list[MedicationRecord] = []
    seen_ids: set[str] = set()
    duplicate_count = 0
    logger.info(
        "Reading catalogue from %s (%.1f MB)",
        path,
        path.stat().st_size / 1_000_000,
    )

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CatalogError(
                    f"Invalid JSON on line {line_number} of {path}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise CatalogError(
                    f"Line {line_number} of {path} is not a JSON object."
                )

            record = MedicationRecord.from_mapping(row)
            if not record.source_record_id:
                raise CatalogError(
                    f"Missing source_record_id on line {line_number} of {path}."
                )
            if record.source_record_id in seen_ids:
                duplicate_count += 1
                logger.warning(
                    "Duplicate source_record_id %r on line %d; "
                    "keeping the first occurrence.",
                    record.source_record_id,
                    line_number,
                )
                warnings.warn(
                    "Duplicate source_record_id "
                    f"{record.source_record_id!r} on line {line_number}; "
                    "keeping the first occurrence.",
                    stacklevel=2,
                )
                continue

            seen_ids.add(record.source_record_id)
            records.append(record)

    if not records:
        raise CatalogError(f"No medication records found in {path}.")

    normalized = {
        field: tuple(normalize_text(getattr(record, field)) for record in records)
        for field in MATCH_FIELDS
    }
    dosage_terms = tuple(
        extract_dosage_terms(record.dosage) for record in records
    )

    elapsed_ms = (perf_counter() - started) * 1000
    logger.info(
        "Catalogue parsed: %d records, %d duplicate(s) skipped, %.0f ms",
        len(records),
        duplicate_count,
        elapsed_ms,
    )

    return Catalog(
        records=tuple(records),
        normalized=normalized,
        dosage_terms=dosage_terms,
        source_path=str(path),
        duplicate_count=duplicate_count,
    )


@lru_cache(maxsize=4)
def _load_catalog_cached(
    path_str: str, mtime_ns: int, size: int
) -> Catalog:
    del mtime_ns, size
    return _read_catalog(Path(path_str))


def load_catalog(path: str | Path) -> Catalog:
    catalog_path = Path(path).expanduser().resolve()
    logger.info("Loading catalogue from %s", catalog_path)
    if not catalog_path.exists():
        logger.error("Catalogue file not found: %s", catalog_path)
        raise FileNotFoundError(f"Catalog file not found: {catalog_path}")
    if not catalog_path.is_file():
        logger.error("Catalogue path is not a file: %s", catalog_path)
        raise CatalogError(f"Catalog path is not a file: {catalog_path}")

    stat = catalog_path.stat()
    try:
        catalog = _load_catalog_cached(
            str(catalog_path), stat.st_mtime_ns, stat.st_size
        )
    except Exception:
        logger.exception("Failed to load catalogue from %s", catalog_path)
        raise

    logger.info(
        "Catalogue ready: %d records from %s",
        catalog.size,
        catalog_path,
    )
    return catalog
