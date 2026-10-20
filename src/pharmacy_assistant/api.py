from contextlib import asynccontextmanager, suppress
import asyncio
import math
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from pharmacy_assistant.core.catalog import DATASET, MedicationCatalog
from pharmacy_assistant.core.chat import ChatService
from pharmacy_assistant.core.chat_models import ChatRequest, ChatResponse, ConversationView
from pharmacy_assistant.core.errors import ChatError
from pharmacy_assistant.core.pharmacy_directory import PHARMACIES, PharmacyDirectory
from pharmacy_assistant.config import CoreSettings, Settings
from pharmacy_assistant.contracts.language_service import LanguageHealth
from pharmacy_assistant.contracts.storage import StorageUnavailable
from pharmacy_assistant.transport.language import create_interpreter
from pharmacy_assistant.contracts.nlu_models import (
    InferenceError, InferenceErrorResponse, InterpretationRequest, InterpretationResponse,
)
from pharmacy_assistant.core.models import (
    HealthResponse,
    Medication,
    MedicationSearchRequest,
    MedicationSearchResponse,
)


def get_catalog(request: Request) -> MedicationCatalog:
    return request.app.state.catalog


Catalog = Annotated[MedicationCatalog, Depends(get_catalog)]


def create_app(dataset: Path = DATASET, settings: CoreSettings | Settings | None = None,
               pharmacy_dataset: Path = PHARMACIES) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Fail at startup for missing, empty, duplicate or malformed data.
        app.state.settings = CoreSettings.for_app(settings) if settings is not None else CoreSettings.from_env()
        engine, cleanup_task = None, None
        if app.state.settings.storage_backend == "postgres":
            from pharmacy_assistant.database import create_database_engine
            from pharmacy_assistant.core.storage.catalogue import load_catalogue
            from pharmacy_assistant.core.storage.chat import PersistentChatService
            from pharmacy_assistant.core.storage.conversations import ConversationStore
            engine = create_database_engine(app.state.settings.core_database_url.get_secret_value())
            try:
                app.state.catalog, app.state.directory = await asyncio.to_thread(load_catalogue, engine)
            except Exception:
                engine.dispose()
                raise RuntimeError("PostgreSQL catalogue unavailable. Run explicit migrations/import validation; no file fallback was used.") from None
            app.state.conversations = ConversationStore(engine)
        else:
            app.state.catalog = MedicationCatalog.from_path(dataset)
            app.state.directory = PharmacyDirectory.from_path(pharmacy_dataset)
        app.state.interpreter = create_interpreter(app.state.settings)
        if engine:
            app.state.chat = PersistentChatService(app.state.catalog, app.state.interpreter,
                                                  app.state.directory, app.state.conversations)
            async def cleanup():
                while True:
                    try:
                        await asyncio.to_thread(app.state.conversations.cleanup)
                    except StorageUnavailable:
                        pass  # Access checks still reject expired state while cleanup is unavailable.
                    await asyncio.sleep(60)
            cleanup_task = asyncio.create_task(cleanup())
        else:
            app.state.chat = ChatService(app.state.catalog, app.state.interpreter, app.state.directory)
        try:
            yield
        finally:
            if cleanup_task:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task
            await app.state.interpreter.close()
            if engine:
                await asyncio.to_thread(engine.dispose)
                del app.state.conversations
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

    @app.exception_handler(ChatError)
    async def chat_error_handler(request: Request, error: ChatError):
        status = {
            "session_expired": 410,
            "clarification_expired": 410,
            "invalid_reference": 422,
            "invalid_selection": 422,
            "invalid_refinement": 422,
            "conversation_conflict": 409,
            "request_in_progress": 409,
            "request_conflict": 409,
        }[error.code]
        return JSONResponse(
            status_code=status,
            content={"detail": {"code": error.code, "message": error.message}},
        )

    @app.exception_handler(StorageUnavailable)
    async def storage_error_handler(request: Request, error: StorageUnavailable):
        return JSONResponse(status_code=503, content={"detail": {"code": "storage_unavailable",
            "message": str(error), "retryable": True, "retry_after_seconds": None}})

    def conversation_store(request: Request):
        store = getattr(request.app.state, "conversations", None)
        if store is None:
            raise StorageUnavailable()
        return store

    def bearer(authorization):
        if not authorization or not authorization.startswith("Bearer ") or not 20 <= len(authorization[7:]) <= 100:
            raise HTTPException(401, detail="A valid conversation bearer token is required.")
        return authorization[7:]

    @app.post("/conversation", response_model=ConversationView)
    async def new_conversation(request: Request):
        return await asyncio.to_thread(conversation_store(request).create)

    @app.get("/conversation", response_model=ConversationView)
    async def restore_conversation(request: Request, authorization: Annotated[str | None, Header()] = None):
        return await asyncio.to_thread(conversation_store(request).restore, bearer(authorization))

    @app.delete("/conversation", status_code=204)
    async def reset_conversation(request: Request, authorization: Annotated[str | None, Header()] = None):
        await asyncio.to_thread(conversation_store(request).reset, bearer(authorization))

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

    @app.get("/ready")
    async def ready(request: Request):
        # Language is deliberately not a readiness dependency: offered choices,
        # restoration, and catalogue operations remain useful during its outage.
        store = getattr(request.app.state, "conversations", None)
        if store is not None:
            await asyncio.to_thread(store.ready)
        return {"status": "ok", "service": "core", "storage_backend": request.app.state.settings.storage_backend}

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
