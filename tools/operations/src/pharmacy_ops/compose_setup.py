"""Prepare ignored Compose credentials from existing settings; never starts services."""

import argparse
import json
from pathlib import Path

from sqlalchemy.engine import make_url

from pharmacy_infrastructure.paths import ENV_FILE
from pharmacy_language.config import InferenceSettings
from pharmacy_ops.database import ENV, configuration
from pharmacy_infrastructure.paths import ROOT


OUTPUT = ROOT / ".runtime/compose.env"


def compose_values(database_values, inference: InferenceSettings):
    required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "CORE_DB_PASSWORD", "LANGUAGE_DB_PASSWORD")
    if any(not database_values.get(key) for key in required):
        raise ValueError("Database credentials are incomplete; keep the existing database environment file.")
    values = {key: database_values[key] for key in required}
    values.update(POSTGRES_PORT=database_values.get("POSTGRES_PORT", "55432"), WEB_PORT="8080")
    for field in ("MIGRATION_DATABASE_URL", "CORE_DATABASE_URL", "LANGUAGE_DATABASE_URL"):
        url = make_url(database_values[field])
        if url.drivername != "postgresql+psycopg" or url.database != values["POSTGRES_DB"]:
            raise ValueError("Database URLs must select the existing project PostgreSQL database.")
        values[field] = url.set(host="postgres", port=5432).render_as_string(hide_password=False)
    # Include only the selected provider's credential and options. Retain the same
    # scope/model/spacing so moving to containers cannot reset shared accounting.
    for name in ("inference_provider", "inference_min_interval_seconds", "inference_quota_scope"):
        values[name.upper()] = str(getattr(inference, name))
    prefix = inference.inference_provider + "_"
    for name in InferenceSettings.model_fields:
        if name.startswith(prefix):
            value = getattr(inference, name)
            if value is not None:
                values[name.upper()] = value.get_secret_value() if hasattr(value, "get_secret_value") else str(value)
    return values


def write_environment(path: Path, values):
    # Single quoting prevents Compose interpolation of dollar signs in secrets.
    lines = []
    for key, value in values.items():
        if any(character in value for character in ("\n", "\r", "\0")):
            raise ValueError("Environment values must occupy a single line.")
        lines.append(key + "='" + value.replace("'", "\\'") + "'")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("# Local runtime credentials; never commit, print, or build into an image.\n")
        handle.write("\n".join(lines) + "\n")
    return {"configuration_created": True, "path": str(path), "secrets_printed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-env", type=Path, default=ENV)
    parser.add_argument("--inference-env", type=Path, default=ENV_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        values = compose_values(configuration(args.database_env), InferenceSettings.from_env(args.inference_env))
        print(json.dumps(write_environment(args.output, values)))
    except FileExistsError:
        print(json.dumps({"error": "Compose credentials already exist and were not overwritten. Edit the ignored file deliberately when configuration changes."}))
        return 1
    except Exception:
        print(json.dumps({"error": "Compose setup failed. Check existing database/provider configuration; credentials were not printed."}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
