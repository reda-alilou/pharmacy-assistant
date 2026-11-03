from __future__ import annotations

import json
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .api_schemas import (
    CatalogStatsOut,
    HealthOut,
    IdentificationOut,
    IdentifyOptions,
    ServiceInfoOut,
    TextIdentifyRequest,
)
from .api_service import (
    SERVICE_NAME,
    SERVICE_VERSION,
    MedicationAPIService,
)
from .config import Settings
from .logging_config import configure_logging, get_logger

logger = get_logger("api")

MAX_IMAGE_BYTES = 15_000_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    if getattr(app.state, "service", None) is None:
        app.state.service = MedicationAPIService(app.state.settings)
    logger.info("%s %s started", SERVICE_NAME, SERVICE_VERSION)
    yield
    logger.info("%s stopped", SERVICE_NAME)


def create_app(
    settings: Settings | None = None,
    service: MedicationAPIService | None = None,
) -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="AMMPS Medication Identifier API",
        description=(
            "OCR and fuzzy matching backend for the AMMPS medication "
            "packaging identifier."
        ),
        version=SERVICE_VERSION,
        lifespan=lifespan,
    )
    app.state.settings = settings or Settings()
    app.state.service = service

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        client = request.client.host if request.client else "unknown"
        logger.info(
            "API %s %s started (request_id=%s, client=%s)",
            request.method,
            request.url.path,
            request_id,
            client,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "API %s %s failed (request_id=%s)",
                request.method,
                request.url.path,
                request_id,
            )
            raise
        elapsed_ms = (perf_counter() - started) * 1000
        logger.info(
            "API %s %s -> %d (%.0f ms, request_id=%s)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    def get_service(request: Request) -> MedicationAPIService:
        service_instance = getattr(request.app.state, "service", None)
        if service_instance is None:
            raise HTTPException(
                status_code=503,
                detail="The identification service is not ready.",
            )
        return service_instance

    def request_id_for(request: Request) -> str:
        return getattr(request.state, "request_id", uuid4().hex)

    @app.get("/", response_model=ServiceInfoOut)
    def service_info() -> ServiceInfoOut:
        return ServiceInfoOut(
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            docs_url="/docs",
            endpoints=[
                "/health",
                "/catalog/stats",
                "/identify/text",
                "/identify/image",
            ],
        )

    @app.get("/health", response_model=HealthOut)
    def health(request: Request) -> HealthOut:
        return get_service(request).health()

    @app.get("/catalog/stats", response_model=CatalogStatsOut)
    def catalog_stats(request: Request) -> CatalogStatsOut:
        return get_service(request).stats

    @app.post("/identify/text", response_model=IdentificationOut)
    def identify_text(
        payload: TextIdentifyRequest,
        request: Request,
    ) -> IdentificationOut:
        try:
            return get_service(request).identify_text(
                payload.text,
                options=payload,
                request_id=request_id_for(request),
            )
        except ValueError as exc:
            logger.warning(
                "Invalid text request (request_id=%s): %s",
                request_id_for(request),
                exc,
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(
                "Text identification failed (request_id=%s)",
                request_id_for(request),
            )
            raise HTTPException(
                status_code=500,
                detail="Identification failed on the server.",
            ) from exc

    @app.post("/identify/image", response_model=IdentificationOut)
    async def identify_image(
        request: Request,
        file: Annotated[UploadFile, File()],
        top_k: Annotated[int | None, Form(ge=1, le=50)] = None,
        min_score: Annotated[float | None, Form(ge=0.0, le=100.0)] = None,
        scoring_mode: Annotated[str | None, Form()] = None,
        group_presentations: Annotated[bool | None, Form()] = None,
        weights_json: Annotated[str | None, Form()] = None,
        ocr_min_confidence: Annotated[
            float | None, Form(ge=0.0, le=1.0)
        ] = None,
    ) -> IdentificationOut:
        request_id = request_id_for(request)
        weights = None
        if weights_json:
            try:
                parsed = json.loads(weights_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="weights_json must be valid JSON.",
                ) from exc
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=400,
                    detail="weights_json must be a JSON object.",
                )
            weights = parsed

        try:
            options = IdentifyOptions(
                top_k=top_k,
                min_score=min_score,
                scoring_mode=scoring_mode,
                group_presentations=group_presentations,
                weights=weights,
                ocr_min_confidence=ocr_min_confidence,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=exc.errors(),
            ) from exc

        content_type = (file.content_type or "").lower()
        if content_type and not (
            content_type.startswith("image/")
            or content_type == "application/octet-stream"
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported content type: {file.content_type}",
            )

        try:
            image_bytes = await file.read()
        finally:
            await file.close()

        if not image_bytes:
            raise HTTPException(status_code=400, detail="The image is empty.")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "The image is too large. Maximum size is "
                    f"{MAX_IMAGE_BYTES // 1_000_000} MB."
                ),
            )

        try:
            service_instance = get_service(request)
            return await run_in_threadpool(
                service_instance.identify_image,
                image_bytes,
                options=options,
                request_id=request_id,
            )
        except ValueError as exc:
            logger.warning(
                "Invalid image request (request_id=%s): %s",
                request_id,
                exc,
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(
                "Image identification failed (request_id=%s)",
                request_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Identification failed on the server.",
            ) from exc

    return app


app = create_app()
