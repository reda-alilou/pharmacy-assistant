"""The installed core package owns only core settings and its HTTP dependency."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from pharmacy_core.config import CoreSettings


class CoreSettingsTests(unittest.TestCase):
    def test_explicit_environment_filters_other_service_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / "test.env"
            env.write_text("STORAGE_BACKEND=postgres\nCORE_DATABASE_URL=postgresql+psycopg://core:offline@host/database\nLANGUAGE_DATABASE_URL=language-test\nGROQ_API_KEY=provider-test\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = CoreSettings.from_env(env)
        self.assertEqual(settings.core_database_url.get_secret_value(), "postgresql+psycopg://core:offline@host/database")
        self.assertFalse(hasattr(settings, "language_database_url"))
        self.assertFalse(hasattr(settings, "groq_api_key"))
        self.assertNotIn("postgresql+psycopg://core:offline@host/database", repr(settings))

    def test_postgres_settings_require_owned_database_and_validate_http_origin(self):
        with self.assertRaises(ValidationError):
            CoreSettings(storage_backend="postgres")
        for origin in ("http://name:password@localhost", "http://localhost/path", "file:///tmp"):
            with self.subTest(origin=origin), self.assertRaises(ValidationError):
                CoreSettings(language_service_url=origin)


if __name__ == "__main__":
    unittest.main()
