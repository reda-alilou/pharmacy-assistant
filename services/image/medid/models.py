from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class MedicationRecord:
    source_record_id: str
    brand_name: str
    active_substance: str
    epi: str
    dosage: str
    form: str
    presentation: str
    commercialization_status: str
    ppv_price_mad: float | None
    hospital_price_mad: float | None
    source: str
    source_page: str
    source_url: str
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> MedicationRecord:
        return cls(
            source_record_id=_text(row.get("source_record_id")),
            brand_name=_text(row.get("brand_name")),
            active_substance=_text(row.get("active_substance")),
            epi=_text(row.get("epi")),
            dosage=_text(row.get("dosage")),
            form=_text(row.get("form")),
            presentation=_text(row.get("presentation")),
            commercialization_status=_text(
                row.get("commercialization_status")
            ),
            ppv_price_mad=_optional_float(row.get("ppv_price_mad")),
            hospital_price_mad=_optional_float(
                row.get("hospital_price_mad")
            ),
            source=_text(row.get("source")),
            source_page=_text(row.get("source_page")),
            source_url=_text(row.get("source_url")),
            raw=dict(row),
        )

    @property
    def display_label(self) -> str:
        label = " ".join(
            part for part in (self.brand_name, self.dosage) if part
        )
        return label or self.brand_name or self.source_record_id


@dataclass(frozen=True)
class OCRToken:
    text: str
    confidence: float
    bbox: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class OCRResult:
    text: str
    tokens: tuple[OCRToken, ...] = ()
    languages: tuple[str, ...] = ()
    width: int = 0
    height: int = 0

    @classmethod
    def empty(cls, languages: tuple[str, ...] = ()) -> OCRResult:
        return cls(text="", tokens=(), languages=languages)


@dataclass(frozen=True)
class MatchResult:
    record: MedicationRecord
    score: float
    field_scores: Mapping[str, float] = field(default_factory=dict)
    variants: tuple[MedicationRecord, ...] = ()

    @property
    def variant_count(self) -> int:
        return len(self.variants) if self.variants else 1

    @property
    def presentation_variants(self) -> tuple[MedicationRecord, ...]:
        if not self.variants:
            return (self.record,)
        return self.variants


@dataclass(frozen=True)
class WorkflowEvent:
    step: str
    message: str
    duration_ms: float | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


@dataclass(frozen=True)
class IdentificationResult:
    query: str
    matches: tuple[MatchResult, ...]
    ocr: OCRResult | None = None
    catalog_size: int = 0
    elapsed_ms: float = 0.0
    scoring_mode: str = "field_aware"
    grouped: bool = False
    request_id: str | None = None
    workflow: tuple[WorkflowEvent, ...] = ()

    @property
    def has_matches(self) -> bool:
        return bool(self.matches)
