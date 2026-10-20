import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from tests.support.configuration import FixtureSettings as Settings

class ConfigurationTests(unittest.TestCase):

    def test_configuration_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('GROQ_API_KEY=file-test-key\nGROQ_MODEL=file-model\nGROQ_TIMEOUT_SECONDS=12\n', encoding='utf-8')
            with patch.dict(os.environ, {'GROQ_MODEL': 'environment-model'}, clear=True):
                settings = Settings.from_env(path)
            self.assertEqual(settings.groq_api_key.get_secret_value(), 'file-test-key')
            self.assertEqual(settings.groq_model, 'environment-model')
            self.assertEqual(settings.groq_timeout_seconds, 12)
            self.assertNotIn('file-test-key', repr(settings))
            with patch.dict(os.environ, {'GROQ_API_KEY': ''}, clear=True):
                self.assertFalse(Settings.from_env(path).interpretation_configured)

    def test_blank_placeholder_and_invalid_settings(self):
        for value in (None, '', '   ', 'your_key_here'):
            self.assertFalse(Settings(inference_provider='groq', groq_api_key=value).interpretation_configured)
        for value in (0, 61, float('nan')):
            with self.assertRaises(ValidationError):
                Settings(groq_timeout_seconds=value)
import asyncio
import json
from unittest.mock import AsyncMock, patch
import groq
import httpx
from pharmacy_language.config import DEFAULT_MODEL
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.providers.groq import GroqInterpreter, InferenceError
from pharmacy_contracts.interpretation import Interpretation, InterpretationRequest

def extraction():
    return {'language': 'darija', 'reply_language': 'darija', 'reply_script': 'latin', 'intents': ['price', 'availability'], 'entities': {'medications': [{'name': 'ABIP', 'strength': '15mg', 'quantity': None, 'form': None, 'presentation': None}], 'pharmacy': None, 'city': None, 'area': None, 'date': None, 'time': None, 'symptom': None}}

def completion(data=None, finish='stop', **message_extra):
    return {'id': 'offline-completion', 'object': 'chat.completion', 'created': 1, 'model': DEFAULT_MODEL, 'choices': [{'index': 0, 'finish_reason': finish, 'message': {'role': 'assistant', 'content': json.dumps(data or extraction()), **message_extra}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}}

def interpreter_for(handler, output_mode='json_schema'):
    settings = Settings(inference_provider='groq', groq_api_key='offline-test-key', groq_output_mode=output_mode)
    client = groq.AsyncGroq(api_key=settings.groq_api_key.get_secret_value(), max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return GroqInterpreter(settings, client=client)

class InterpretationTests(unittest.IsolatedAsyncioTestCase):

    async def test_explicit_json_mode_sends_schema_in_prompt_and_reports_actual_mode(self):
        requests = []

        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=completion())
        interpreter = interpreter_for(handler, 'json_object')
        try:
            result = await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
        finally:
            await interpreter.close()
        self.assertEqual(requests[0]['response_format'], {'type': 'json_object'})
        self.assertIn('"additionalProperties":false', requests[0]['messages'][0]['content'])
        self.assertEqual(result.metadata.output_mode, 'json_object')
        self.assertEqual(interpreter.settings.inference_output_mode, 'json_object')
        self.assertEqual(result.interpretation.entities.medications[0].name, 'ABIP')

    async def test_json_mode_still_rejects_invented_entities_extra_fields_and_wrong_schema(self):
        for fault in ('invented', 'extra', 'wrong_schema'):
            data = extraction()
            if fault == 'invented':
                data['entities']['medications'][0]['name'] = 'INVENTED999'
            elif fault == 'extra':
                data['model_price'] = 123
            else:
                data['entities']['medications'] = None
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=completion(data))
            interpreter = interpreter_for(handler, 'json_object')
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, 'provider_invalid_response')
            self.assertEqual(len(calls), 1)

    async def test_actual_sdk_sends_schema_and_returns_measured_metadata(self):
        requests = []

        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=completion())
        interpreter = interpreter_for(handler)
        try:
            response = await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
        finally:
            await interpreter.close()
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request['model'], DEFAULT_MODEL)
        self.assertEqual(request['reasoning_effort'], 'none')
        self.assertEqual(request['response_format']['type'], 'json_schema')
        schema = request['response_format']['json_schema']
        self.assertTrue(schema['strict'])
        for shape in [schema['schema'], *schema['schema']['$defs'].values()]:
            if shape.get('type') == 'object':
                self.assertFalse(shape['additionalProperties'])
                self.assertEqual(set(shape['required']), set(shape['properties']))
        self.assertEqual(response.interpretation.entities.medications[0].name, 'ABIP')
        self.assertIsNone(response.interpretation.entities.medications[0].quantity)
        self.assertEqual(response.metadata.usage.total_tokens, 150)
        self.assertEqual(response.metadata.attempts, 1)
        self.assertGreaterEqual(response.metadata.latency_ms, 0)

    async def test_missing_key_never_sends_a_request(self):
        interpreter = GroqInterpreter(Settings())
        with self.assertRaises(InferenceError) as caught:
            await interpreter.interpret(InterpretationRequest(text='Bch7al?'))
        self.assertEqual(caught.exception.detail.code, 'model_not_configured')

    async def test_transient_error_has_one_retry_without_sdk_multiplication(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503, json={'error': {'message': 'temporary'}})
        interpreter = interpreter_for(handler)
        try:
            with patch('pharmacy_language.providers.groq.asyncio.sleep', new_callable=AsyncMock) as sleep:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text='ABIP'))
                sleep.assert_awaited_once_with(1)
        finally:
            await interpreter.close()
        self.assertEqual(len(calls), 2)
        self.assertEqual(caught.exception.status_code, 503)

    async def test_successful_retry_is_recorded(self):
        count = 0

        def handler(request):
            nonlocal count
            count += 1
            if count == 1:
                return httpx.Response(503, headers={'retry-after': '0.5'}, json={'error': {'message': 'unavailable'}})
            return httpx.Response(200, json=completion())
        interpreter = interpreter_for(handler)
        try:
            with patch('pharmacy_language.providers.groq.asyncio.sleep', new_callable=AsyncMock) as sleep:
                result = await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
                sleep.assert_awaited_once_with(0.5)
        finally:
            await interpreter.close()
        self.assertEqual(result.metadata.attempts, 2)
        self.assertEqual(count, 2)

    async def test_provider_json_generation_failure_gets_only_one_retry(self):
        for persistent in (False, True):
            calls = []

            def handler(request):
                calls.append(request)
                if persistent or len(calls) == 1:
                    return httpx.Response(400, json={'error': {'code': 'json_validate_failed', 'message': 'SENSITIVE_PROVIDER_TEXT'}})
                return httpx.Response(200, json=completion())
            interpreter = interpreter_for(handler)
            try:
                with patch('pharmacy_language.providers.groq.asyncio.sleep', new_callable=AsyncMock):
                    if persistent:
                        with self.assertRaises(InferenceError) as caught:
                            await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
                        self.assertEqual(caught.exception.detail.code, 'provider_generation_failed')
                        self.assertEqual(caught.exception.status_code, 502)
                    else:
                        result = await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
                        self.assertEqual(result.metadata.attempts, 2)
            finally:
                await interpreter.close()
            self.assertEqual(len(calls), 2)

    async def test_auth_permission_bad_model_and_long_rate_limit_are_not_retried(self):
        for status, code in [(401, 'provider_authentication_failed'), (403, 'provider_permission_denied'), (400, 'provider_request_rejected'), (429, 'provider_rate_limited')]:
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers={'retry-after': '120'}, json={'error': {'message': 'SENSITIVE_PROVIDER_TEXT'}})
            interpreter = interpreter_for(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text='ABIP'))
            finally:
                await interpreter.close()
            self.assertEqual(len(calls), 1)
            self.assertEqual(caught.exception.detail.code, code)
            self.assertNotIn('SENSITIVE', str(caught.exception))

    async def test_connection_and_timeout_errors_have_bounded_retry(self):
        for kind, code in [(httpx.ConnectError, 'provider_unreachable'), (httpx.ReadTimeout, 'provider_timeout')]:
            calls = []

            def handler(request):
                calls.append(request)
                raise kind('SENSITIVE_TRANSPORT_TEXT', request=request)
            interpreter = interpreter_for(handler)
            try:
                with patch('pharmacy_language.providers.groq.asyncio.sleep', new_callable=AsyncMock):
                    with self.assertRaises(InferenceError) as caught:
                        await interpreter.interpret(InterpretationRequest(text='ABIP'))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 2)

    async def test_invalid_truncated_refused_or_invented_outputs_are_rejected(self):
        invented = extraction()
        invented['entities']['medications'][0]['strength'] = '20mg'
        wrong_intent = extraction()
        wrong_intent['intents'] = ['diagnose']
        duplicate = extraction()
        duplicate['intents'] = ['price', 'price']
        malformed = completion()
        malformed['choices'][0]['message']['content'] = 'not json'
        for payload, code in [(completion(invented), 'provider_invalid_response'), (completion(wrong_intent), 'provider_invalid_response'), (completion(duplicate), 'provider_invalid_response'), (completion(finish='length'), 'provider_invalid_response'), (completion(refusal='Declined'), 'provider_refused'), (malformed, 'provider_invalid_response'), ({**completion(), 'choices': []}, 'provider_invalid_response')]:
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=payload)
            interpreter = interpreter_for(handler)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text='Wach kayn ABIP 15mg w bch7al?'))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, code)
            self.assertEqual(len(calls), 1)

    async def test_hard_deadline_is_enforced(self):

        async def handler(request):
            await asyncio.Event().wait()
        interpreter = interpreter_for(handler)
        interpreter.settings = Settings(groq_api_key='offline-test-key', groq_timeout_seconds=1)
        try:
            with patch('pharmacy_language.providers.groq.asyncio.sleep', new_callable=AsyncMock):
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text='ABIP'))
        finally:
            await interpreter.close()
        self.assertEqual(caught.exception.status_code, 504)

    def test_multiple_medications_and_incomplete_requests(self):
        data = extraction()
        data['entities']['medications'].append({'name': 'AIRCORT', 'strength': None, 'quantity': 'deux boîtes', 'form': None, 'presentation': None})
        result = Interpretation.model_validate(data)
        result.validate_evidence('ABIP 15mg et deux boîtes de AIRCORT')
        self.assertEqual(len(result.entities.medications), 2)
        data['entities']['medications'] = []
        data['intents'] = ['price']
        Interpretation.model_validate(data).validate_evidence('Bch7al?')
