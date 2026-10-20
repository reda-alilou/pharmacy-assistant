from typing import Annotated
from fastapi import Depends, HTTPException, Request
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_contracts.errors import StorageUnavailable


def get_catalog(request: Request) -> MedicationCatalog:
    return request.app.state.catalog


Catalog = Annotated[MedicationCatalog, Depends(get_catalog)]


def conversation_store(request: Request):
    store = getattr(request.app.state, "conversations", None)
    if store is None:
        raise StorageUnavailable()
    return store


def bearer(authorization):
    if not authorization or not authorization.startswith("Bearer ") or not 20 <= len(authorization[7:]) <= 100:
        raise HTTPException(401, detail="A valid conversation bearer token is required.")
    return authorization[7:]
