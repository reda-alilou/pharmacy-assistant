"""Validated catalogue records and public medication API contracts."""

import re
import unicodedata
from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator,
)


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SearchText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Price = Annotated[float, Field(ge=0, allow_inf_nan=False)]

BASIC_SOURCE = "https://www.ammps.gov.ma/recherche-medicaments"
DETAILED_SOURCE = (
    "https://www.ammps.gov.ma/basesdedonnes/liste_marocaine_des_medicaments"
)


class MedicationSourceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source: Literal["medicament.ma", "saydalia.ma"]
    source_record_id: Text
    source_url: Text
    fetched_at_utc: Text
    source_updated_at_raw: Text | None
    atc_code: Text | None
    reimbursement_raw: Text | None
    ppv_price_mad: Price | None
    hospital_price_mad: Price | None
    commercialization_status: Text | None


class MedicationDataConflict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    field: str
    reference_value: str | float | bool | None
    observed_value: str | float | bool | None
    source: Literal["medicament.ma", "saydalia.ma"]
    source_url: str


class Medication(BaseModel):
    """One presentation, including its recorded prices and provenance."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_record_id: Annotated[str, StringConstraints(pattern=r"^\d+$")]
    brand_name: Text
    active_substance: Text
    epi: Text
    dosage: Text
    form: Text
    presentation: Text
    commercialization_status: Text
    ppv_price_mad: Price | None
    hospital_price_mad: Price | None
    source: Literal["AMMPS"]
    source_page: Annotated[int, Field(gt=0)]
    source_url: str
    authorization_status: Text | None
    therapeutic_class: Text | None
    pp_gn_raw: Text | None
    pfht_price_mad: Price | None
    vat_raw: Text | None
    rcp_naf_reference: Text | None
    detailed_source_url: str | None
    source_fetched_at_utc: Text | None = None
    atc_code: Text | None = None
    reimbursement_status: Literal["yes", "no"] | None = None
    source_observations: list[MedicationSourceObservation] = Field(default_factory=list)
    data_conflicts: list[MedicationDataConflict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_provenance(self) -> "Medication":
        expected = {
            f"{base}?page={self.source_page}"
            for base in (BASIC_SOURCE, DETAILED_SOURCE)
        }
        if self.source_url not in expected:
            raise ValueError("source_url must identify the AMMPS listing and source_page")
        if self.detailed_source_url is not None:
            if not re.fullmatch(
                re.escape(DETAILED_SOURCE) + r"\?page=[1-9]\d*",
                self.detailed_source_url,
            ):
                raise ValueError("detailed_source_url must identify a detailed AMMPS page")
            # Overlapping records retain the original listing's page, which
            # need not equal the detailed listing's page.
            if self.source_url.startswith(DETAILED_SOURCE):
                if self.detailed_source_url != self.source_url:
                    raise ValueError("detailed source URLs disagree")
        return self


class MedicationSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchText
    strength: SearchText | None = None
    form: SearchText | None = None
    presentation: SearchText | None = None

    @field_validator("query", "strength", "form", "presentation")
    @classmethod
    def require_searchable_text(cls, value: str | None) -> str | None:
        if value is not None and not any(
            not char.isspace() and not unicodedata.combining(char)
            for char in unicodedata.normalize("NFKD", value)
        ):
            raise ValueError("Search text must contain searchable characters")
        return value


class MedicationSuggestion(BaseModel):
    term: str
    field: Literal["brand_name", "active_substance"]
    similarity: Annotated[float, Field(ge=0, le=1)]
    medication_ids: list[str]


class MedicationSearchResponse(BaseModel):
    query: str
    result_count: int
    medications: list[Medication]
    catalog_scope: Literal["partial"] = "partial"
    status: Literal["matches", "suggestions", "not_found"]
    message: str
    suggestions: list[MedicationSuggestion] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    catalog_scope: Literal["partial"] = "partial"
    catalog_dataset: str
    catalog_record_count: int
    catalog_brand_count: int
    interpretation_configured: bool = False
    interpretation_model: str | None = None
    interpretation_provider: Literal["groq", "opencode", "gemini"] | None = None
