import unittest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_core.conversation.image import ImageCandidate, ImageIdentification


class ChatImageApiTests(unittest.TestCase):

    def test_image_upload_returns_candidates_and_rejects_non_images(self):
        identifier = AsyncMock()
        identifier.identify.return_value = ImageIdentification(
            query='ABIP 15 MG', candidates=(ImageCandidate('9080', 92.5),), elapsed_ms=12.5)
        with TestClient(create_app(settings=Settings(), interpreter=AsyncMock(), image_identifier=identifier)) as client:
            uploaded = client.post('/chat/image', files={'file': ('photo.png', b'not-a-real-png', 'image/png')})
            self.assertEqual(uploaded.status_code, 200)
            body = uploaded.json()
            self.assertEqual(body['medications'][0]['medication']['source_record_id'], '9080')
            self.assertEqual(body['inference']['provider'], 'local')
            self.assertFalse(body['inference_performed'])
            self.assertIn('Texte détecté', body['answer'])
            invalid = client.post('/chat/image', files={'file': ('notes.txt', b'hello', 'text/plain')})
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(invalid.json()['detail']['code'], 'image_invalid')
        identifier.identify.assert_awaited_once_with(b'not-a-real-png', content_type='image/png')

    def test_image_upload_is_unavailable_without_an_identifier(self):
        with TestClient(create_app(settings=Settings(), interpreter=AsyncMock())) as client:
            uploaded = client.post('/chat/image', files={'file': ('photo.png', b'image', 'image/png')})
            self.assertEqual(uploaded.status_code, 503)
            self.assertEqual(uploaded.json()['detail']['code'], 'image_unavailable')
