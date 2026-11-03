"""Single-attempt HTTP client for the local OCR/matching image service."""

import asyncio

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pharmacy_contracts.interpretation import InferenceError
from pharmacy_core.config import CoreSettings
from pharmacy_core.conversation.image import (
    ImageCandidate,
    ImageIdentification,
)

MAX_RESPONSE_BYTES = 2_000_000


class MedidRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_record_id: str


class MedidMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    record: MedidRecord
    score: float
    field_scores: dict[str, float] = Field(default_factory=dict)


class MedidIdentification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str
    matches: list[MedidMatch] = Field(default_factory=list)
    elapsed_ms: float = 0.0


def failure(code: str) -> InferenceError:
    status, retryable, message = {
        "image_invalid": (422, False, "La photo envoyée n'est pas une image valide."),
        "image_too_large": (413, False, "La photo dépasse la taille maximale de 15 Mo."),
        "image_service_unavailable": (
            503,
            True,
            "Le service d'identification des photos est inaccessible.",
        ),
        "image_service_timeout": (
            504,
            True,
            "L'identification de la photo a dépassé le délai autorisé.",
        ),
        "image_identification_failed": (
            502,
            False,
            "L'identification de la photo a échoué. Aucun médicament n'a été inventé.",
        ),
    }[code]
    return InferenceError(code, message, status, retryable)


class HttpImageIdentifier:
    def __init__(
        self,
        settings: CoreSettings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client if client is not None else httpx.AsyncClient(
            base_url=settings.image_service_url,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(
                settings.image_service_timeout_seconds,
                connect=2,
                pool=2,
            ),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, path: str, *, seconds: float, **kwargs):
        try:
            async with asyncio.timeout(seconds):
                async with self.client.stream(
                    "POST",
                    self.settings.image_service_url + path,
                    **kwargs,
                ) as response:
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE_BYTES:
                            raise failure("image_identification_failed")
                    return response.status_code, bytes(data)
        except (TimeoutError, httpx.TimeoutException):
            raise failure("image_service_timeout") from None
        except httpx.RequestError:
            raise failure("image_service_unavailable") from None

    async def identify(
        self,
        image_bytes: bytes,
        *,
        content_type: str = "image/jpeg",
    ) -> ImageIdentification:
        status, data = await self._request(
            "/identify/image",
            seconds=self.settings.image_service_timeout_seconds,
            data={
                "top_k": str(self.settings.image_top_k),
                "min_score": str(self.settings.image_min_score),
                "scoring_mode": "field_aware",
                "group_presentations": "true",
            },
            files={
                "file": (
                    "medication",
                    image_bytes,
                    content_type or "application/octet-stream",
                )
            },
        )
        if status == 413:
            raise failure("image_too_large")
        if status == 400:
            raise failure("image_invalid")
        if status == 503:
            raise failure("image_service_unavailable")
        if status != 200:
            raise failure("image_identification_failed")
        try:
            result = MedidIdentification.model_validate_json(data)
        except (ValidationError, ValueError):
            raise failure("image_identification_failed") from None
        return ImageIdentification(
            query=result.query,
            candidates=tuple(
                ImageCandidate(
                    source_record_id=match.record.source_record_id,
                    score=match.score,
                    field_scores=match.field_scores,
                )
                for match in result.matches
            ),
            elapsed_ms=result.elapsed_ms,
        )


def create_image_identifier(settings: CoreSettings) -> HttpImageIdentifier:
    return HttpImageIdentifier(settings)
