"""Language-owned provider, quota and database settings."""

from typing import Literal
from pydantic import ConfigDict, Field, SecretStr, field_validator
from pharmacy_infrastructure.environment import EnvironmentSettings
from pharmacy_infrastructure.database import validate_database_url


DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_OPENCODE_MODEL = "glm-5.3-flash-free"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
OPENCODE_BASE_URL = "https://opencode.ai/inference/openai/v1"


class InferenceSettings(EnvironmentSettings):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    inference_provider: Literal["gemini", "opencode", "groq"] = "gemini"
    inference_min_interval_seconds: float = Field(default=0, ge=0, le=3600, allow_inf_nan=False)
    inference_quota_scope: str = Field(default="default", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    gemini_api_key: SecretStr | None = Field(default=None, repr=False)
    gemini_model: str = Field(default=DEFAULT_GEMINI_MODEL, min_length=1, max_length=200, pattern=r"^gemini-[A-Za-z0-9._-]+$")
    gemini_timeout_seconds: float = Field(default=30, ge=1, le=60, allow_inf_nan=False)
    gemini_max_output_tokens: int = Field(default=4096, ge=256, le=8192)
    opencode_api_key: SecretStr | None = Field(default=None, repr=False)
    opencode_model: str = Field(default=DEFAULT_OPENCODE_MODEL, min_length=1, max_length=200)
    opencode_output_mode: Literal["json_schema", "json_object"] = "json_schema"
    opencode_timeout_seconds: float = Field(default=30, ge=1, le=60, allow_inf_nan=False)
    opencode_max_completion_tokens: int = Field(default=2048, ge=256, le=4096)

    groq_api_key: SecretStr | None = Field(default=None, repr=False)
    groq_model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=200)
    groq_output_mode: Literal["json_schema", "json_object"] = "json_schema"
    groq_timeout_seconds: float = Field(default=20, ge=1, le=60, allow_inf_nan=False)
    groq_max_completion_tokens: int = Field(default=1200, ge=256, le=4096)

    @field_validator("groq_api_key", "opencode_api_key", "gemini_api_key", mode="before")
    @classmethod
    def empty_key_is_unconfigured(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value in {"", "your_key", "your_key_here", "replace_me"}:
                return None
        return value

    @field_validator("groq_model", "opencode_model", "gemini_model", mode="before")
    @classmethod
    def trim_model(cls, value):
        return value.strip() if isinstance(value, str) else value

    @property
    def interpretation_configured(self) -> bool:
        return getattr(self, f"{self.inference_provider}_api_key") is not None

    @property
    def inference_key_name(self) -> str:
        return f"{self.inference_provider.upper()}_API_KEY"

    @property
    def inference_model(self) -> str:
        return getattr(self, f"{self.inference_provider}_model")

    @property
    def inference_output_mode(self) -> str:
        if self.inference_provider == "opencode":
            return self.opencode_output_mode
        return self.groq_output_mode if self.inference_provider == "groq" else "json_schema"


class LanguageSettings(InferenceSettings):
    storage_backend: Literal["postgres"] = "postgres"
    language_database_url: SecretStr = Field(repr=False)

    @field_validator("language_database_url")
    @classmethod
    def require_language_database(cls, value):
        validate_database_url(value.get_secret_value())
        return value

    @classmethod
    def for_app(cls, settings):
        if isinstance(settings, cls):
            return settings
        return cls(**{name: getattr(settings, name) for name in cls.model_fields if hasattr(settings, name)})
