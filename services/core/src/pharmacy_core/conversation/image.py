"""Image-identification contracts and deterministic response construction.

This module owns no HTTP client. The remote OCR/matching service is reached
through the protocol below, implemented in ``pharmacy_core.clients.medid``.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from pharmacy_contracts.interpretation import (
    ExtractedEntities,
    InferenceMetadata,
    Interpretation,
    MedicationMention,
    TokenUsage,
)
from pharmacy_core.conversation.models import (
    ChatResponse,
    ConversationContext,
    MedicationResult,
    SourceInfo,
)
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.medications.models import Medication
from pharmacy_core.medications.pricing import price_amount


IMAGE_MESSAGE = "Photo de médicament envoyée"
MAX_IMAGE_BYTES = 15_000_000


@dataclass(frozen=True)
class ImageCandidate:
    source_record_id: str
    score: float
    field_scores: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageIdentification:
    query: str
    candidates: tuple[ImageCandidate, ...] = ()
    elapsed_ms: float = 0.0


class ImageIdentifier(Protocol):
    async def identify(
        self, image_bytes: bytes, *, content_type: str = "image/jpeg"
    ) -> ImageIdentification: ...


def image_interpretation(query: str, count: int) -> Interpretation:
    mentions = [
        MedicationMention(
            name=(query.strip()[:200] or "Photo de médicament"),
            strength=None,
            quantity=None,
            form=None,
            presentation=None,
        )
        for _ in range(count)
    ]
    return Interpretation(
        language="fr",
        reply_language="fr",
        reply_script="latin",
        intents=["medication_information", "availability"],
        entities=ExtractedEntities(
            medications=mentions,
            pharmacy=None,
            city=None,
            area=None,
            date=None,
            time=None,
            symptom=None,
        ),
    )


def image_answer(identification: ImageIdentification, records: list[tuple[ImageCandidate, Medication]]) -> str:
    query = identification.query.strip()
    if not query:
        return (
            "Aucun texte n'a été détecté dans la photo. "
            "Essayez une photo plus nette, rapprochée et bien éclairée."
        )
    paragraphs = [f"Texte détecté dans l'image : « {query[:300]} »."]
    if not records:
        paragraphs.append(
            "Aucun médicament du catalogue partiel ne correspond à ce texte. "
            "Vérifiez la photo ou reformulez le nom."
        )
        return "\n\n".join(paragraphs)
    paragraphs.append(f"Principaux candidats ({len(records)}) :")
    for rank, (candidate, record) in enumerate(records, 1):
        price = (
            "Prix public non renseigné."
            if record.ppv_price_mad is None
            else f"Prix public enregistré : {price_amount(record.ppv_price_mad):.2f} MAD."
        )
        paragraphs.append(
            f"{rank}. {record.brand_name} — {record.dosage} — {record.form} — "
            f"{record.presentation}. {price} Commercialisation : "
            f"{record.commercialization_status}. Correspondance : "
            f"{candidate.score:.1f} %."
        )
    paragraphs.append(
        "Ces candidats sont classés par similarité avec le texte reconnu. "
        "Vérifiez la boîte et les informations enregistrées avant toute décision."
    )
    return "\n\n".join(paragraphs)


def build_image_response(
    identification: ImageIdentification,
    catalog: MedicationCatalog,
    *,
    session_id: str | None = None,
    session_expires_at_utc: str | None = None,
) -> ChatResponse:
    records: list[tuple[ImageCandidate, Medication]] = []
    seen: set[str] = set()
    for candidate in identification.candidates:
        if len(records) >= 10:
            break
        record = catalog.get(candidate.source_record_id)
        if record is None or record.source_record_id in seen:
            continue
        seen.add(record.source_record_id)
        records.append((candidate, record))

    interpretation = image_interpretation(identification.query, len(records))
    results = [
        MedicationResult(
            mention_index=index,
            mention=interpretation.entities.medications[index],
            status="resolved",
            match_method="fuzzy",
            medication=record,
        )
        for index, (_, record) in enumerate(records)
    ]
    sources: dict[tuple[str, str, str | None], SourceInfo] = {}
    for _, record in records:
        key = (record.source, record.source_url, record.source_fetched_at_utc)
        if key not in sources:
            sources[key] = SourceInfo(
                source=record.source,
                url=record.source_url,
                fetched_at_utc=record.source_fetched_at_utc,
                record_ids=[],
            )
        if record.source_record_id not in sources[key].record_ids:
            sources[key].record_ids.append(record.source_record_id)

    model = "medid-ocr-rapidfuzz"
    return ChatResponse(
        status="answered",
        interpretation=interpretation,
        medications=results,
        pharmacy=None,
        answer=image_answer(identification, records),
        sources=list(sources.values()),
        inference=InferenceMetadata(
            provider="local",
            output_mode="json_schema",
            requested_model=model,
            model=model,
            prompt_version="challenge-2-image-v1",
            latency_ms=max(0.0, identification.elapsed_ms),
            attempts=1,
            completion_id=None,
            usage=TokenUsage(
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
            ),
        ),
        inference_performed=False,
        continuation_id=None,
        continuation_expires_at_utc=None,
        session_id=session_id,
        session_expires_at_utc=session_expires_at_utc,
        context=ConversationContext(
            effective_interpretation=interpretation,
            action="independent",
        ),
    )
