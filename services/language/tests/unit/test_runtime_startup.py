"""R4: a configured PostgreSQL quota store is mandatory before serving requests."""
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pharmacy_language.api.app import create_app
from pharmacy_language.config import LanguageSettings
from pharmacy_language.quota import control

URL = 'postgresql+psycopg://language:private-startup-password@127.0.0.1:1/fixture'


class LanguageStartupTests(unittest.TestCase):
    def test_missing_owned_url_fails_before_provider_creation(self):
        with patch('pharmacy_infrastructure.environment.dotenv_values', return_value={}), \
             patch.dict('os.environ', {}, clear=True), \
             patch('pharmacy_language.api.app.create_interpreter') as provider:
            with self.assertRaises(ValidationError) as caught, TestClient(create_app()):
                self.fail('Startup unexpectedly succeeded')
            self.assertIn('language_database_url', str(caught.exception))
            provider.assert_not_called()

    def test_quota_database_failure_blocks_startup_and_closes_resources(self):
        interpreter = AsyncMock()
        interpreter.control = Mock()
        interpreter.control.store.status.side_effect = RuntimeError('private-startup-password')
        with patch('pharmacy_language.api.app.create_interpreter', return_value=interpreter):
            with self.assertRaisesRegex(RuntimeError, 'Language PostgreSQL quota storage unavailable') as caught, \
                 TestClient(create_app(LanguageSettings(language_database_url=URL))):
                self.fail('Startup unexpectedly succeeded')
            self.assertNotIn('private-startup-password', str(caught.exception))
        interpreter.close.assert_awaited_once()
        interpreter.interpret.assert_not_awaited()

    def test_explicit_fixture_works_without_database_or_provider_creation(self):
        interpreter = AsyncMock()
        with patch('pharmacy_language.api.app.create_interpreter', side_effect=AssertionError('Provider created')):
            with TestClient(create_app(LanguageSettings(language_database_url=URL), interpreter=interpreter)) as client:
                self.assertEqual(client.get('/health').json()['storage_backend'], 'postgres')
        interpreter.interpret.assert_not_awaited()
        interpreter.close.assert_awaited_once()

    def test_runtime_exposes_no_sqlite_backend_or_ledger_setting(self):
        self.assertFalse(hasattr(control, 'QuotaStore'))
        self.assertNotIn('inference_quota_db', LanguageSettings.model_fields)
        for values in ({'storage_backend': 'files', 'language_database_url': URL},
                       {'language_database_url': 'sqlite:///private-startup-password'},
                       {'language_database_url': ''}):
            with self.subTest(values=list(values)), self.assertRaises(ValidationError) as caught:
                LanguageSettings(**values)
            self.assertNotIn('private-startup-password', str(caught.exception))
