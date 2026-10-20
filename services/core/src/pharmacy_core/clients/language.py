"""Single-attempt HTTP interpreter. No provider access, local fallback, or retries."""

import asyncio
import httpx
from pydantic import ValidationError

from pharmacy_core.config import CoreSettings
from pharmacy_contracts.language import ERRORS, LanguageHealth
from pharmacy_contracts.interpretation import (
    InferenceError, InferenceErrorResponse, InterpretationRequest, InterpretationResponse,
)

MAX_RESPONSE_BYTES = 65536


def failure(code, delay=None):
    status, retryable, message = ERRORS[code]
    return InferenceError(code, message, status, retryable, delay)


class HttpInterpreter:
    def __init__(self, settings: CoreSettings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client if client is not None else httpx.AsyncClient(
            base_url=settings.language_service_url,
            trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(settings.language_service_timeout_seconds, connect=2, pool=2),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self):
        await self.client.aclose()

    async def _request(self, method, path, *, seconds, **kwargs):
        try:
            async with asyncio.timeout(seconds):
                async with self.client.stream(method, self.settings.language_service_url + path, **kwargs) as response:
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE_BYTES:
                            raise failure("language_invalid_response")
                    return response.status_code, bytes(data)
        except (TimeoutError, httpx.TimeoutException):
            raise failure("language_timeout") from None
        except httpx.RequestError:
            raise failure("language_unavailable") from None

    async def health(self) -> LanguageHealth | None:
        try:
            status, data = await self._request("GET", "/health", seconds=1)
            if status == 200:
                return LanguageHealth.model_validate_json(data, strict=True)
        except (InferenceError, ValidationError):
            pass
        return None

    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse:
        status, data = await self._request("POST", "/v1/interpret",
            seconds=self.settings.language_service_timeout_seconds, json=request.model_dump())
        try:
            if status == 200:
                result = InterpretationResponse.model_validate_json(data, strict=True)
                result.interpretation.validate_evidence(request.text)
                return result
            error = InferenceErrorResponse.model_validate_json(data, strict=True).detail
            if error.code in ERRORS and status == ERRORS[error.code][0]:
                raise failure(error.code, error.retry_after_seconds)
        except (ValidationError, ValueError, TypeError):
            pass
        raise failure("language_invalid_response")


def create_interpreter(settings: CoreSettings):
    return HttpInterpreter(settings)
