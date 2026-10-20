"""Structured interpretation contracts shared by the API, model, and evaluator."""

import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Intent = Literal[
    "price", "availability", "medication_information", "medication_request",
    "pharmacy_search", "pharmacy_contact", "opening_hours", "pharmacy_on_duty",
    "unsupported",
]
Span = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PatientText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


def normalize_span(text: str) -> str:
    # Compare Unicode-equivalent text and whitespace, preserving numbers,
    # accents and spelling. This deliberately does not transliterate or translate.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).casefold()


class InterpretationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: PatientText

    @field_validator("text")
    @classmethod
    def require_content(cls, value: str) -> str:
        if not any(not c.isspace() and not unicodedata.combining(c) for c in value):
            raise ValueError("Patient text must contain readable characters")
        return value


class ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MedicationMention(ExtractionModel):
    # Required nullable fields are intentional: strict provider schemas require
    # every property to be required, with null representing unknown information.
    name: Span | None
    strength: Span | None
    quantity: Span | None
    form: Span | None
    presentation: Span | None


class ExtractedEntities(ExtractionModel):
    medications: Annotated[list[MedicationMention], Field(max_length=10)]
    pharmacy: Span | None
    city: Span | None
    area: Span | None
    date: Span | None
    time: Span | None
    symptom: Span | None


class Interpretation(ExtractionModel):
    language: Literal["fr", "ar", "darija", "mixed", "unknown"]
    reply_language: Literal["fr", "ar", "darija"]
    reply_script: Literal["latin", "arabic"]
    intents: Annotated[list[Intent], Field(min_length=1, max_length=9)]
    entities: ExtractedEntities

    @field_validator("intents")
    @classmethod
    def unique_intents(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Intents must be unique")
        return values

    def validate_evidence(self, text: str) -> None:
        """Reject non-null entity values absent from the patient's message.

        This is an evidence check, not proof of semantic correctness. A model
        could still label a present word incorrectly; live evaluation checks that.
        """
        source = normalize_span(text)
        values = []
        for medication in self.entities.medications:
            fields = medication.model_dump()
            if not any(value is not None for value in fields.values()):
                raise ValueError("Empty medication mention")
            values.extend(fields.values())
        values.extend(
            value for key, value in self.entities.model_dump().items()
            if key != "medications"
        )
        if any(value is not None and normalize_span(value) not in source for value in values):
            raise ValueError("Extracted entity has no evidence in the patient message")


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prompt_tokens: Annotated[int, Field(ge=0)] | None
    completion_tokens: Annotated[int, Field(ge=0)] | None
    total_tokens: Annotated[int, Field(ge=0)] | None


class InferenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["groq", "opencode", "gemini"] = "groq"
    output_mode: Literal["json_schema", "json_object"] = "json_schema"
    requested_model: str
    model: str
    prompt_version: str
    latency_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    attempts: Annotated[int, Field(ge=1, le=2)]
    completion_id: str | None
    usage: TokenUsage
    usage_scope: Literal["successful_attempt"] = "successful_attempt"


class InterpretationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    interpretation: Interpretation
    metadata: InferenceMetadata


class InferenceErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str
    message: str
    retryable: bool
    retry_after_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None


class InferenceError(Exception):
    def __init__(self, code: str, message: str, status_code: int,
                 retryable: bool = False, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = InferenceErrorDetail(
            code=code, message=message, retryable=retryable,
            retry_after_seconds=retry_after_seconds,
        )


class InferenceErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    detail: InferenceErrorDetail
