"""Public contracts for grounded chat and explicit presentation selection."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from pharmacy_assistant.core.pharmacy_models import PharmacyRecord
from pharmacy_assistant.core.models import Medication
from pharmacy_assistant.contracts.nlu_models import (
    Interpretation, InterpretationRequest, InferenceMetadata, MedicationMention, PatientText,
)


class MedicationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mention_index: Annotated[int, Field(ge=0, le=9)]
    record_id: Annotated[str, Field(pattern=r"^\d+$")]


RefinementField = Literal["strength", "form", "presentation", "brand_name", "page"]


class MedicationRefinement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mention_index: Annotated[int, Field(ge=0, le=9)]
    field: RefinementField
    value: Annotated[str, Field(min_length=1, max_length=300)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{16,80}$")] | None = None
    text: PatientText | None = None
    session_id: Annotated[str, Field(min_length=20, max_length=100)] | None = None
    reference_index: Annotated[int, Field(ge=0, le=9)] | None = None
    continuation_id: Annotated[str, Field(min_length=20, max_length=100)] | None = None
    selections: Annotated[list[MedicationSelection], Field(max_length=10)] = Field(default_factory=list)
    refinements: Annotated[list[MedicationRefinement], Field(max_length=10)] = Field(default_factory=list)

    @model_validator(mode="after")
    def request_mode(self):
        if self.reference_index is not None:
            if self.session_id is None or self.text is not None or self.continuation_id or self.selections or self.refinements:
                raise ValueError("A reference choice requires only session_id and reference_index")
            return self
        if self.session_id is not None and (self.text is None or self.continuation_id or self.selections or self.refinements):
            raise ValueError("A session_id accompanies text or an offered reference choice")
        if self.continuation_id is None:
            if self.text is None or self.selections or self.refinements:
                raise ValueError("Send text, or a continuation_id with selections or offered refinements")
            InterpretationRequest(text=self.text)
        elif self.text is not None or bool(self.selections) == bool(self.refinements):
            raise ValueError("A continuation accepts either record selections or offered refinements")
        indexes = [selection.mention_index for selection in [*self.selections, *self.refinements]]
        if len(indexes) != len(set(indexes)):
            raise ValueError("Send at most one selection or refinement per medication mention")
        return self


class ClarificationOption(BaseModel):
    value: str
    candidate_count: int


class MedicationClarification(BaseModel):
    kind: Literal["refine_search", "correct_filters", "confirm_name", "choose_record"]
    field: Literal["strength", "form", "presentation", "brand_name"] | None = None
    options: list[ClarificationOption] = Field(default_factory=list)


MoneyAmount = Annotated[str, Field(pattern=r"^\d+\.\d{2}$")]


class MedicationPricing(BaseModel):
    status: Literal["not_requested", "calculated", "needs_quantity_clarification", "awaiting_medication", "price_unavailable"]
    requested_quantity: str | None = None
    presentation_count: int | None = None
    unit_price_mad: MoneyAmount | None = None
    total_price_mad: MoneyAmount | None = None
    currency: Literal["MAD"] = "MAD"
    basis: Literal["per_catalogue_presentation"] = "per_catalogue_presentation"
    clarification_reason: Literal["unclear_package_count", "container_mismatch"] | None = None


class OrderPricing(BaseModel):
    status: Literal["not_requested", "calculated", "incomplete"] = "not_requested"
    total_price_mad: MoneyAmount | None = None
    currency: Literal["MAD"] = "MAD"


class MedicationResult(BaseModel):
    mention_index: int
    mention: MedicationMention
    status: Literal["resolved", "ambiguous", "suggestions", "not_found", "missing_name", "filters_not_matched"]
    match_method: Literal["exact_brand", "exact_substance", "partial", "fuzzy", "user_selection", "context_record"] | None = None
    medication: Medication | None = None
    candidates: list[Medication] = Field(default_factory=list)
    candidate_count: int = 0
    candidates_truncated: bool = False
    stock_status: Literal["unknown"] = "unknown"
    clarification: MedicationClarification | None = None
    conflicting_filters: list[Literal["strength", "form", "presentation"]] = Field(default_factory=list)
    applied_refinements: dict[str, str] = Field(default_factory=dict)
    name_alias: str | None = None
    candidate_offset: int = 0
    next_candidate_offset: int | None = None
    pricing: MedicationPricing | None = None


class PharmacyResult(BaseModel):
    status: Literal["matches", "ambiguous", "not_found", "outside_coverage"]
    applied_city: str
    city_defaulted: bool
    result_count: int
    pharmacies: list[PharmacyRecord]
    scope: Literal["partial_rabat_directory"] = "partial_rabat_directory"
    ordering: Literal["name_not_distance"] = "name_not_distance"
    stock_status: Literal["unknown"] = "unknown"
    opening_hours_status: Literal["unknown"] = "unknown"
    duty_status: Literal["unverified"] = "unverified"
    match_method: Literal["exact_name", "reviewed_alias", "name_tokens", "area_filter", "browse"] | None = None
    name_alias: str | None = None
    results_truncated: bool = False


class SourceInfo(BaseModel):
    source: str
    url: str
    fetched_at_utc: str | None
    record_ids: list[str]


class ContextReferenceOption(BaseModel):
    mention_index: int
    medication: MedicationMention


class ConversationContext(BaseModel):
    effective_interpretation: Interpretation
    inherited_fields: list[str] = Field(default_factory=list)
    normalized_fields: list[str] = Field(default_factory=list)
    needs_reference: bool = False
    reference_options: list[ContextReferenceOption] = Field(default_factory=list)
    action: Literal["independent", "followup", "reference_choice", "ordinal_selection"] = "independent"


class ChatResponse(BaseModel):
    status: Literal["answered", "needs_clarification"]
    interpretation: Interpretation
    medications: list[MedicationResult]
    pharmacy: PharmacyResult | None
    answer: str
    sources: list[SourceInfo]
    inference: InferenceMetadata
    inference_performed: bool
    continuation_id: str | None
    continuation_expires_at_utc: str | None
    session_id: str | None = None
    session_expires_at_utc: str | None = None
    context: ConversationContext | None = None
    order_pricing: OrderPricing = Field(default_factory=OrderPricing)
    catalog_scope: Literal["partial"] = "partial"


class ConversationMessageView(BaseModel):
    sequence: Annotated[int, Field(ge=0)]
    role: Literal["user", "assistant"]
    outcome: Literal["pending", "answered", "failed"]
    text: str | None
    created_at_utc: str
    payload: dict[str, JsonValue] | None


class ConversationView(BaseModel):
    session_id: str
    expires_at_utc: str
    messages: list[ConversationMessageView]
    response: ChatResponse | None
