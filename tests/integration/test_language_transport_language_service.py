import socket
import threading
import time
import unittest
from fastapi.testclient import TestClient
import uvicorn
from tests.support.runtime import core_app as create_app
from pharmacy_core.config import CoreSettings
from pharmacy_language.config import LanguageSettings
from tests.support.runtime import language_app, CORE_URL, LANGUAGE_URL

class ServiceConfigurationTests(unittest.TestCase):

    def test_real_loopback_http_to_an_independent_language_server(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(32)
        url = f'http://127.0.0.1:{listener.getsockname()[1]}'
        app = language_app(LanguageSettings(language_database_url=LANGUAGE_URL, inference_provider='groq'))
        server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and thread.is_alive() and (time.monotonic() < deadline):
                time.sleep(0.02)
            self.assertTrue(server.started)
            with TestClient(create_app(settings=CoreSettings(core_database_url=CORE_URL, language_service_url=url))) as core:
                health = core.get('/health').json()
                self.assertEqual(health['language_service_status'], 'available')
                self.assertFalse(health['interpretation_configured'])
                result = core.post('/chat', json={'text': 'Prix ABIP ?'})
                self.assertEqual(result.status_code, 503, result.text)
                self.assertEqual(result.json()['detail']['code'], 'model_not_configured')
                self.assertEqual(core.get('/medications/9080').status_code, 200)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            listener.close()
            self.assertFalse(thread.is_alive(), 'Ephemeral language server did not stop')
import asyncio
from contextlib import AsyncExitStack
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import groq
import httpx
from pharmacy_contracts.interpretation import InferenceError
from pharmacy_language.providers.groq import GroqInterpreter
from pharmacy_language.quota.control import AttemptControl
from tests.support.ledger import MemoryLedger
from pharmacy_core.clients.language import HttpInterpreter
from tests.support.groq import completion
TEXT = 'Wach kayn ABIP 15mg w bch7al?'

class LanguageHttpTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.stack = AsyncExitStack()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.provider_calls, self.wire_calls = ([], [])
        self.provider_entered = asyncio.Event()
        self.available, self.override, self.provider_mode = (True, None, 'ok')
        self.settings = LanguageSettings(language_database_url=LANGUAGE_URL, inference_provider='groq', groq_api_key='offline-private-key', groq_output_mode='json_object')

        async def hosted(request):
            self.provider_calls.append(request)
            self.provider_entered.set()
            if self.provider_mode == 'slow':
                await asyncio.sleep(10)
            if self.provider_mode == 'quota':
                return httpx.Response(429, headers={'retry-after': '120'}, json={'error': {'message': 'private-hosted-body'}})
            return httpx.Response(200, json=completion())
        sdk = groq.AsyncGroq(api_key='offline-private-key', max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(hosted)))
        self.control = AttemptControl(MemoryLedger(), 'offline:groq:test', 0)
        self.provider = GroqInterpreter(self.settings, client=sdk, control=self.control)
        self.stack.enter_context(patch('pharmacy_language.api.app.create_interpreter', return_value=self.provider))
        self.language = language_app(self.settings)
        await self.stack.enter_async_context(self.language.router.lifespan_context(self.language))
        self.language_http = await self.stack.enter_async_context(httpx.AsyncClient(transport=httpx.ASGITransport(app=self.language), base_url='http://language'))

        async def dispatch(request):
            self.wire_calls.append(request)
            if not self.available:
                raise httpx.ConnectError('private-connection-details', request=request)
            if self.override is not None and request.method == 'POST':
                return self.override(request)
            return await self.language_http.request(request.method, request.url.path, content=request.content, headers={'content-type': 'application/json'})
        self.core_settings = CoreSettings(core_database_url=CORE_URL, language_service_url='http://language')
        self.remote = HttpInterpreter(self.core_settings, httpx.AsyncClient(transport=httpx.MockTransport(dispatch)))
        self.stack.enter_context(patch('pharmacy_core.api.app.create_interpreter', return_value=self.remote))
        self.core = create_app(settings=self.core_settings)
        await self.stack.enter_async_context(self.core.router.lifespan_context(self.core))
        self.http = await self.stack.enter_async_context(httpx.AsyncClient(transport=httpx.ASGITransport(app=self.core), base_url='http://core'))

    async def asyncTearDown(self):
        await self.stack.aclose()

    async def test_two_services_preserve_grounding_and_only_send_current_message(self):
        health = (await self.http.get('/health')).json()
        self.assertEqual(health['language_service_status'], 'available')
        self.assertTrue(health['interpretation_configured'])
        self.assertEqual(len(self.provider_calls), 0)
        first = await self.http.post('/chat', json={'text': TEXT})
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertEqual(body['status'], 'needs_clarification')
        selected = await self.http.post('/chat', json={'continuation_id': body['continuation_id'], 'selections': [{'mention_index': 0, 'record_id': '9080'}]})
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertIn('372.00 MAD', selected.json()['answer'])
        self.assertFalse(selected.json()['inference_performed'])
        posts = [r for r in self.wire_calls if r.method == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].url.path, '/v1/interpret')
        self.assertEqual(json.loads(posts[0].content), {'text': TEXT})
        self.assertNotIn('authorization', posts[0].headers)
        self.assertEqual(len(self.provider_calls), 1)

    async def test_language_failure_preserves_pending_choices_and_catalogue(self):
        first = (await self.http.post('/chat', json={'text': TEXT})).json()
        self.available = False
        failed = await self.http.post('/chat', json={'text': 'Et deux boites ?', 'session_id': first['session_id']})
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.json()['detail']['code'], 'language_unavailable')
        self.assertNotIn('private', failed.text)
        self.assertEqual((await self.http.get('/health')).json()['language_service_status'], 'unavailable')
        self.assertEqual((await self.http.get('/medications/9080')).status_code, 200)
        before = len(self.wire_calls)
        selected = await self.http.post('/chat', json={'continuation_id': first['continuation_id'], 'selections': [{'mention_index': 0, 'record_id': '9080'}]})
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertFalse(selected.json()['inference_performed'])
        self.assertEqual(len(self.wire_calls), before)
        self.assertEqual(len(self.provider_calls), 1)

    async def test_quota_cooldown_crosses_http_without_replay_and_blocks_next_attempt(self):
        self.provider_mode = 'quota'
        for _ in range(2):
            result = await self.http.post('/interpret', json={'text': TEXT})
            self.assertEqual(result.status_code, 429, result.text)
            self.assertEqual(result.json()['detail']['code'], 'provider_rate_limited')
            self.assertGreaterEqual(int(result.headers['retry-after']), 119)
            self.assertNotIn('private', result.text)
        self.assertEqual(len(self.provider_calls), 1)
        self.assertEqual(self.control.store.status(self.control.scope)['local_attempts_reserved'], 1)

    async def test_readiness_checks_quota_without_a_provider_attempt(self):
        result = await self.language_http.get('/ready')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(self.provider_calls), 0)
        with patch.object(self.control.store, 'status', side_effect=InferenceError('quota_state_unavailable', 'private-db', 503)):
            result = await self.language_http.get('/ready')
            self.assertEqual(result.status_code, 503)
            self.assertNotIn('private-db', result.text)
        self.assertEqual(len(self.provider_calls), 0)

    async def test_malformed_success_and_invented_evidence_are_rejected(self):
        good = (await self.language_http.post('/v1/interpret', json={'text': TEXT})).json()
        for mode in ('json', 'extra', 'evidence', 'metadata', 'large', 'redirect'):
            body = json.loads(json.dumps(good))
            if mode == 'extra':
                body['price'] = 999
            elif mode == 'evidence':
                body['interpretation']['entities']['medications'][0]['name'] = 'INVENTED'
            elif mode == 'metadata':
                body['metadata']['latency_ms'] = float('nan')
            if mode == 'json':
                response = httpx.Response(200, text='private-not-json')
            elif mode == 'large':
                response = httpx.Response(200, content=b'x' * 65537)
            elif mode == 'redirect':
                response = httpx.Response(307, headers={'location': 'http://other-provider'})
            elif mode == 'metadata':
                response = httpx.Response(200, content=json.dumps(body).encode())
            else:
                response = httpx.Response(200, json=body)
            self.override = lambda request: response
            result = await self.http.post('/interpret', json={'text': TEXT})
            with self.subTest(mode=mode):
                self.assertEqual(result.status_code, 502, result.text)
                self.assertEqual(result.json()['detail']['code'], 'language_invalid_response')
                self.assertNotIn('private', result.text)

    async def test_remote_error_text_and_invalid_error_contract_never_leak(self):
        for code, status, delay in (('provider_unavailable', 503, None), ('unknown', 503, None), ('provider_rate_limited', 429, -1), ('provider_rate_limited', 503, 120)):
            self.override = lambda request: httpx.Response(status, json={'detail': {'code': code, 'message': 'private-password-and-patient', 'retryable': True, 'retry_after_seconds': delay}})
            result = await self.http.post('/interpret', json={'text': TEXT})
            self.assertEqual(result.status_code, 503 if code == 'provider_unavailable' else 502)
            self.assertNotIn('private', result.text)

    async def test_transport_timeout_is_single_attempt_and_completion_is_uncertain(self):

        def timed_out(request):
            raise httpx.ReadTimeout('private-body', request=request)
        self.override = timed_out
        before = len(self.wire_calls)
        result = await self.http.post('/interpret', json={'text': TEXT})
        self.assertEqual(result.status_code, 504)
        self.assertEqual(result.json()['detail']['code'], 'language_timeout')
        self.assertIn('comptabilisée', result.json()['detail']['message'])
        self.assertEqual(len(self.wire_calls), before + 1)
        self.assertEqual(len(self.provider_calls), 0)

    async def test_language_total_deadline_stops_without_a_second_provider_attempt(self):
        self.provider_mode = 'slow'
        deadline = asyncio.timeout(None)
        with patch('pharmacy_language.api.app.asyncio.timeout', return_value=deadline):
            task = asyncio.create_task(self.language_http.post('/v1/interpret', json={'text': TEXT}))
            try:
                await asyncio.wait_for(self.provider_entered.wait(), timeout=10)
                deadline.reschedule(asyncio.get_running_loop().time())
                result = await asyncio.wait_for(task, timeout=10)
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(result.status_code, 504, result.text)
        self.assertEqual(result.json()['detail']['code'], 'language_timeout')
        self.assertEqual(len(self.provider_calls), 1)
        self.assertEqual(self.control.store.status(self.control.scope)['local_attempts_reserved'], 1)

    async def test_invalid_request_never_calls_provider_or_echoes_patient_input(self):
        result = await self.language_http.post('/v1/interpret', json={'text': 'private-patient', 'unknown': True})
        self.assertEqual(result.status_code, 422)
        self.assertNotIn('private-patient', result.text)
        self.assertEqual(len(self.provider_calls), 0)
