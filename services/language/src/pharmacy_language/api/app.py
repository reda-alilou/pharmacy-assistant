"""Independent language HTTP application; no catalogue or conversation access."""

import asyncio
import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pharmacy_language.config import LanguageSettings
from pharmacy_contracts.language import ERRORS, LanguageHealth
from pharmacy_contracts.interpretation import (
    InferenceError, InferenceErrorResponse, InterpretationRequest, InterpretationResponse,
)
from pharmacy_language.extraction.service import create_interpreter
from pharmacy_contracts.interpreter import Interpreter


def create_app(settings: LanguageSettings | None = None, *, interpreter: Interpreter | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        config = LanguageSettings.for_app(settings) if settings is not None else LanguageSettings.from_env()
        app.state.settings = config
        app.state.interpreter = interpreter if interpreter is not None else create_interpreter(config)
        try:
            if interpreter is None:
                control = app.state.interpreter.control
                try:
                    await asyncio.to_thread(control.store.status, control.scope)
                except Exception:
                    raise RuntimeError("Language PostgreSQL quota storage unavailable. Check connectivity and run explicit migrations; no SQLite fallback is available.") from None
            yield
        finally:
            try:
                await app.state.interpreter.close()
            finally:
                del app.state.interpreter
                del app.state.settings

    app = FastAPI(title="Pharmacy Language Service", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(InferenceError)
    async def inference_error(request, error):
        code = error.detail.code if error.detail.code in ERRORS else "language_invalid_response"
        status, retryable, message = ERRORS[code]
        delay = error.detail.retry_after_seconds
        headers = {"Retry-After": str(math.ceil(delay))} if delay is not None else {}
        return JSONResponse(status_code=status, headers=headers, content=InferenceErrorResponse(
            detail=dict(code=code, message=message, retryable=retryable, retry_after_seconds=delay)
        ).model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        # FastAPI's default validation body echoes patient text and unknown fields.
        return JSONResponse(status_code=422, content={"detail": {
            "code": "invalid_request", "message": "Saisissez entre 1 et 2 000 caractères.",
            "retryable": False, "retry_after_seconds": None}})

    @app.get("/health", response_model=LanguageHealth)
    async def health(request: Request):
        config = request.app.state.settings
        return LanguageHealth(storage_backend=config.storage_backend,
            interpretation_configured=config.interpretation_configured,
            interpretation_provider=config.inference_provider, interpretation_model=config.inference_model)

    @app.get("/ready", response_model=LanguageHealth)
    async def ready(request: Request):
        if not request.app.state.settings.interpretation_configured:
            raise InferenceError("model_not_configured", "", 503)
        control = request.app.state.interpreter.control
        await asyncio.to_thread(control.store.status, control.scope)
        return await health(request)

    @app.post("/v1/interpret", response_model=InterpretationResponse,
              responses={code: {"model": InferenceErrorResponse} for code in (422, 429, 502, 503, 504)})
    async def interpret(payload: InterpretationRequest, request: Request):
        config = request.app.state.settings
        # Include provider-owned retries and quota operations inside one deadline.
        # Core makes exactly one HTTP attempt; uncertainty never triggers a replay.
        seconds = 2 * getattr(config, f"{config.inference_provider}_timeout_seconds") + 25
        try:
            async with asyncio.timeout(seconds):
                result = await request.app.state.interpreter.interpret(payload)
                result.interpretation.validate_evidence(payload.text)
                return result
        except TimeoutError:
            raise InferenceError("language_timeout", "", 504, True) from None
        except (ValueError, TypeError, AttributeError):
            raise InferenceError("provider_invalid_response", "", 502) from None

    return app


app = create_app()
