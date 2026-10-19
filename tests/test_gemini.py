"""Gemini HTTP contract and end-to-end grounding with offline inference."""

import asyncio
import copy
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pharmacy_assistant.api import create_app
from pharmacy_assistant.config import DEFAULT_GEMINI_MODEL, GEMINI_BASE_URL, Settings
from pharmacy_assistant.gemini_nlu import GeminiInterpreter
from pharmacy_assistant.inference import create_interpreter
from pharmacy_assistant.nlu import InferenceError
from pharmacy_assistant.nlu_models import InterpretationRequest
from test_interpretation import extraction


TEXT = "Wach kayn ABIP 15mg w bch7al?"


def completion(data=None):
    return {
        "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
            {"text": json.dumps(data or extraction())},
        ]}}],
        "modelVersion": "gemini-3.8-flash-test-version", "responseId": "offline-gemini",
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50,
                          "thoughtsTokenCount": 20, "totalTokenCount": 170},
    }


def adapter(handler, **kwargs):
    settings = Settings(gemini_api_key="offline-gemini-key", groq_api_key="DO_NOT_SEND_GROQ",
                        opencode_api_key="DO_NOT_SEND_OPENCODE", **kwargs)
    return GeminiInterpreter(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


class GeminiConfigTests(unittest.TestCase):
    def test_default_selection_key_isolation_and_health(self):
        settings = Settings(groq_api_key="unused-groq", opencode_api_key="unused-opencode")
        self.assertEqual(settings.inference_provider, "gemini")
        self.assertEqual(settings.inference_model, DEFAULT_GEMINI_MODEL)
        self.assertEqual(settings.inference_key_name, "GEMINI_API_KEY")
        self.assertEqual(settings.inference_output_mode, "json_schema")
        self.assertFalse(settings.interpretation_configured)
        self.assertIsInstance(create_interpreter(settings), GeminiInterpreter)
        self.assertNotIn("unused-groq", repr(settings))
        with TestClient(create_app(settings=settings)) as client:
            health = client.get("/health").json()
            self.assertEqual(health["interpretation_provider"], "gemini")
            self.assertEqual(health["interpretation_model"], DEFAULT_GEMINI_MODEL)
            self.assertFalse(health["interpretation_configured"])
            result = client.post("/chat", json={"text": TEXT})
            self.assertEqual(result.status_code, 503)
            self.assertIn("GEMINI_API_KEY", result.json()["detail"]["message"])
            self.assertNotIn("unused-", result.text)
            self.assertEqual(client.get("/medications/9079").status_code, 200)

    def test_environment_precedence_and_config_validation(self):
        with patch("pharmacy_assistant.config.dotenv_values", return_value={
            "GEMINI_API_KEY": "file-key", "GEMINI_MODEL": " gemini-3.8-flash ",
        }), patch.dict(os.environ, {"GEMINI_API_KEY": "environment-key"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.gemini_api_key.get_secret_value(), "environment-key")
        self.assertTrue(settings.interpretation_configured)
        self.assertEqual(settings.inference_model, DEFAULT_GEMINI_MODEL)
        self.assertNotIn("environment-key", repr(settings))
        for key in (None, "", "  ", "your_key_here"):
            self.assertFalse(Settings(gemini_api_key=key).interpretation_configured)
        for kwargs in ({"gemini_model": "../secret?key=oops"}, {"gemini_model": "gemini-x:other"},
                       {"gemini_timeout_seconds": 0}, {"gemini_timeout_seconds": float("nan")},
                       {"gemini_max_output_tokens": 0}):
            with self.assertRaises(ValidationError):
                Settings(**kwargs)

    def test_real_adapter_chat_clarification_and_sources_without_a_server(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=completion())
        interpreter = adapter(handler)
        with patch("pharmacy_assistant.api.create_interpreter", return_value=interpreter), \
             TestClient(create_app(settings=interpreter.settings)) as client:
            initial = client.post("/chat", json={"text": TEXT})
            self.assertEqual(initial.status_code, 200)
            body = initial.json()
            self.assertEqual(body["inference"]["provider"], "gemini")
            self.assertEqual(body["status"], "needs_clarification")
            self.assertEqual({c["ppv_price_mad"] for c in body["medications"][0]["candidates"]}, {268, 372})
            selected = client.post("/chat", json={"continuation_id": body["continuation_id"],
                                   "selections": [{"mention_index": 0, "record_id": "9080"}]}).json()
            self.assertEqual(selected["status"], "answered")
            self.assertFalse(selected["inference_performed"])
            self.assertIn("372.00 MAD", selected["answer"])
            self.assertEqual(selected["medications"][0]["stock_status"], "unknown")
            self.assertEqual(selected["sources"][0]["source"], "AMMPS")
        self.assertEqual(len(calls), 1)


class GeminiAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_schema_request_and_actual_usage_with_thoughts_excluded(self):
        calls = []
        def handler(request):
            calls.append(request)
            body = completion()
            body["candidates"][0]["content"]["parts"].insert(0, {"thought": True, "text": "PRIVATE_REASONING"})
            return httpx.Response(200, json=body)
        interpreter = adapter(handler)
        try:
            result = await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(len(calls), 1)
        request = calls[0]
        self.assertEqual(str(request.url), f"{GEMINI_BASE_URL}/{DEFAULT_GEMINI_MODEL}:generateContent")
        self.assertEqual(request.headers["x-goog-api-key"], "offline-gemini-key")
        self.assertNotIn("Authorization", request.headers)
        self.assertFalse(request.url.query)
        payload = json.loads(request.content)
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], TEXT)
        output = payload["generationConfig"]["responseFormat"]["text"]
        self.assertEqual(output["mimeType"], "APPLICATION_JSON")
        self.assertFalse(output["schema"]["additionalProperties"])
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "LOW")
        self.assertNotIn("DO_NOT_SEND", request.content.decode())
        self.assertEqual(result.metadata.model, "gemini-3.8-flash-test-version")
        self.assertEqual(result.metadata.provider, "gemini")
        self.assertEqual(result.metadata.usage.total_tokens, 170)
        self.assertEqual(result.metadata.usage.completion_tokens, 50)
        self.assertNotIn("PRIVATE_REASONING", result.model_dump_json())

    async def test_auth_permission_model_schema_redirect_and_long_retry_are_not_retried(self):
        for status, code in ((400, "provider_request_rejected"), (401, "provider_authentication_failed"),
                             (403, "provider_permission_denied"), (404, "provider_model_unavailable"),
                             (302, "provider_request_rejected"), (429, "provider_rate_limited")):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={"error": {"message": "SENSITIVE_BODY"}},
                                      headers={"retry-after": "30", "location": "https://other.invalid"})
            interpreter = adapter(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 1)
            self.assertNotIn("SENSITIVE", str(caught.exception))

    async def test_google_invalid_key_error_and_retry_info(self):
        for status, detail, code, delay in (
            (400, {"reason": "API_KEY_INVALID"}, "provider_authentication_failed", None),
            (400, {"reason": []}, "provider_request_rejected", None),
            (429, {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "35.5s"}, "provider_rate_limited", 35.5),
        ):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={"error": {"details": [detail]}})
            interpreter = adapter(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(caught.exception.detail.retry_after_seconds, delay)
            self.assertEqual(len(calls), 1)

    async def test_short_rate_limit_cooldown_is_not_automatically_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, headers={"retry-after": "2"}) if len(calls) == 1 else httpx.Response(200, json=completion())
        interpreter = adapter(handler)
        try:
            with patch("pharmacy_assistant.gemini_nlu.asyncio.sleep", new_callable=AsyncMock) as sleep:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
                sleep.assert_not_awaited()
        finally:
            await interpreter.close()
        self.assertEqual(len(calls), 1)
        self.assertEqual(caught.exception.detail.retry_after_seconds, 2)

    async def test_persistent_network_server_and_timeout_failures_stop_after_two(self):
        for kind, code in (("server", "provider_unavailable"), ("network", "provider_unreachable"),
                           ("timeout", "provider_timeout")):
            calls = []
            def handler(request):
                calls.append(request)
                if kind == "server":
                    return httpx.Response(503)
                if kind == "network":
                    raise httpx.ConnectError("PRIVATE", request=request)
                raise httpx.ReadTimeout("PRIVATE", request=request)
            interpreter = adapter(handler)
            try:
                with patch("pharmacy_assistant.gemini_nlu.asyncio.sleep", new_callable=AsyncMock):
                    with self.assertRaises(InferenceError) as caught:
                        await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 2)

    async def test_refusals_truncation_malformed_and_invented_entities_are_rejected(self):
        invented = extraction()
        invented["entities"]["medications"][0]["strength"] = "99mg"
        bad = completion()
        bad["candidates"][0]["content"]["parts"][0]["text"] = "```json\n{}\n```"
        truncated = completion()
        truncated["candidates"][0]["finishReason"] = "MAX_TOKENS"
        refused = completion()
        refused["candidates"][0]["finishReason"] = "SAFETY"
        missing_model = completion()
        missing_model.pop("modelVersion")
        for body, code in ((completion(invented), "provider_invalid_response"), (bad, "provider_invalid_response"),
                           (truncated, "provider_invalid_response"), (refused, "provider_refused"),
                           ({"promptFeedback": {"blockReason": "SAFETY"}}, "provider_refused"),
                           (missing_model, "provider_invalid_response"), ({"candidates": []}, "provider_invalid_response")):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=copy.deepcopy(body))
            interpreter = adapter(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 1)

    async def test_hard_deadline_is_bounded_even_without_transport_timeout(self):
        async def handler(request):
            await asyncio.Event().wait()
        interpreter = adapter(handler, gemini_timeout_seconds=1)
        try:
            with patch("pharmacy_assistant.gemini_nlu.asyncio.sleep", new_callable=AsyncMock):
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(caught.exception.detail.code, "provider_timeout")


if __name__ == "__main__":
    unittest.main()
