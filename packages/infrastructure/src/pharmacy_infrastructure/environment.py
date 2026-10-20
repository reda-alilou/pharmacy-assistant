"""Explicit environment loading shared by independently configured services."""

import os
from pathlib import Path
from dotenv import dotenv_values
from pydantic import BaseModel
from pharmacy_infrastructure.paths import ENV_FILE


class EnvironmentSettings(BaseModel):
    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE):
        values = dotenv_values(env_file, encoding="utf-8-sig", interpolate=False)
        database_file = os.environ.get("DATABASE_ENV_FILE", values.get("DATABASE_ENV_FILE"))
        if database_file:
            if not Path(database_file).is_file():
                raise ValueError("Configured database environment file is missing.")
            database_values = dotenv_values(database_file, encoding="utf-8-sig", interpolate=False)
            values.update({key: value for key, value in database_values.items()
                           if key in {"STORAGE_BACKEND", "CORE_DATABASE_URL", "LANGUAGE_DATABASE_URL"}})
        values.update(os.environ)
        return cls(**{field: values[field.upper()] for field in cls.model_fields
                      if values.get(field.upper()) is not None})
