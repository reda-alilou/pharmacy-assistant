import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from tests.support.configuration import FixtureSettings as Settings
from tests.support.chat import response

class PharmacyApiAndUiTests(unittest.TestCase):

    def test_api_preserves_raw_arabic_and_exposes_matching_method(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response([], ['pharmacy_contact'], pharmacy='صيدلية ابن نفيس', city='الرباط', language='ar', script='arabic')
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter), TestClient(create_app(settings=Settings())) as api:
            body = api.post('/chat', json={'text': 'رقم صيدلية ابن نفيس في الرباط'}).json()
            self.assertEqual(body['pharmacy']['match_method'], 'reviewed_alias')
            self.assertEqual(body['pharmacy']['pharmacies'][0]['phone'], '0537720657')
            self.assertEqual(body['interpretation']['entities']['pharmacy'], 'صيدلية ابن نفيس')
        interpreter.interpret.assert_awaited_once()
