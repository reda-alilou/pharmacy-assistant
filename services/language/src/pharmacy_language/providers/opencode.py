"""OpenCode's GLM extraction adapter, with explicit output mode and no fallback."""

import asyncio
import json
import logging
import time

import httpx

from pharmacy_language.config import OPENCODE_BASE_URL, LanguageSettings as Settings
from pharmacy_contracts.interpretation import InferenceError
from pharmacy_language.extraction.prompt import PROMPT_VERSION, SYSTEM_PROMPT
from pharmacy_language.extraction.validation import parse_retry_after
from pharmacy_contracts.interpretation import (
    InferenceMetadata, Interpretation, InterpretationRequest, InterpretationResponse, TokenUsage,
)
from pharmacy_language.quota.control import AttemptControl


logger = logging.getLogger(__name__)


def status_error(response: httpx.Response) -> InferenceError:
    # Provider text may contain keys or patient input; never relay or log it.
    status = response.status_code
    if status == 401:
        return InferenceError("provider_authentication_failed", "OpenCode rejected the configured key.", 503)
    if status == 403:
        try:
            body = response.json()
            detail = body.get("error", {}) if isinstance(body, dict) else {}
        except ValueError:
            detail = {}
        if isinstance(detail, dict) and detail.get("type") == "FreeTierError":
            return InferenceError(
                "provider_free_tier_restricted",
                "OpenCode restricts this free tier to use within OpenCode. Direct inference from this application is unavailable.",
                503,
            )
        return InferenceError("provider_permission_denied", "The OpenCode account cannot access this model.", 503)
    if status == 402:
        return InferenceError("provider_payment_required", "OpenCode requested billing or credits. No paid fallback was attempted.", 503)
    delay = parse_retry_after(response.headers.get("retry-after"))
    if status == 429:
        return InferenceError("provider_rate_limited", "OpenCode's rate limit was reached.", 429, True, delay)
    if status == 408 or status >= 500:
        return InferenceError("provider_unavailable", "OpenCode is temporarily unavailable.", 503, True, delay)
    if status == 400:
        try:
            body = response.json()
            detail = body.get("error", {}) if isinstance(body, dict) else {}
        except ValueError:
            detail = {}
        if isinstance(detail, dict) and detail.get("code") == "json_validate_failed":
            return InferenceError("provider_generation_failed", "OpenCode could not generate valid structured output.", 502, True)
    return InferenceError(
        "provider_request_rejected",
        "OpenCode rejected the model, endpoint or output mode. No schema downgrade or model fallback was attempted.", 503,
    )


class OpenCodeInterpreter:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None, *, control: AttemptControl | None = None):
        self.settings = settings
        self.client = client
        self.control = control
        if self.client is None and settings.opencode_api_key is not None:
            self.client = httpx.AsyncClient(timeout=settings.opencode_timeout_seconds, follow_redirects=False)

    async def close(self):
        if self.control is not None:
            await asyncio.to_thread(self.control.close)
        if self.client is not None:
            await self.client.aclose()

    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse:
        if self.client is None or self.settings.opencode_api_key is None:
            raise InferenceError("model_not_configured", "Set OPENCODE_API_KEY in the local .env file to use GLM.", 503)
        mode = self.settings.opencode_output_mode
        schema = Interpretation.model_json_schema()
        response_format = ({"type": "json_schema", "json_schema": {
            "name": "patient_pharmacy_interpretation", "strict": True, "schema": schema,
        }} if mode == "json_schema" else {"type": "json_object"})
        prompt = SYSTEM_PROMPT
        if mode == "json_object":
            # This mode is explicitly configured, not a silent downgrade.
            prompt += "\nReturn a JSON object matching this exact schema:\n" + json.dumps(schema, ensure_ascii=False)
        payload = {
            "model": self.settings.opencode_model, "messages": [
                {"role": "system", "content": prompt}, {"role": "user", "content": request.text},
            ], "response_format": response_format, "temperature": 0,
            "max_tokens": self.settings.opencode_max_completion_tokens, "stream": False,
        }
        if self.settings.opencode_model.startswith("glm-5.3-flash"):
            # The model card documents max thinking as the default. Extraction
            # uses its supported low budget to avoid unnecessary reasoning time.
            payload["reasoning_effort"] = "low"
        started = time.monotonic()
        for attempt in (1, 2):
            if self.control is not None:
                await self.control.before_attempt()
            failure = None
            try:
                response = await asyncio.wait_for(self.client.post(
                    OPENCODE_BASE_URL + "/chat/completions", json=payload,
                    headers={"Authorization": "Bearer " + self.settings.opencode_api_key.get_secret_value()},
                    follow_redirects=False,
                ), timeout=self.settings.opencode_timeout_seconds)
                if not 200 <= response.status_code < 300:
                    failure = status_error(response)
            except (asyncio.TimeoutError, httpx.TimeoutException):
                failure = InferenceError("provider_timeout", "OpenCode timed out.", 504, True)
            except httpx.RequestError:
                failure = InferenceError("provider_unreachable", "Cannot reach OpenCode.", 503, True)
            if failure is not None:
                if self.control is not None:
                    failure = await asyncio.to_thread(self.control.failed, failure)
                delay = failure.detail.retry_after_seconds
                if attempt == 1 and failure.status_code != 429 and failure.detail.retryable and (delay is None or delay <= 2):
                    await asyncio.sleep(1 if delay is None else delay)
                    continue
                logger.warning("Interpretation failed provider=opencode code=%s attempts=%d", failure.detail.code, attempt)
                raise failure from None
            try:
                body = response.json()
                choice = body["choices"][0]
                message = choice["message"]
                if message.get("refusal") or choice.get("finish_reason") == "content_filter":
                    raise InferenceError("provider_refused", "OpenCode declined to interpret the request.", 422)
                if choice.get("finish_reason") != "stop" or not isinstance(message.get("content"), str):
                    raise ValueError("Incomplete response")
                interpretation = Interpretation.model_validate_json(message["content"])
                interpretation.validate_evidence(request.text)
                usage = body.get("usage") or {}
                metadata = InferenceMetadata(
                    provider="opencode", output_mode=mode, requested_model=self.settings.opencode_model,
                    model=body["model"], prompt_version=PROMPT_VERSION, attempts=attempt,
                    latency_ms=round((time.monotonic() - started) * 1000, 2), completion_id=body.get("id"),
                    usage=TokenUsage(**{field: usage.get(field) for field in ("prompt_tokens", "completion_tokens", "total_tokens")}),
                )
            except InferenceError:
                raise
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                raise InferenceError("provider_invalid_response", "OpenCode returned invalid or unsupported extracted data. No interpretation was accepted.", 502) from None
            return InterpretationResponse(interpretation=interpretation, metadata=metadata)
        raise AssertionError("Unreachable retry state")
