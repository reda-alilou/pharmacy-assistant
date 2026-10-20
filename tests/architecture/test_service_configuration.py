import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from pharmacy_core.config import CoreSettings
from pharmacy_language.config import LanguageSettings
from tests.support.runtime import CORE_URL
from pharmacy_infrastructure.paths import ROOT

class ServiceConfigurationTests(unittest.TestCase):

    def test_runtime_settings_own_only_their_service_credentials(self):
        values = {'STORAGE_BACKEND': 'postgres', 'CORE_DATABASE_URL': 'postgresql+psycopg://core:private@host/database', 'LANGUAGE_DATABASE_URL': 'postgresql+psycopg://language:private@host/database', 'GROQ_API_KEY': 'private-key', 'GROQ_MODEL': 'model', 'INFERENCE_PROVIDER': 'groq'}
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'settings.env'
            env.write_text('\n'.join((f'{k}={v}' for k, v in values.items())), encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True):
                core, language = (CoreSettings.from_env(env), LanguageSettings.from_env(env))
        self.assertFalse(hasattr(core, 'language_database_url'))
        self.assertFalse(hasattr(core, 'groq_api_key'))
        self.assertFalse(hasattr(language, 'core_database_url'))
        self.assertEqual(language.groq_api_key.get_secret_value(), 'private-key')
        self.assertNotIn('private', repr(core))
        self.assertNotIn('private', repr(language))
        for cls, field in ((CoreSettings, 'core_database_url'), (LanguageSettings, 'language_database_url')):
            cls(storage_backend='postgres', **{field: CORE_URL})
            with self.assertRaises(ValidationError):
                cls(storage_backend='postgres')
        for url in ('file:///tmp/private', 'http://name:secret@localhost', 'http://localhost/path', 'http://localhost:bad', 'http://localhost?secret=x'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                CoreSettings(core_database_url=CORE_URL, language_service_url=url)

    def test_entrypoints_import_without_other_service_or_provider_modules(self):
        scripts = ["import pharmacy_core.api.app; banned=('groq', 'pharmacy_assistant.language')", "import pharmacy_language.api.app; banned=('pharmacy_assistant.core',)"]
        for script in scripts:
            script += "\nimport sys\nfor p in banned: assert not any(n == p or n.startswith(p+'.') for n in sys.modules), p"
            result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
