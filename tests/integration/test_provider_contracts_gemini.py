import json
import unittest
import httpx
from tests.support.services import connected_apps
from pharmacy_language.config import DEFAULT_GEMINI_MODEL
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.providers.gemini import GeminiInterpreter
from pharmacy_language.extraction.service import create_interpreter
from tests.support.groq import extraction
TEXT = 'Wach kayn ABIP 15mg w bch7al?'

def completion(data=None):
    return {'candidates': [{'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': json.dumps(data or extraction())}]}}], 'modelVersion': 'gemini-3.8-flash-test-version', 'responseId': 'offline-gemini', 'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 50, 'thoughtsTokenCount': 20, 'totalTokenCount': 170}}

def adapter(handler, **kwargs):
    settings = Settings(gemini_api_key='offline-gemini-key', groq_api_key='DO_NOT_SEND_GROQ', opencode_api_key='DO_NOT_SEND_OPENCODE', **kwargs)
    return GeminiInterpreter(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

class GeminiConfigTests(unittest.TestCase):

    def test_default_selection_key_isolation_and_health(self):
        settings = Settings(groq_api_key='unused-groq', opencode_api_key='unused-opencode')
        self.assertEqual(settings.inference_provider, 'gemini')
        self.assertEqual(settings.inference_model, DEFAULT_GEMINI_MODEL)
        self.assertEqual(settings.inference_key_name, 'GEMINI_API_KEY')
        self.assertEqual(settings.inference_output_mode, 'json_schema')
        self.assertFalse(settings.interpretation_configured)
        self.assertIsInstance(create_interpreter(settings), GeminiInterpreter)
        self.assertNotIn('unused-groq', repr(settings))
        with connected_apps(settings) as client:
            health = client.get('/health').json()
            self.assertEqual(health['interpretation_provider'], 'gemini')
            self.assertEqual(health['interpretation_model'], DEFAULT_GEMINI_MODEL)
            self.assertFalse(health['interpretation_configured'])
            result = client.post('/chat', json={'text': TEXT})
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()['detail']['code'], 'model_not_configured')
            self.assertNotIn('unused-', result.text)
            self.assertEqual(client.get('/medications/9079').status_code, 200)

    def test_real_adapter_chat_clarification_and_sources_without_a_server(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=completion())
        interpreter = adapter(handler)
        with connected_apps(interpreter.settings, interpreter) as client:
            initial = client.post('/chat', json={'text': TEXT})
            self.assertEqual(initial.status_code, 200)
            body = initial.json()
            self.assertEqual(body['inference']['provider'], 'gemini')
            self.assertEqual(body['status'], 'needs_clarification')
            self.assertEqual({c['ppv_price_mad'] for c in body['medications'][0]['candidates']}, {268, 372})
            selected = client.post('/chat', json={'continuation_id': body['continuation_id'], 'selections': [{'mention_index': 0, 'record_id': '9080'}]}).json()
            self.assertEqual(selected['status'], 'answered')
            self.assertFalse(selected['inference_performed'])
            self.assertIn('372.00 MAD', selected['answer'])
            self.assertEqual(selected['medications'][0]['stock_status'], 'unknown')
            self.assertEqual(selected['sources'][0]['source'], 'AMMPS')
        self.assertEqual(len(calls), 1)
