"""Alembic entry point; imports only the selected service's metadata."""

import importlib

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import text

from pharmacy_assistant.database import create_database_engine
from pharmacy_assistant.paths import ROOT


def run():
    config = context.config
    schema = config.get_main_option("service_schema")
    if schema not in {"core", "language"}:
        raise ValueError("Select the core or language Alembic environment.")
    metadata = importlib.import_module(f"pharmacy_assistant.{schema}.storage.models").metadata
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", target_metadata=metadata,
                          version_table_schema=schema, literal_binds=True, include_schemas=True)
        with context.begin_transaction():
            context.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            context.run_migrations()
        return
    import os
    env_path = os.environ.get("DATABASE_ENV_FILE", str(ROOT / ".runtime/postgres.env"))
    values = {**dotenv_values(env_path, interpolate=False), **os.environ}
    url = config.attributes.get("database_url") or values.get("MIGRATION_DATABASE_URL")
    if not url:
        raise ValueError("Configure MIGRATION_DATABASE_URL; migrations never use runtime credentials.")
    engine = create_database_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            context.configure(connection=connection, target_metadata=metadata,
                              version_table_schema=schema, include_schemas=True,
                              include_name=lambda name, kind, parent: kind != "schema" or name == schema)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
