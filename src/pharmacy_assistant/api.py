from contextlib import asynccontextmanager
import math
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from pharmacy_assistant.catalog import DATASET, MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest, ChatResponse
from pharmacy_assistant.pharmacy_directory import PHARMACIES, PharmacyDirectory
from pharmacy_assistant.config import Settings
from pharmacy_assistant.nlu import InferenceError
from pharmacy_assistant.inference import create_interpreter
from pharmacy_assistant.nlu_models import (
    InferenceErrorResponse, InterpretationRequest, InterpretationResponse,
)
from pharmacy_assistant.models import (
    HealthResponse,
    Medication,
    MedicationSearchRequest,
    MedicationSearchResponse,
)


def get_catalog(request: Request) -> MedicationCatalog:
    return request.app.state.catalog


Catalog = Annotated[MedicationCatalog, Depends(get_catalog)]


def create_app(dataset: Path = DATASET, settings: Settings | None = None,
               pharmacy_dataset: Path = PHARMACIES) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Fail at startup for missing, empty, duplicate or malformed data.
        app.state.catalog = MedicationCatalog.from_path(dataset)
        app.state.directory = PharmacyDirectory.from_path(pharmacy_dataset)
        app.state.settings = settings if settings is not None else Settings.from_env()
        app.state.interpreter = create_interpreter(app.state.settings)
        app.state.chat = ChatService(app.state.catalog, app.state.interpreter, app.state.directory)
        try:
            yield
        finally:
            await app.state.interpreter.close()
            del app.state.chat
            del app.state.directory
            del app.state.interpreter
            del app.state.settings
            del app.state.catalog

    app = FastAPI(
        title="Patient-Pharmacy Assistant API",
        version="0.3.0",
        description="Grounded multilingual medication answers and a partial Rabat pharmacy directory.",
        lifespan=lifespan,
    )

    @app.exception_handler(InferenceError)
    async def inference_error_handler(request: Request, error: InferenceError):
        headers = {}
        if error.detail.retry_after_seconds is not None:
            headers["Retry-After"] = str(math.ceil(error.detail.retry_after_seconds))
        return JSONResponse(
            status_code=error.status_code,
            content=InferenceErrorResponse(detail=error.detail).model_dump(mode="json"),
            headers=headers,
        )

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request, catalog: Catalog):
        return HealthResponse(
            catalog_dataset=catalog.dataset_name,
            catalog_record_count=len(catalog.records),
            catalog_brand_count=catalog.brand_count,
            interpretation_configured=request.app.state.settings.interpretation_configured,
            interpretation_model=request.app.state.settings.inference_model,
            interpretation_provider=request.app.state.settings.inference_provider,
        )

    @app.post(
        "/interpret", response_model=InterpretationResponse,
        responses={code: {"model": InferenceErrorResponse} for code in (429, 502, 503, 504)},
    )
    async def interpret_patient_request(payload: InterpretationRequest, request: Request):
        return await request.app.state.interpreter.interpret(payload)

    @app.post(
        "/chat", response_model=ChatResponse,
        responses={410: {"description": "Clarification expired or lost after server restart"},
                   **{code: {"model": InferenceErrorResponse} for code in (429, 502, 503, 504)}},
    )
    async def chat(payload: ChatRequest, request: Request):
        return await request.app.state.chat.respond(payload)

    # Register the static search path before the record-ID path.
    @app.get("/medications/search", response_model=MedicationSearchResponse)
    def search_medication_endpoint(
        filters: Annotated[MedicationSearchRequest, Query()], catalog: Catalog
    ):
        return catalog.search(filters)

    @app.get("/medications/{record_id}", response_model=Medication)
    def medication_by_id(record_id: str, catalog: Catalog):
        medication = catalog.get(record_id)
        if medication is None:
            raise HTTPException(
                status_code=404,
                detail=f"Medication record {record_id!r} was not found in this partial catalogue.",
            )
        return medication

    return app


app = create_app()
