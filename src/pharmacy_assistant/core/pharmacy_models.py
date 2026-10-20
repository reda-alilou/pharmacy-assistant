"""Pharmacy record shared by runtime lookup and offline imports."""

from pydantic import BaseModel, ConfigDict, Field


class PharmacyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pharmacy_id: str
    name: str = Field(min_length=1)
    city: str
    address: str | None
    phone: str | None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    opening_information: str | None = None
    source: str = "saydalia.ma"
    source_url: str
    source_request_url: str
    fetched_at_utc: str
    directory_scope: str = "partial_rabat_map_sample"
