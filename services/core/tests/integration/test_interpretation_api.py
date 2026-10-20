import json
import unittest
import groq
import httpx
from tests.support.services import connected_apps
from pharmacy_language.config import DEFAULT_MODEL
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.providers.groq import GroqInterpreter

def extraction():
    return {'language': 'darija', 'reply_language': 'darija', 'reply_script': 'latin', 'intents': ['price', 'availability'], 'entities': {'medications': [{'name': 'ABIP', 'strength': '15mg', 'quantity': None, 'form': None, 'presentation': None}], 'pharmacy': None, 'city': None, 'area': None, 'date': None, 'time': None, 'symptom': None}}

def completion(data=None, finish='stop', **message_extra):
    return {'id': 'offline-completion', 'object': 'chat.completion', 'created': 1, 'model': DEFAULT_MODEL, 'choices': [{'index': 0, 'finish_reason': finish, 'message': {'role': 'assistant', 'content': json.dumps(data or extraction()), **message_extra}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}}

def interpreter_for(handler, output_mode='json_schema'):
    settings = Settings(inference_provider='groq', groq_api_key='offline-test-key', groq_output_mode=output_mode)
    client = groq.AsyncGroq(api_key=settings.groq_api_key.get_secret_value(), max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return GroqInterpreter(settings, client=client)

class InterpretationApiTests(unittest.TestCase):

    def test_unconfigured_api_keeps_catalogue_working_and_returns_actionable_error(self):
        with connected_apps(Settings()) as client:
            health = client.get('/health').json()
            self.assertFalse(health['interpretation_configured'])
            self.assertEqual(client.get('/medications/search', params={'query': 'ABIP'}).status_code, 200)
            result = client.post('/interpret', json={'text': 'Bch7al ABIP?'})
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()['detail']['code'], 'model_not_configured')

    def test_input_validation_precedes_inference(self):
        with connected_apps(Settings()) as client:
            for body in ({}, {'text': '  '}, {'text': 'x' * 2001}, {'text': 123}, {'text': 'ABIP', 'unknown': True}):
                self.assertEqual(client.post('/interpret', json=body).status_code, 422)

    def test_real_api_response_and_secret_redaction(self):
        interpreter = interpreter_for(lambda request: httpx.Response(200, json=completion()))
        with connected_apps(interpreter.settings, interpreter) as client:
            result = client.post('/interpret', json={'text': 'Wach kayn ABIP 15mg w bch7al?'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['interpretation']['intents'], ['price', 'availability'])
            self.assertNotIn('offline-test-key', result.text)
            self.assertNotIn('offline-test-key', client.get('/health').text)

    def test_rate_limit_response_propagates_cooldown_without_provider_body(self):
        interpreter = interpreter_for(lambda request: httpx.Response(429, headers={'retry-after': '120'}, json={'error': {'message': 'SECRET_KEY_AND_PATIENT_TEXT'}}))
        with connected_apps(interpreter.settings, interpreter) as client:
            result = client.post('/interpret', json={'text': 'ABIP'})
            self.assertEqual(result.status_code, 429)
            self.assertEqual(result.headers['retry-after'], '120')
            self.assertNotIn('SECRET', result.text)
