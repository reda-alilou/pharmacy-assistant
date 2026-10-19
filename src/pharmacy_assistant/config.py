"""Local server configuration. Credentials never appear in API responses."""

import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_OPENCODE_MODEL = "glm-5.3-flash-free"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
OPENCODE_BASE_URL = "https://opencode.ai/inference/openai/v1"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    inference_provider: Literal["gemini", "opencode", "groq"] = "gemini"
    inference_min_interval_seconds: float = Field(default=0, ge=0, le=3600, allow_inf_nan=False)
    inference_quota_scope: str = Field(default="default", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    inference_quota_db: Path = ROOT / ".runtime/inference_quota.sqlite3"
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

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> "Settings":
        # Read this project's file explicitly, without mutating the process
        # environment or searching unrelated parent directories for credentials.
        values = dotenv_values(env_file, encoding="utf-8-sig", interpolate=False)
        values.update(os.environ)  # Explicit environment variables take priority.
        mapping = {
            "INFERENCE_PROVIDER": "inference_provider",
            "INFERENCE_MIN_INTERVAL_SECONDS": "inference_min_interval_seconds",
            "INFERENCE_QUOTA_SCOPE": "inference_quota_scope",
            "INFERENCE_QUOTA_DB": "inference_quota_db",
            "GEMINI_API_KEY": "gemini_api_key",
            "GEMINI_MODEL": "gemini_model",
            "GEMINI_TIMEOUT_SECONDS": "gemini_timeout_seconds",
            "GEMINI_MAX_OUTPUT_TOKENS": "gemini_max_output_tokens",
            "OPENCODE_API_KEY": "opencode_api_key",
            "OPENCODE_MODEL": "opencode_model",
            "OPENCODE_OUTPUT_MODE": "opencode_output_mode",
            "OPENCODE_TIMEOUT_SECONDS": "opencode_timeout_seconds",
            "OPENCODE_MAX_COMPLETION_TOKENS": "opencode_max_completion_tokens",
            "GROQ_API_KEY": "groq_api_key",
            "GROQ_MODEL": "groq_model",
            "GROQ_OUTPUT_MODE": "groq_output_mode",
            "GROQ_TIMEOUT_SECONDS": "groq_timeout_seconds",
            "GROQ_MAX_COMPLETION_TOKENS": "groq_max_completion_tokens",
        }
        return cls(**{
            field: values[key] for key, field in mapping.items()
            if key in values and values[key] is not None
        })
