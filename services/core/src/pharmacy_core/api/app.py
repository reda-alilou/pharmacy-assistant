from contextlib import asynccontextmanager, suppress
import asyncio
import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pharmacy_core.conversation.errors import ChatError
from pharmacy_core.api.resources import CoreResources
from pharmacy_core.config import CoreSettings
from pharmacy_contracts.errors import StorageUnavailable
from pharmacy_core.clients.language import create_interpreter
from pharmacy_contracts.interpretation import InferenceError, InferenceErrorResponse


from pharmacy_core.api.routes import conversations, health, chat as chat_routes, catalogue


def create_app(settings: CoreSettings | None = None, *, resources: CoreResources | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = CoreSettings.for_app(settings) if settings is not None else CoreSettings.from_env()
        engine, cleanup_task = None, None
        if resources is None:
            from pharmacy_infrastructure.database import create_database_engine
            from pharmacy_core.storage.postgres.catalogue import load_catalogue
            from pharmacy_core.storage.postgres.chat import PersistentChatService
            from pharmacy_core.storage.postgres.conversations import ConversationStore
            engine = create_database_engine(app.state.settings.core_database_url.get_secret_value())
            try:
                app.state.catalog, app.state.directory = await asyncio.to_thread(load_catalogue, engine)
                app.state.conversations = ConversationStore(engine)
                await asyncio.to_thread(app.state.conversations.ready)
            except Exception:
                engine.dispose()
                raise RuntimeError("Core PostgreSQL storage unavailable. Check connectivity and run explicit migrations/import validation; no file fallback is available.") from None
            try:
                app.state.interpreter = create_interpreter(app.state.settings)
            except Exception:
                engine.dispose()
                raise
            app.state.chat = PersistentChatService(app.state.catalog, app.state.interpreter,
                                                  app.state.directory, app.state.conversations)
        else:
            # Only an explicit caller supplies offline resources; no settings/env
            # value can select file-mode or an in-memory service at startup.
            app.state.catalog, app.state.directory = resources.catalog, resources.directory
            app.state.interpreter, app.state.chat = resources.interpreter, resources.chat
            if resources.conversations is not None:
                app.state.conversations = resources.conversations
        if engine:
            async def cleanup():
                while True:
                    try:
                        await asyncio.to_thread(app.state.conversations.cleanup)
                    except StorageUnavailable:
                        pass  # Access checks still reject expired state while cleanup is unavailable.
                    await asyncio.sleep(60)
            cleanup_task = asyncio.create_task(cleanup())
        try:
            yield
        finally:
            if cleanup_task:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task
            try:
                await app.state.interpreter.close()
            finally:
                if engine:
                    await asyncio.to_thread(engine.dispose)
                for name in ("conversations", "chat", "directory", "interpreter", "settings", "catalog"):
                    if hasattr(app.state, name):
                        delattr(app.state, name)

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


    # Register the static search path before the record-ID path.


    for router in (conversations.router, health.router, chat_routes.router, catalogue.router):
        app.include_router(router)
    return app


app = create_app()
