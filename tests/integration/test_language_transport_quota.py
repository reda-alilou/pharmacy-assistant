from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from tests.support.runtime import language_app as create_app
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.quota.control import AttemptControl
from tests.support.ledger import MemoryLedger
from tests.support.gemini import TEXT, completion

class QuotaApiTests(unittest.TestCase):

    def test_factory_api_spacing_preserves_lookup_and_retry_after_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(gemini_api_key='offline-key', inference_min_interval_seconds=30)
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=completion())
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch('pharmacy_language.providers.gemini.httpx.AsyncClient', return_value=http_client), TestClient(create_app(settings=settings, store=MemoryLedger())) as client:
                self.assertEqual(client.post('/v1/interpret', json={'text': TEXT}).status_code, 200)
                result = client.post('/v1/interpret', json={'text': TEXT})
                self.assertEqual(result.status_code, 429)
                self.assertEqual(result.json()['detail']['code'], 'local_rate_limited')
                self.assertGreater(int(result.headers['retry-after']), 0)
                self.assertNotIn('offline-key', result.text)
                self.assertEqual(client.get('/health').status_code, 200)
            self.assertEqual(len(calls), 1)

    def test_default_allows_back_to_back_requests_and_ignores_old_spacing(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(gemini_api_key='offline-key')
            self.assertEqual(settings.inference_min_interval_seconds, 0)
            store = MemoryLedger()
            control = AttemptControl(store, f'{settings.inference_quota_scope}:{settings.inference_provider}:{settings.inference_model}', 0)
            control.store.reserve(control.scope, 30)
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=completion())
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch('pharmacy_language.providers.gemini.httpx.AsyncClient', return_value=http_client), TestClient(create_app(settings=settings, store=store)) as client:
                for _ in range(2):
                    result = client.post('/v1/interpret', json={'text': TEXT})
                    self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(len(calls), 2)
