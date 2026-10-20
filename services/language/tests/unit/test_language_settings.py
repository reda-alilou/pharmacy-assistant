"""The installed language package owns provider and language database settings."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from pharmacy_language.config import LanguageSettings


class LanguageSettingsTests(unittest.TestCase):
    def test_explicit_environment_filters_core_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / "test.env"
            env.write_text("STORAGE_BACKEND=postgres\nCORE_DATABASE_URL=core-test\nLANGUAGE_DATABASE_URL=postgresql+psycopg://language:offline@host/database\nINFERENCE_PROVIDER=groq\nGROQ_API_KEY=provider-test\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = LanguageSettings.from_env(env)
        self.assertEqual(settings.language_database_url.get_secret_value(), "postgresql+psycopg://language:offline@host/database")
        self.assertEqual(settings.groq_api_key.get_secret_value(), "provider-test")
        self.assertFalse(hasattr(settings, "core_database_url"))
        self.assertNotIn("postgresql+psycopg://language:offline@host/database", repr(settings))
        self.assertNotIn("provider-test", repr(settings))

    def test_postgres_settings_require_only_language_database(self):
        with self.assertRaises(ValidationError):
            LanguageSettings(storage_backend="postgres")
        settings = LanguageSettings(storage_backend="postgres", language_database_url="postgresql+psycopg://language:offline@host/database")
        self.assertEqual(settings.storage_backend, "postgres")


if __name__ == "__main__":
    unittest.main()
