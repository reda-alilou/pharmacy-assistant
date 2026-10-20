"""Native Gemini extraction: schema output, local validation, bounded retries."""

import asyncio
import logging
import time

import httpx

from pharmacy_assistant.config import GEMINI_BASE_URL, Settings
from pharmacy_assistant.language.nlu import InferenceError, PROMPT_VERSION, SYSTEM_PROMPT, parse_retry_after
from pharmacy_assistant.contracts.nlu_models import (
    InferenceMetadata, Interpretation, InterpretationRequest, InterpretationResponse, TokenUsage,
)
from pharmacy_assistant.language.quota import AttemptControl, daily_reset_delay


logger = logging.getLogger(__name__)


def status_error(response: httpx.Response) -> InferenceError:
    # Inspect only typed error fields. Never expose Google's body, which may
    # contain credentials or patient text, in logs or public error messages.
    try:
        body = response.json()
        error = body.get("error", {}) if isinstance(body, dict) else {}
        details = error.get("details", []) if isinstance(error, dict) else []
        if not isinstance(details, list):
            details = []
    except ValueError:
        details = []
    invalid_key = any(isinstance(d, dict) and d.get("reason") in (
        "API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_NOT_FOUND",
    ) for d in details)
    status = response.status_code
    if status == 401 or invalid_key:
        return InferenceError("provider_authentication_failed", "Gemini rejected the configured key.", 503)
    if status == 403:
        return InferenceError("provider_permission_denied", "The Google project cannot access Gemini or this model.", 503)
    if status == 404:
        return InferenceError("provider_model_unavailable", "The configured Gemini model is unavailable for this project or API.", 503)
    delay = parse_retry_after(response.headers.get("retry-after"))
    for detail in details:
        if isinstance(detail, dict) and detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
            duration = detail.get("retryDelay")
            if isinstance(duration, str) and duration.endswith("s"):
                retry_delay = parse_retry_after(duration[:-1])
                if retry_delay is not None:
                    delay = max(delay or 0, retry_delay)
    if status == 429:
        daily = any(
            isinstance(detail, dict) and detail.get("@type") == "type.googleapis.com/google.rpc.QuotaFailure"
            and isinstance(detail.get("violations"), list)
            and any(isinstance(v, dict) and isinstance(v.get("quotaId"), str)
                    and "perday" in v["quotaId"].casefold().replace("_", "") for v in detail["violations"])
            for detail in details
        )
        if daily:
            return InferenceError("provider_daily_quota_exhausted", "Gemini's daily quota is exhausted. Resume after its reset.",
                                  429, False, max(delay or 0, daily_reset_delay()))
        return InferenceError("provider_rate_limited", "Gemini's quota or rate limit was reached. Check the free project quota.", 429, True, delay)
    if status == 408 or status >= 500:
        return InferenceError("provider_unavailable", "Gemini is temporarily unavailable.", 503, True, delay)
    return InferenceError("provider_request_rejected", "Gemini rejected the model or structured-output configuration.", 503)


class GeminiInterpreter:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None, *, control: AttemptControl | None = None):
        self.settings = settings
        self.client = client
        self.control = control
        if self.client is None and settings.gemini_api_key is not None:
            self.client = httpx.AsyncClient(timeout=settings.gemini_timeout_seconds, follow_redirects=False)

    async def close(self):
        if self.control is not None:
            await asyncio.to_thread(self.control.close)
        if self.client is not None:
            await self.client.aclose()

    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse:
        if self.client is None or self.settings.gemini_api_key is None:
            raise InferenceError("model_not_configured", "Set GEMINI_API_KEY in the local .env file to use Gemini.", 503)
        generation = {
            "maxOutputTokens": self.settings.gemini_max_output_tokens,
            "responseFormat": {"text": {
                "mimeType": "APPLICATION_JSON", "schema": Interpretation.model_json_schema(),
            }},
        }
        if self.settings.gemini_model.startswith("gemini-3"):
            generation["thinkingConfig"] = {"thinkingLevel": "LOW", "includeThoughts": False}
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": request.text}]}],
            "generationConfig": generation,
        }
        started = time.monotonic()
        for attempt in (1, 2):
            if self.control is not None:
                await self.control.before_attempt()
            failure = None
            try:
                response = await asyncio.wait_for(self.client.post(
                    f"{GEMINI_BASE_URL}/{self.settings.gemini_model}:generateContent",
                    json=payload, headers={"x-goog-api-key": self.settings.gemini_api_key.get_secret_value()},
                    follow_redirects=False,
                ), timeout=self.settings.gemini_timeout_seconds)
                if not 200 <= response.status_code < 300:
                    failure = status_error(response)
            except (asyncio.TimeoutError, httpx.TimeoutException):
                failure = InferenceError("provider_timeout", "Gemini timed out.", 504, True)
            except httpx.RequestError:
                failure = InferenceError("provider_unreachable", "Cannot reach Gemini.", 503, True)
            if failure is not None:
                if self.control is not None:
                    failure = await asyncio.to_thread(self.control.failed, failure)
                delay = failure.detail.retry_after_seconds
                if attempt == 1 and failure.status_code != 429 and failure.detail.retryable and (delay is None or delay <= 2):
                    await asyncio.sleep(1 if delay is None else delay)
                    continue
                logger.warning("Interpretation failed provider=gemini code=%s attempts=%d", failure.detail.code, attempt)
                raise failure from None
            try:
                body = response.json()
                if body.get("promptFeedback", {}).get("blockReason") not in (None, "BLOCK_REASON_UNSPECIFIED"):
                    raise InferenceError("provider_refused", "Gemini declined to interpret the request.", 422)
                candidates = body["candidates"]
                if len(candidates) != 1:
                    raise ValueError("Unexpected candidate count")
                candidate = candidates[0]
                finish = candidate.get("finishReason")
                if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                    raise InferenceError("provider_refused", "Gemini declined to interpret the request.", 422)
                if finish != "STOP":
                    raise ValueError("Incomplete response")
                # Reasoning parts are never included in extracted JSON or returned.
                parts = [part for part in candidate["content"]["parts"] if not part.get("thought", False)]
                if not parts or any(not isinstance(part.get("text"), str) for part in parts):
                    raise ValueError("Missing text")
                interpretation = Interpretation.model_validate_json("".join(part["text"] for part in parts))
                interpretation.validate_evidence(request.text)
                usage = body.get("usageMetadata") or {}
                metadata = InferenceMetadata(
                    provider="gemini", output_mode="json_schema", requested_model=self.settings.gemini_model,
                    model=body["modelVersion"], completion_id=body.get("responseId"),
                    prompt_version=PROMPT_VERSION, attempts=attempt,
                    latency_ms=round((time.monotonic() - started) * 1000, 2),
                    usage=TokenUsage(prompt_tokens=usage.get("promptTokenCount"),
                                     completion_tokens=usage.get("candidatesTokenCount"),
                                     total_tokens=usage.get("totalTokenCount")),
                )
            except InferenceError:
                raise
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                raise InferenceError("provider_invalid_response", "Gemini returned invalid or unsupported extracted data. No interpretation was accepted.", 502) from None
            return InterpretationResponse(interpretation=interpretation, metadata=metadata)
        raise AssertionError("Unreachable retry state")
