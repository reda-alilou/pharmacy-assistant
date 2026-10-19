"""Read-only Rabat sample; a directory match never implies stock or duty."""

from collections import defaultdict
from pathlib import Path

from pharmacy_assistant.catalog import ROOT
from pharmacy_assistant.chat_models import PharmacyResult
from pharmacy_assistant.collect_rabat_pharmacies import PharmacyRecord
from pharmacy_assistant.nlu_models import ExtractedEntities
from pharmacy_assistant.pharmacy_normalization import (
    AREA_ALIASES, area_term, contains_tokens, directory_term, pharmacy_name,
)


PHARMACIES = ROOT / "data/processed/pharmacies_rabat.jsonl"


class PharmacyDirectory:
    def __init__(self, records: list[PharmacyRecord]):
        if len({r.pharmacy_id for r in records}) != len(records):
            raise ValueError("Duplicate pharmacy IDs")
        if any(r.city != "Rabat" for r in records):
            raise ValueError("This directory is limited to Rabat")
        self.records = tuple(records)
        self.name_index = defaultdict(list)
        self.name_keys, self.area_keys = {}, {}
        for record in self.records:
            key = directory_term(record.name)
            self.name_index[key].append(record)
            self.name_keys[record.pharmacy_id] = key
            self.area_keys[record.pharmacy_id] = area_term(f"{record.name} {record.address or ''}")

    @classmethod
    def from_path(cls, path: Path = PHARMACIES):
        # A deployment without this optional sample can still serve medications.
        if not path.exists():
            return cls([])
        return cls([PharmacyRecord.model_validate_json(line)
                    for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])

    def search(self, entities: ExtractedEntities) -> PharmacyResult:
        city = entities.city or "Rabat"
        base = {"applied_city": city, "city_defaulted": entities.city is None}
        if directory_term(city) not in {"rabat", "الرباط", "رباط"}:
            return PharmacyResult(**base, status="outside_coverage", result_count=0, pharmacies=[])
        matches = list(self.records)
        method, alias = "browse", None
        if entities.pharmacy:
            term = pharmacy_name(entities.pharmacy)
            alias = term if term != directory_term(entities.pharmacy) else None
            exact = self.name_index.get(term, []) if term else []
            if exact:
                matches = list(exact)
                method = "reviewed_alias" if alias else "exact_name"
            else:
                matches = [r for r in matches if contains_tokens(self.name_keys[r.pharmacy_id], term)]
                method = "name_tokens"
        if entities.area:
            term = area_term(entities.area)
            matches = [r for r in matches if contains_tokens(self.area_keys[r.pharmacy_id], term)]
            if not entities.pharmacy:
                method = "area_filter"
        matches.sort(key=lambda r: (directory_term(r.name), r.pharmacy_id))
        status = "not_found" if not matches else "ambiguous" if entities.pharmacy and len(matches) > 1 else "matches"
        return PharmacyResult(**base, status=status, match_method=method, name_alias=alias,
                              result_count=len(matches), pharmacies=matches[:5], results_truncated=len(matches) > 5)
