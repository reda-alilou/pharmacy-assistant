import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dotenv import dotenv_values
import yaml
from pharmacy_ops.compose_setup import compose_values, write_environment
from pharmacy_language.config import InferenceSettings
from pharmacy_ops.database import main as database_setup_main
from pharmacy_infrastructure.paths import ROOT

class ComposeConfigurationTests(unittest.TestCase):

    def test_default_stack_has_one_entry_point_and_only_owned_credentials(self):
        config = yaml.safe_load((ROOT / 'deploy/compose.yaml').read_text(encoding='utf-8'))
        services = config['services']
        self.assertEqual(config['name'], 'pharmacy-assistant-architecture')
        self.assertEqual({key for key, service in services.items() if not service.get('profiles')}, {'web', 'core', 'language', 'platform', 'postgres'})
        for key, service in services.items():
            if key != 'web':
                self.assertNotIn('ports', service)
            self.assertIn('healthcheck', service) if not service.get('profiles') else None
        self.assertEqual(services['web']['ports'], ['127.0.0.1:${WEB_PORT:-8080}:8080'])
        self.assertEqual(set(services['core']['environment']), {'STORAGE_BACKEND', 'CORE_DATABASE_URL', 'LANGUAGE_SERVICE_URL', 'LANGUAGE_SERVICE_TIMEOUT_SECONDS'})
        self.assertNotIn('CORE_DATABASE_URL', services['language']['environment'])
        self.assertNotIn('MIGRATION_DATABASE_URL', services['language']['environment'])
        self.assertEqual(set(services['platform']['environment']), {'PLATFORM_DATABASE_URL', 'PLATFORM_ORIGIN', 'PLATFORM_COOKIE_SECURE', 'PLATFORM_TRUST_PROXY'})
        self.assertNotIn('environment', services['web'])
        self.assertNotIn('language', services['core']['depends_on'])
        self.assertEqual(services['postgres']['volumes'], ['postgres_data:/var/lib/postgresql/data'])
        self.assertEqual(services['database-setup']['profiles'], ['tools'])
        for name in ('core', 'language', 'platform', 'web'):
            self.assertTrue(services[name]['read_only'])
            self.assertEqual(services[name]['cap_drop'], ['ALL'])

    def test_credentials_translate_existing_database_without_changing_scope_or_provider(self):
        database = dict(POSTGRES_DB='pharmacy_assistant', POSTGRES_USER='admin', POSTGRES_PASSWORD='admin-private', CORE_DB_PASSWORD='core-private', LANGUAGE_DB_PASSWORD='language-private')
        for key, role in (('MIGRATION_DATABASE_URL', 'admin'), ('CORE_DATABASE_URL', 'core'), ('LANGUAGE_DATABASE_URL', 'language')):
            database[key] = f'postgresql+psycopg://{role}:private@127.0.0.1:55432/pharmacy_assistant'
        inference = InferenceSettings(inference_provider='groq', groq_api_key='selected$private', gemini_api_key='never-copy', opencode_api_key='never-copy', inference_quota_scope='shared-test')
        values = compose_values(database, inference)
        self.assertEqual(values['INFERENCE_QUOTA_SCOPE'], 'shared-test')
        self.assertEqual(values['GROQ_API_KEY'], 'selected$private')
        self.assertNotIn('GEMINI_API_KEY', values)
        self.assertNotIn('OPENCODE_API_KEY', values)
        self.assertIn('@postgres:5432/', values['CORE_DATABASE_URL'])
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'compose.env'
            result = write_environment(env, values)
            self.assertNotIn('private', json.dumps(result))
            self.assertEqual(dict(dotenv_values(env, interpolate=False)), values)
            original = env.read_bytes()
            with self.assertRaises(FileExistsError):
                write_environment(env, {'NEW_KEY': 'new-private'})
            self.assertEqual(env.read_bytes(), original)
            with self.assertRaises(ValueError):
                write_environment(Path(directory) / 'invalid.env', {'KEY': 'bad\nvalue'})

    def test_container_setup_reads_only_explicit_environment_without_a_file(self):
        values = {'MIGRATION_DATABASE_URL': 'private-admin-url'}
        with patch.dict(os.environ, values, clear=True), patch('sys.argv', ['database_setup', 'migrate', '--from-environment']), patch('pharmacy_ops.database.configuration', side_effect=AssertionError('Host file read')), patch('pharmacy_ops.database.migrate', return_value={'migrated': ['core', 'language']}) as migrate, patch('builtins.print'):
            self.assertIsNone(database_setup_main())
            migrate.assert_called_once_with(None)
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from pharmacy_core.config import CoreSettings
from pharmacy_contracts.errors import StorageUnavailable

class CoreReadinessTests(unittest.TestCase):

    def test_core_ready_is_independent_of_language_and_does_not_infer(self):
        interpreter = AsyncMock()
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter), TestClient(create_app(settings=CoreSettings(core_database_url='postgresql+psycopg://core:offline@host/database'))) as client:
            self.assertEqual(client.get('/ready').json(), {'status': 'ok', 'service': 'core', 'storage_backend': 'postgres'})
            interpreter.health.assert_not_awaited()
            interpreter.interpret.assert_not_awaited()

    def test_database_outage_makes_core_unready_without_exposing_database_errors(self):
        interpreter = AsyncMock()
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter), TestClient(create_app(settings=CoreSettings(core_database_url='postgresql+psycopg://core:offline@host/database'))) as client:
            store = Mock()
            client.app.state.conversations = store
            store.ready.side_effect = StorageUnavailable()
            result = client.get('/ready')
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()['detail']['code'], 'storage_unavailable')
            interpreter.interpret.assert_not_awaited()
