"""Core-owned runtime settings; no provider or language database credentials."""

from typing import Literal
from pydantic import ConfigDict, Field, SecretStr, field_validator
from pharmacy_infrastructure.environment import EnvironmentSettings
from pharmacy_infrastructure.database import validate_database_url


class CoreSettings(EnvironmentSettings):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    storage_backend: Literal["postgres"] = "postgres"
    core_database_url: SecretStr = Field(repr=False)
    language_service_url: str = "http://127.0.0.1:8001"
    language_service_timeout_seconds: float = Field(default=160, ge=1, le=180, allow_inf_nan=False)

    @field_validator("language_service_url")
    @classmethod
    def validate_origin(cls, value):
        from urllib.parse import urlsplit
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("Language service URL must be an HTTP(S) origin without credentials or a path.")
        try:
            parsed.port
        except ValueError:
            raise ValueError("Language service URL has an invalid port.") from None
        return value

    @field_validator("core_database_url")
    @classmethod
    def require_core_database(cls, value):
        validate_database_url(value.get_secret_value())
        return value

    @classmethod
    def for_app(cls, settings):
        # Compatibility for existing explicitly constructed fixture/tool settings;
        # never retain provider credentials or language database access in core.
        if isinstance(settings, cls):
            return settings
        return cls(**{name: getattr(settings, name) for name in cls.model_fields if hasattr(settings, name)})
