import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from tests.support.runtime import core_app as create_app
from pharmacy_core.conversation.models import ChatRequest
from tests.support.configuration import FixtureSettings as Settings
from tests.support.chat import mention, response

class ConversationApiAndUiTests(unittest.TestCase):

    def test_request_modes_and_api_session_roundtrip(self):
        token = 'x' * 32
        for invalid in ({'session_id': token}, {'text': 'x', 'reference_index': 0}, {'text': 'x', 'session_id': token, 'reference_index': 0}, {'session_id': token, 'reference_index': True}, {'text': 'x', 'session_id': token, 'continuation_id': token}):
            with self.assertRaises(ValidationError):
                ChatRequest.model_validate(invalid)
        interpreter = AsyncMock()
        interpreter.interpret.side_effect = [response([mention('ABIP')]), response([mention(None, presentation='boîte de 30')])]
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter), TestClient(create_app(settings=Settings())) as client:
            initial = client.post('/chat', json={'text': 'Prix ABIP'}).json()
            final = client.post('/chat', json={'text': 'La boîte de 30', 'session_id': initial['session_id']})
            self.assertEqual(final.status_code, 200)
            self.assertEqual(final.json()['medications'][0]['medication']['source_record_id'], '9080')
            self.assertIsNone(final.json()['interpretation']['entities']['medications'][0]['name'])
            self.assertEqual(client.post('/chat', json={'text': 'Prix?', 'session_id': token}).status_code, 410)
        self.assertEqual(interpreter.interpret.await_count, 2)
