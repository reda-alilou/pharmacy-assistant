"""R4: default startup fails closed; fixtures require explicit resources."""
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pharmacy_core.api.app import create_app
from pharmacy_core.api.resources import CoreResources
from pharmacy_core.config import CoreSettings

URL = 'postgresql+psycopg://core:private-startup-password@127.0.0.1:1/fixture'


class CoreStartupTests(unittest.TestCase):
    def test_missing_owned_url_fails_before_reading_catalogue_or_creating_interpreter(self):
        with patch('pharmacy_infrastructure.environment.dotenv_values', return_value={}), \
             patch.dict('os.environ', {}, clear=True), \
             patch('pharmacy_core.api.app.create_interpreter') as provider, \
             patch('pharmacy_core.medications.catalog.MedicationCatalog.from_path') as files:
            with self.assertRaises(ValidationError) as caught, TestClient(create_app()):
                self.fail('Startup unexpectedly succeeded')
            self.assertIn('core_database_url', str(caught.exception))
            files.assert_not_called()
            provider.assert_not_called()

    def test_unavailable_or_unmigrated_database_fails_without_file_fallback(self):
        engine = Mock()
        with patch('pharmacy_infrastructure.database.create_database_engine', return_value=engine), \
             patch('pharmacy_core.storage.postgres.catalogue.load_catalogue', side_effect=RuntimeError('private-startup-password')), \
             patch('pharmacy_core.medications.catalog.MedicationCatalog.from_path') as files, \
             patch('pharmacy_core.api.app.create_interpreter') as provider:
            with self.assertRaisesRegex(RuntimeError, 'Core PostgreSQL storage unavailable') as caught, \
                 TestClient(create_app(CoreSettings(core_database_url=URL))):
                self.fail('Startup unexpectedly succeeded')
            self.assertNotIn('private-startup-password', str(caught.exception))
            engine.dispose.assert_called_once()
            files.assert_not_called()
            provider.assert_not_called()

    def test_explicit_offline_resources_do_not_open_a_database(self):
        interpreter = AsyncMock()
        resources = CoreResources(Mock(), Mock(), interpreter, AsyncMock())
        with patch('pharmacy_infrastructure.database.create_database_engine', side_effect=AssertionError('Database opened')), \
             patch('pharmacy_core.api.app.create_interpreter', side_effect=AssertionError('Provider created')):
            with TestClient(create_app(CoreSettings(core_database_url=URL), resources=resources)) as client:
                self.assertEqual(client.get('/ready').json()['storage_backend'], 'postgres')
        interpreter.interpret.assert_not_awaited()
        interpreter.close.assert_awaited_once()

    def test_non_postgres_modes_and_urls_are_rejected_without_secret_echo(self):
        for values in ({'storage_backend': 'files', 'core_database_url': URL},
                       {'core_database_url': 'sqlite:///private-startup-password'},
                       {'core_database_url': 'postgresql+psycopg://'},
                       {'core_database_url': ''}):
            with self.subTest(values=list(values)), self.assertRaises(ValidationError) as caught:
                CoreSettings(**values)
            self.assertNotIn('private-startup-password', str(caught.exception))
