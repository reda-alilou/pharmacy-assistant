import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from tests.support.configuration import FixtureSettings as Settings
from tests.support.chat import mention, response

class RefinementApiAndUiTests(unittest.TestCase):

    def test_http_refinement_validation_and_existing_presentation_selection(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response([mention('ABIP', strength='5mg')])
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter), TestClient(create_app(settings=Settings())) as client:
            initial = client.post('/chat', json={'text': 'ABIP 5mg'}).json()
            token = initial['continuation_id']
            self.assertEqual(client.post('/chat', json={'continuation_id': token, 'refinements': [{'mention_index': 0, 'field': 'quantity', 'value': '2'}]}).status_code, 422)
            self.assertEqual(client.post('/chat', json={'continuation_id': token, 'refinements': [{'mention_index': 0, 'field': 'strength', 'value': '5 MG'}]}).status_code, 422)
            corrected = client.post('/chat', json={'continuation_id': token, 'refinements': [{'mention_index': 0, 'field': 'strength', 'value': '15 MG'}]})
            self.assertEqual(corrected.status_code, 200)
            final = client.post('/chat', json={'continuation_id': corrected.json()['continuation_id'], 'selections': [{'mention_index': 0, 'record_id': '9079'}]}).json()
            self.assertIn('268.00 MAD', final['answer'])
        interpreter.interpret.assert_awaited_once()
