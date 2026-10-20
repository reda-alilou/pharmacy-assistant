import os
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from pharmacy_language.config import DEFAULT_OPENCODE_MODEL
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.extraction.service import create_interpreter
from pharmacy_language.providers.groq import GroqInterpreter
from pharmacy_language.providers.opencode import OpenCodeInterpreter

class OpenCodeConfigTests(unittest.TestCase):

    def test_provider_selection_and_selected_key_are_independent(self):
        settings = Settings(inference_provider='opencode', groq_api_key='old-groq-key')
        self.assertEqual(settings.inference_provider, 'opencode')
        self.assertEqual(settings.inference_model, DEFAULT_OPENCODE_MODEL)
        self.assertFalse(settings.interpretation_configured)
        self.assertIsInstance(create_interpreter(settings), OpenCodeInterpreter)
        self.assertIsInstance(create_interpreter(Settings(inference_provider='groq')), GroqInterpreter)
        self.assertFalse(Settings(inference_provider='groq', opencode_api_key='some-key').interpretation_configured)
        self.assertNotIn('old-groq-key', repr(settings))

    def test_env_selection_and_validation(self):
        values = {'INFERENCE_PROVIDER': 'opencode', 'OPENCODE_API_KEY': 'file-key', 'OPENCODE_OUTPUT_MODE': 'json_object', 'OPENCODE_MODEL': ' glm-5.3-flash-free '}
        with patch('pharmacy_infrastructure.environment.dotenv_values', return_value=values), patch.dict(os.environ, {'OPENCODE_API_KEY': 'environment-key'}, clear=True):
            settings = Settings.from_env()
        self.assertTrue(settings.interpretation_configured)
        self.assertEqual(settings.opencode_api_key.get_secret_value(), 'environment-key')
        self.assertEqual(settings.inference_output_mode, 'json_object')
        self.assertEqual(settings.inference_model, DEFAULT_OPENCODE_MODEL)
        for kwargs in ({'inference_provider': 'unknown'}, {'opencode_output_mode': 'automatic'}, {'opencode_timeout_seconds': 0}, {'opencode_timeout_seconds': float('nan')}):
            with self.assertRaises(ValidationError):
                Settings(**kwargs)
import asyncio
import json
from unittest.mock import AsyncMock, patch
import httpx
from pharmacy_language.config import DEFAULT_OPENCODE_MODEL, OPENCODE_BASE_URL
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.providers.groq import InferenceError
from pharmacy_contracts.interpretation import InterpretationRequest
from tests.support.groq import completion, extraction
TEXT = 'Wach kayn ABIP 15mg w bch7al?'

def glm_completion(**kwargs):
    return {**completion(**kwargs), 'model': 'glm-5.3-flash'}

def adapter(handler, **kwargs):
    settings = Settings(inference_provider='opencode', opencode_api_key='offline-opencode-key', groq_api_key='DO_NOT_SEND_GROQ_KEY', **kwargs)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenCodeInterpreter(settings, client=client)

class OpenCodeAdapterTests(unittest.IsolatedAsyncioTestCase):

    async def test_strict_request_endpoint_credentials_and_actual_metadata(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=glm_completion())
        interpreter = adapter(handler)
        try:
            result = await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(len(calls), 1)
        self.assertEqual(str(calls[0].url), OPENCODE_BASE_URL + '/chat/completions')
        self.assertEqual(calls[0].headers['Authorization'], 'Bearer offline-opencode-key')
        payload = json.loads(calls[0].content)
        self.assertEqual(payload['model'], DEFAULT_OPENCODE_MODEL)
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['reasoning_effort'], 'low')
        self.assertNotIn('DO_NOT_SEND_GROQ_KEY', calls[0].content.decode())
        self.assertEqual(result.metadata.provider, 'opencode')
        self.assertEqual(result.metadata.output_mode, 'json_schema')
        self.assertEqual(result.metadata.model, 'glm-5.3-flash')
        self.assertEqual(result.metadata.requested_model, DEFAULT_OPENCODE_MODEL)
        self.assertEqual(result.metadata.usage.total_tokens, 150)

    async def test_json_object_requires_explicit_configuration_and_keeps_local_validation(self):
        calls = []

        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json=glm_completion())
        interpreter = adapter(handler, opencode_output_mode='json_object')
        try:
            result = await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(calls[0]['response_format'], {'type': 'json_object'})
        self.assertIn('"additionalProperties": false', calls[0]['messages'][0]['content'])
        self.assertEqual(result.metadata.output_mode, 'json_object')

    async def test_bad_schema_auth_payment_redirect_and_long_cooldown_have_no_fallback(self):
        for status, code in ((400, 'provider_request_rejected'), (401, 'provider_authentication_failed'), (402, 'provider_payment_required'), (403, 'provider_permission_denied'), (302, 'provider_request_rejected'), (429, 'provider_rate_limited')):
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={'error': {'message': 'SENSITIVE_PROVIDER_BODY'}}, headers={'retry-after': '30', 'location': 'https://other.invalid/steal'})
            interpreter = adapter(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('SENSITIVE', str(caught.exception))

    async def test_transient_error_retries_only_once_and_records_success(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=glm_completion())
        interpreter = adapter(handler)
        try:
            with patch('pharmacy_language.providers.opencode.asyncio.sleep', new_callable=AsyncMock) as sleep:
                result = await interpreter.interpret(InterpretationRequest(text=TEXT))
                sleep.assert_awaited_once_with(1)
        finally:
            await interpreter.close()
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.metadata.attempts, 2)

    async def test_free_tier_restriction_is_actionable_and_not_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(403, json={'type': 'error', 'error': {'type': 'FreeTierError', 'message': 'PRIVATE_PROVIDER_ERROR_BODY'}})
        interpreter = adapter(handler)
        try:
            with self.assertRaises(InferenceError) as caught:
                await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(caught.exception.detail.code, 'provider_free_tier_restricted')
        self.assertFalse(caught.exception.detail.retryable)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('PRIVATE', caught.exception.detail.message)

    async def test_persistent_generation_connection_and_timeout_errors_stop_after_two(self):
        for kind, code in (('generation', 'provider_generation_failed'), ('connection', 'provider_unreachable'), ('timeout', 'provider_timeout')):
            calls = []

            def handler(request):
                calls.append(request)
                if kind == 'generation':
                    return httpx.Response(400, json={'error': {'code': 'json_validate_failed'}})
                if kind == 'connection':
                    raise httpx.ConnectError('SENSITIVE', request=request)
                raise httpx.ReadTimeout('SENSITIVE', request=request)
            interpreter = adapter(handler)
            try:
                with patch('pharmacy_language.providers.opencode.asyncio.sleep', new_callable=AsyncMock):
                    with self.assertRaises(InferenceError) as caught:
                        await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 2)

    async def test_invalid_entities_refusal_truncation_and_missing_metadata_are_rejected(self):
        invented = extraction()
        invented['entities']['medications'][0]['strength'] = '99mg'
        missing_model = glm_completion()
        missing_model.pop('model')
        malformed = glm_completion()
        malformed['choices'][0]['message']['content'] = '```json\n{}\n```'
        for body, code in ((glm_completion(data=invented), 'provider_invalid_response'), (glm_completion(finish='length'), 'provider_invalid_response'), (glm_completion(refusal='no'), 'provider_refused'), (missing_model, 'provider_invalid_response'), (malformed, 'provider_invalid_response')):
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=body)
            interpreter = adapter(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 1)

    async def test_hard_deadline_is_bounded(self):

        async def handler(request):
            await asyncio.Event().wait()
        interpreter = adapter(handler, opencode_timeout_seconds=1)
        try:
            with patch('pharmacy_language.providers.opencode.asyncio.sleep', new_callable=AsyncMock):
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(caught.exception.detail.code, 'provider_timeout')
