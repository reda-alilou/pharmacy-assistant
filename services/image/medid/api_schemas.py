from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .config import MATCH_FIELDS, ScoringMode
from .models import (
    IdentificationResult,
    MatchResult,
    MedicationRecord,
    OCRResult,
    WorkflowEvent,
)


class IdentifyOptions(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=50)
    min_score: float | None = Field(default=None, ge=0.0, le=100.0)
    scoring_mode: ScoringMode | None = None
    group_presentations: bool | None = None
    weights: dict[str, float] | None = None
    ocr_min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TextIdentifyRequest(IdentifyOptions):
    text: str = Field(min_length=1, max_length=4000)


class MedicationOut(BaseModel):
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


class MatchOut(BaseModel):
    record: MedicationOut
    score: float
    field_scores: dict[str, float]
    variants: list[MedicationOut]
    variant_count: int


class OCRTokenOut(BaseModel):
    text: str
    confidence: float
    bbox: list[list[float]] | None = None


class OCROut(BaseModel):
    text: str
    tokens: list[OCRTokenOut]
    languages: list[str]
    width: int
    height: int


class WorkflowEventOut(BaseModel):
    step: str
    message: str
    duration_ms: float | None = None
    timestamp: str


class IdentificationOut(BaseModel):
    request_id: str
    query: str
    matches: list[MatchOut]
    ocr: OCROut | None = None
    catalog_size: int
    elapsed_ms: float
    scoring_mode: str
    grouped: bool
    workflow: list[WorkflowEventOut]


class CatalogStatsOut(BaseModel):
    records: int
    unique_brands: int
    presentation_groups: int
    duplicate_ids: int
    source_path: str
    source_size_bytes: int
    modified_at: str
    match_fields: list[str]


class HealthOut(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    catalog_size: int
    ocr_languages: list[str]
    use_gpu: bool
    ocr_min_confidence: float


class ServiceInfoOut(BaseModel):
    name: str
    version: str
    docs_url: str
    endpoints: list[str]


def medication_out(record: MedicationRecord) -> MedicationOut:
    return MedicationOut(
        source_record_id=record.source_record_id,
        brand_name=record.brand_name,
        active_substance=record.active_substance,
        epi=record.epi,
        dosage=record.dosage,
        form=record.form,
        presentation=record.presentation,
        commercialization_status=record.commercialization_status,
        ppv_price_mad=record.ppv_price_mad,
        hospital_price_mad=record.hospital_price_mad,
        source=record.source,
        source_page=record.source_page,
        source_url=record.source_url,
    )


def match_out(match: MatchResult) -> MatchOut:
    return MatchOut(
        record=medication_out(match.record),
        score=round(match.score, 2),
        field_scores={
            field: round(score, 2)
            for field, score in match.field_scores.items()
        },
        variants=[
            medication_out(variant)
            for variant in match.presentation_variants
        ],
        variant_count=match.variant_count,
    )


def ocr_out(ocr: OCRResult | None) -> OCROut | None:
    if ocr is None:
        return None
    return OCROut(
        text=ocr.text,
        tokens=[
            OCRTokenOut(
                text=token.text,
                confidence=round(token.confidence, 4),
                bbox=(
                    [[float(x), float(y)] for x, y in token.bbox]
                    if token.bbox
                    else None
                ),
            )
            for token in ocr.tokens
        ],
        languages=list(ocr.languages),
        width=ocr.width,
        height=ocr.height,
    )


def workflow_out(event: WorkflowEvent) -> WorkflowEventOut:
    return WorkflowEventOut(
        step=event.step,
        message=event.message,
        duration_ms=(
            round(event.duration_ms, 2)
            if event.duration_ms is not None
            else None
        ),
        timestamp=event.timestamp,
    )


def identification_out(result: IdentificationResult) -> IdentificationOut:
    if not result.request_id:
        raise ValueError("Identification result has no request_id.")
    return IdentificationOut(
        request_id=result.request_id,
        query=result.query,
        matches=[match_out(match) for match in result.matches],
        ocr=ocr_out(result.ocr),
        catalog_size=result.catalog_size,
        elapsed_ms=round(result.elapsed_ms, 2),
        scoring_mode=result.scoring_mode,
        grouped=result.grouped,
        workflow=[workflow_out(event) for event in result.workflow],
    )


def validate_weights(weights: dict[str, float] | None) -> None:
    if weights is None:
        return
    unknown = set(weights) - set(MATCH_FIELDS)
    if unknown:
        raise ValueError(
            "Unknown weight field(s): " + ", ".join(sorted(unknown))
        )
    if any(value < 0 for value in weights.values()):
        raise ValueError("Matching weights must be non-negative.")
    if sum(weights.values()) <= 0:
        raise ValueError("At least one matching weight must be positive.")
