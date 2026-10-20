import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from tests.support.services import connected_apps
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_contracts.interpretation import InterpretationResponse, MedicationMention

def mention(name='ABIP', **kwargs):
    return MedicationMention(name=name, strength=kwargs.get('strength'), quantity=kwargs.get('quantity'), form=kwargs.get('form'), presentation=kwargs.get('presentation'))

def response(medications=None, intents=None, language='fr', script='latin', **context):
    return InterpretationResponse.model_validate({'interpretation': {'language': language, 'reply_language': language, 'reply_script': script, 'intents': intents or ['price'], 'entities': {'medications': [m.model_dump() for m in (medications if medications is not None else [mention()])], **{key: context.get(key) for key in ('pharmacy', 'city', 'area', 'date', 'time', 'symptom')}}}, 'metadata': {'requested_model': 'offline', 'model': 'offline', 'prompt_version': 'test', 'latency_ms': 1, 'attempts': 1, 'completion_id': None, 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}})

class ChatApiTests(unittest.TestCase):

    def test_http_clarification_serialization_and_selection_validation(self):
        fake = AsyncMock()
        fake.interpret.return_value = response()
        with patch('pharmacy_core.api.app.create_interpreter', return_value=fake):
            with TestClient(create_app(settings=Settings())) as client:
                initial = client.post('/chat', json={'text': 'Prix ABIP?'})
                self.assertEqual(initial.status_code, 200)
                body = initial.json()
                self.assertEqual(body['status'], 'needs_clarification')
                invalid = client.post('/chat', json={'continuation_id': body['continuation_id'], 'selections': [{'mention_index': 0, 'record_id': '771'}]})
                self.assertEqual(invalid.status_code, 422)
                selected = client.post('/chat', json={'continuation_id': body['continuation_id'], 'selections': [{'mention_index': 0, 'record_id': '9079'}]})
                self.assertEqual(selected.status_code, 200)
                self.assertIn('268.00 MAD', selected.json()['answer'])
                self.assertFalse(selected.json()['inference_performed'])
                for payload in ({}, {'text': ' '}, {'text': 'x', 'selections': [{'mention_index': 0, 'record_id': '9079'}]}, {'continuation_id': 'x' * 32}, {'text': 'x', 'continuation_id': 'x' * 32}, {'text': 'x', 'unexpected': True}):
                    self.assertEqual(client.post('/chat', json=payload).status_code, 422)
                fake.interpret.assert_awaited_once()

    def test_provider_error_is_visible_and_lookup_still_works(self):
        with connected_apps(Settings()) as client:
            failed = client.post('/chat', json={'text': 'Prix ABIP?'})
            self.assertEqual(failed.status_code, 503)
            self.assertEqual(failed.json()['detail']['code'], 'model_not_configured')
            self.assertEqual(client.get('/medications/9079').status_code, 200)
