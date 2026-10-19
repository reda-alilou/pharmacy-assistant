"""Read-only medication catalogue, loaded and indexed once per API startup."""

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from pharmacy_assistant.models import (
    Medication,
    MedicationSearchRequest,
    MedicationSearchResponse,
    MedicationSuggestion,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/processed/ammps_medications_enriched.jsonl"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def normalize_strength(text: str) -> str:
    value = normalize(text).replace(",", ".").replace("μ", "u")
    return re.sub(r"\s+", "", value)


def contains_strength(value: str, requested: str) -> bool:
    # Do not confuse 5 mg with 15 mg, 1.5 mg, or 5 mcg.
    needle = normalize_strength(requested)
    return re.search(
        r"(?<![\w.,])" + re.escape(needle) + r"(?![\w.,])",
        normalize_strength(value),
    ) is not None


def contains_presentation(value: str, requested: str) -> bool:
    # Numeric package filters must not turn a box of 20 into a box of 200.
    return re.search(
        r"(?<!\d)" + re.escape(normalize(requested)) + r"(?!\d)",
        normalize(value),
    ) is not None


class MedicationCatalog:
    def __init__(self, records: list[Medication], dataset_name: str):
        if not records:
            raise ValueError("Medication catalogue is empty")

        self.records = tuple(records)
        self.dataset_name = dataset_name
        self.by_id: dict[str, Medication] = {}
        self.name_index: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.display_names: dict[tuple[str, str], str] = {}

        for record in records:
            record_id = record.source_record_id
            if record_id in self.by_id:
                raise ValueError(f"Duplicate medication ID: {record_id}")
            self.by_id[record_id] = record
            for field in ("brand_name", "active_substance"):
                value = getattr(record, field)
                key = (field, normalize(value))
                self.name_index[key].append(record_id)
                self.display_names.setdefault(key, value)

        self.brand_count = len({normalize(r.brand_name) for r in records})

    @classmethod
    def from_path(cls, path: Path = DATASET) -> "MedicationCatalog":
        records = []
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if line.strip():
                    try:
                        records.append(Medication.model_validate_json(line))
                    except ValueError as error:
                        raise ValueError(
                            f"Invalid catalogue record at line {line_number}: {error}"
                        ) from error
        return cls(records, path.name)

    def get(self, record_id: str) -> Medication | None:
        return self.by_id.get(record_id)

    def _passes_filters(
        self, record: Medication, request: MedicationSearchRequest
    ) -> bool:
        return (
            (request.strength is None or contains_strength(record.dosage, request.strength))
            and (request.form is None or normalize(request.form) in normalize(record.form))
            and (
                request.presentation is None
                or contains_presentation(record.presentation, request.presentation)
            )
        )

    def _suggest(self, request: MedicationSearchRequest) -> list[MedicationSuggestion]:
        query = normalize(request.query)
        if len(query) < 3:
            return []

        candidates = []
        for key, ids in self.name_index.items():
            field, term = key
            if abs(len(term) - len(query)) > max(3, len(query) // 2):
                continue
            score = SequenceMatcher(None, query, term).ratio()
            if score < 0.75:
                continue
            matching_ids = [
                record_id for record_id in ids
                if self._passes_filters(self.by_id[record_id], request)
            ]
            if matching_ids:
                candidates.append(MedicationSuggestion(
                    term=self.display_names[key],
                    field=field,
                    similarity=round(score, 3),
                    medication_ids=matching_ids,
                ))

        return sorted(
            candidates, key=lambda suggestion: (-suggestion.similarity, suggestion.term)
        )[:5]

    def search(self, request: MedicationSearchRequest) -> MedicationSearchResponse:
        query = normalize(request.query)
        candidate_ids = {
            record_id
            for (_, term), ids in self.name_index.items()
            if query in term
            for record_id in ids
        }
        matches = [
            record for record in self.records
            if record.source_record_id in candidate_ids
            and self._passes_filters(record, request)
        ]

        # A known product with an unmatched filter is not a spelling mistake.
        suggestions = self._suggest(request) if not candidate_ids else []
        if matches:
            status = "matches"
            message = f"Found {len(matches)} matching presentation(s) in this partial catalogue."
        elif suggestions:
            status = "suggestions"
            message = (
                "No direct match in this partial catalogue. Review the spelling "
                "suggestions; no medication has been selected."
            )
        else:
            status = "not_found"
            message = (
                "No matching presentation found in this partial catalogue. "
                "This does not establish that the medication does not exist or is unavailable."
            )

        return MedicationSearchResponse(
            query=request.query,
            result_count=len(matches),
            medications=matches,
            status=status,
            message=message,
            suggestions=suggestions,
        )
