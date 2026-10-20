"""Provider/evaluation settings with a non-connectable URL for explicit fixtures."""
from pydantic import Field, SecretStr
from pharmacy_language.config import LanguageSettings


class FixtureSettings(LanguageSettings):
    language_database_url: SecretStr = Field(default=SecretStr('postgresql+psycopg://fixture:offline@127.0.0.1:1/fixture'), repr=False)
