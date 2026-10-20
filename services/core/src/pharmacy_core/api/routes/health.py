import asyncio

from fastapi import Request

from pharmacy_contracts.language import LanguageHealth
from pharmacy_core.medications.models import HealthResponse


from fastapi import APIRouter
from pharmacy_core.api.dependencies import Catalog

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, catalog: Catalog):
    check = getattr(request.app.state.interpreter, "health", None)
    language = await check() if check is not None else None
    if not isinstance(language, LanguageHealth):
        language = None
    return HealthResponse(
        language_service_status="available" if language else "unavailable",
        language_service_url=request.app.state.settings.language_service_url,
        storage_backend=request.app.state.settings.storage_backend,
        catalog_dataset=catalog.dataset_name,
        catalog_record_count=len(catalog.records),
        catalog_brand_count=catalog.brand_count,
        interpretation_configured=language.interpretation_configured if language else False,
        interpretation_model=language.interpretation_model if language else None,
        interpretation_provider=language.interpretation_provider if language else None,
    )


@router.get("/ready")
async def ready(request: Request):
    # Language is deliberately not a readiness dependency: offered choices,
    # restoration, and catalogue operations remain useful during its outage.
    store = getattr(request.app.state, "conversations", None)
    if store is not None:
        await asyncio.to_thread(store.ready)
    return {"status": "ok", "service": "core", "storage_backend": request.app.state.settings.storage_backend}
