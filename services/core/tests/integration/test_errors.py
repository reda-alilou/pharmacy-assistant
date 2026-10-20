import unittest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_core.conversation.errors import ChatError
from pharmacy_contracts.errors import StorageUnavailable
from pharmacy_core.storage.postgres.conversations import ConversationStore

class ChatErrorApiTests(unittest.TestCase):

    def test_application_errors_keep_the_existing_http_contract(self):
        errors = {'session_expired': 410, 'clarification_expired': 410, 'invalid_reference': 422, 'invalid_selection': 422, 'invalid_refinement': 422, 'conversation_conflict': 409, 'request_in_progress': 409, 'request_conflict': 409}
        interpreter = AsyncMock()
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter):
            with TestClient(create_app(settings=Settings())) as client:
                for code, status in errors.items():
                    with self.subTest(code=code):
                        failure = ChatError(code, 'Safe application message')
                        with patch.object(client.app.state.chat, 'respond', side_effect=failure):
                            result = client.post('/chat', json={'text': 'Prix ABIP?'})
                        self.assertEqual(result.status_code, status)
                        self.assertEqual(result.json(), {'detail': {'code': code, 'message': failure.message}})
                interpreter.interpret.assert_not_awaited()
        interpreter.close.assert_awaited_once()

    def test_database_failures_are_sanitized_before_the_http_boundary(self):
        from sqlalchemy.exc import OperationalError
        engine = Mock()
        engine.begin.side_effect = OperationalError('private SQL', {}, Exception('private-password'))
        with self.assertRaises(StorageUnavailable) as caught:
            ConversationStore(engine).create()
        self.assertNotIn('private-password', str(caught.exception))
        interpreter = AsyncMock()
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter):
            with TestClient(create_app(settings=Settings())) as client:
                with patch.object(client.app.state.chat, 'respond', side_effect=caught.exception):
                    result = client.post('/chat', json={'text': 'Prix ABIP?'})
                self.assertEqual(result.status_code, 503)
                self.assertEqual(result.json()['detail']['code'], 'storage_unavailable')
                self.assertNotIn('private-password', result.text)
                interpreter.interpret.assert_not_awaited()
