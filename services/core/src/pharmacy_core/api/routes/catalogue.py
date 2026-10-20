from typing import Annotated

from fastapi import HTTPException, Query

from pharmacy_core.medications.models import Medication, MedicationSearchRequest, MedicationSearchResponse


from fastapi import APIRouter
from pharmacy_core.api.dependencies import Catalog

router = APIRouter()


@router.get("/medications/search", response_model=MedicationSearchResponse)
def search_medication_endpoint(
    filters: Annotated[MedicationSearchRequest, Query()], catalog: Catalog
):
    return catalog.search(filters)


@router.get("/medications/{record_id}", response_model=Medication)
def medication_by_id(record_id: str, catalog: Catalog):
    medication = catalog.get(record_id)
    if medication is None:
        raise HTTPException(
            status_code=404,
            detail=f"Medication record {record_id!r} was not found in this partial catalogue.",
        )
    return medication
