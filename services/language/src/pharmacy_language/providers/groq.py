"""Hosted multilingual extraction with one bounded transient retry."""

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import groq

from pharmacy_language.config import LanguageSettings as Settings
from pharmacy_contracts.interpretation import (
    InferenceError, InferenceMetadata, Interpretation, InterpretationRequest,
    InterpretationResponse, TokenUsage,
)
from pharmacy_language.quota.control import AttemptControl


from pharmacy_language.extraction.prompt import PROMPT_VERSION, SYSTEM_PROMPT
from pharmacy_language.extraction.validation import parse_retry_after

logger = logging.getLogger(__name__)


def retry_after(error: groq.APIStatusError) -> float | None:
    return parse_retry_after(error.response.headers.get("retry-after"))




def map_provider_error(error: Exception) -> InferenceError:
    # Never propagate provider response text: it can echo patient data or secrets.
    if isinstance(error, (asyncio.TimeoutError, groq.APITimeoutError)):
        return InferenceError("provider_timeout", "The interpretation provider timed out.", 504, True)
    if isinstance(error, groq.APIConnectionError):
        return InferenceError("provider_unreachable", "Cannot reach the interpretation provider.", 503, True)
    if isinstance(error, groq.APIStatusError):
        status = error.status_code
        body = error.body if isinstance(error.body, dict) else {}
        details = body.get("error", body)
        if status == 400 and isinstance(details, dict) and details.get("code") == "json_validate_failed":
            return InferenceError(
                "provider_generation_failed",
                "Groq could not generate a schema-compliant interpretation. No output was accepted.",
                502, True,
            )
        if status == 401:
            return InferenceError("provider_authentication_failed", "The configured Groq key was rejected.", 503)
        if status == 403:
            return InferenceError("provider_permission_denied", "The Groq account cannot access this service or model.", 503)
        if status == 429:
            return InferenceError("provider_rate_limited", "Groq's rate limit was reached. Try again later.",
                                  429, True, retry_after(error))
        if status == 408 or status >= 500:
            return InferenceError("provider_unavailable", "The interpretation provider is temporarily unavailable.",
                                  503, True, retry_after(error))
        return InferenceError("provider_request_rejected", "Groq rejected the configured model or request schema.", 503)
    return InferenceError("provider_invalid_response", "Groq returned an invalid interpretation response.", 502)


class GroqInterpreter:
    def __init__(self, settings: Settings, client=None, *, control: AttemptControl | None = None):
        self.settings = settings
        self.client = client
        self.control = control
        if self.client is None and settings.groq_api_key is not None:
            self.client = groq.AsyncGroq(
                api_key=settings.groq_api_key.get_secret_value(),
                timeout=settings.groq_timeout_seconds,
                max_retries=0,  # Our single retry must not multiply SDK retries.
            )
        self.response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "patient_pharmacy_interpretation", "strict": True,
                "schema": Interpretation.model_json_schema(),
            },
        }
        if settings.groq_output_mode == "json_object":
            self.response_format = {"type": "json_object"}

    async def close(self):
        if self.control is not None:
            await asyncio.to_thread(self.control.close)
        if self.client is not None:
            await self.client.close()

    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse:
        if self.client is None or self.settings.groq_api_key is None:
            raise InferenceError(
                "model_not_configured", "Set GROQ_API_KEY in the project's local .env file and restart the API.", 503,
            )
        started = time.monotonic()
        prompt = SYSTEM_PROMPT
        if self.settings.groq_output_mode == "json_object":
            prompt += ("\nReturn one JSON object matching this schema exactly, including all required nullable fields:\n"
                       + json.dumps(Interpretation.model_json_schema(), ensure_ascii=False, separators=(",", ":")))
        options = {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": request.text},
            ],
            "response_format": self.response_format,
            "temperature": 0,
            "max_completion_tokens": self.settings.groq_max_completion_tokens,
            "stream": False,
        }
        if self.settings.groq_model == "qwen/qwen3.8-27b":
            options["reasoning_effort"] = "none"

        for attempt in (1, 2):
            if self.control is not None:
                await self.control.before_attempt()
            try:
                completion = await asyncio.wait_for(
                    self.client.chat.completions.create(**options),
                    timeout=self.settings.groq_timeout_seconds,
                )
            except (groq.APIError, asyncio.TimeoutError) as error:
                failure = map_provider_error(error)
                if self.control is not None:
                    failure = await asyncio.to_thread(self.control.failed, failure)
                delay = failure.detail.retry_after_seconds
                # Honor long provider cooldowns by returning them to the caller,
                # rather than retrying early or blocking the demo for a minute.
                if attempt == 1 and failure.status_code != 429 and failure.detail.retryable and (delay is None or delay <= 2):
                    await asyncio.sleep(1 if delay is None else delay)
                    continue
                logger.warning("Interpretation failed code=%s attempts=%d", failure.detail.code, attempt)
                raise failure from None

            try:
                choice = completion.choices[0]
                if getattr(choice.message, "refusal", None) or choice.finish_reason == "content_filter":
                    raise InferenceError("provider_refused", "The provider declined to interpret this request.", 422)
                if choice.finish_reason != "stop" or not choice.message.content:
                    raise ValueError("Incomplete model response")
                interpretation = Interpretation.model_validate_json(choice.message.content)
                interpretation.validate_evidence(request.text)
                usage = completion.usage
                metadata = InferenceMetadata(
                    output_mode=self.settings.groq_output_mode,
                    requested_model=self.settings.groq_model, model=completion.model,
                    prompt_version=PROMPT_VERSION, attempts=attempt,
                    latency_ms=round((time.monotonic() - started) * 1000, 2),
                    completion_id=completion.id,
                    usage=TokenUsage(**{
                        field: getattr(usage, field, None)
                        for field in ("prompt_tokens", "completion_tokens", "total_tokens")
                    }),
                )
            except InferenceError:
                raise
            except (ValueError, IndexError, AttributeError, TypeError):
                raise InferenceError(
                    "provider_invalid_response",
                    "Groq returned incomplete, invalid, or unsupported extracted data. No interpretation was accepted.",
                    502,
                ) from None

            logger.info("Interpretation complete model=%s attempts=%d latency_ms=%s tokens=%s",
                        metadata.model, metadata.attempts, metadata.latency_ms, metadata.usage.total_tokens)
            return InterpretationResponse(interpretation=interpretation, metadata=metadata)

        raise AssertionError("Unreachable retry state")
