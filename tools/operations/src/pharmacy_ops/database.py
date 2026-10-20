"""Explicit database setup/import commands. Never starts or stops services."""

import argparse
import json
import os
from pathlib import Path
import secrets

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy import text

from pharmacy_infrastructure.database import create_database_engine
from pharmacy_infrastructure.paths import ROOT


ENV = ROOT / ".runtime/postgres.env"


def configuration(path=ENV):
    if not path.is_file():
        raise ValueError("Run database_setup init-env first.")
    return dict(dotenv_values(path, interpolate=False))


def init_env(path=ENV):
    path.parent.mkdir(parents=True, exist_ok=True)
    admin, core, language = (secrets.token_urlsafe(32) for _ in range(3))
    values = dict(STORAGE_BACKEND="postgres", POSTGRES_DB="pharmacy_assistant",
                  POSTGRES_USER="pharmacy_admin", POSTGRES_PASSWORD=admin, POSTGRES_PORT="55432",
                  CORE_DB_PASSWORD=core, LANGUAGE_DB_PASSWORD=language)
    for key, role, password in (("MIGRATION_DATABASE_URL", "pharmacy_admin", admin),
                                ("CORE_DATABASE_URL", "pharmacy_core", core),
                                ("LANGUAGE_DATABASE_URL", "pharmacy_language", language)):
        values[key] = f"postgresql+psycopg://{role}:{password}@127.0.0.1:55432/pharmacy_assistant"
    # Exclusive creation: never overwrite existing credentials or a database volume's password.
    with path.open("x", encoding="utf-8") as handle:
        handle.write("# Local credentials; ignored by Git. Do not publish this file.\n")
        handle.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    return {"configuration_created": True, "path": str(path), "secrets_printed": False}


def migrate(path):
    from pharmacy_ops.migrations import migrate_schemas
    values = configuration(path) if path is not None else os.environ
    return migrate_schemas(values["MIGRATION_DATABASE_URL"])


def grant(values):
    from pharmacy_core.storage.postgres.models import metadata as core
    from pharmacy_language.storage.postgres.models import metadata as language
    engine = create_database_engine(values["MIGRATION_DATABASE_URL"])
    try:
        with engine.begin() as db:
            raw = db.connection.driver_connection
            for schema, role, password_key, metadata in (
                ("core", "pharmacy_core", "CORE_DB_PASSWORD", core),
                ("language", "pharmacy_language", "LANGUAGE_DB_PASSWORD", language),
            ):
                if not db.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                    raw.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(values[password_key])))
                else:
                    # This command owns only these project-specific roles.
                    raw.execute(sql.SQL("ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(values[password_key])))
                raw.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(schema)))
                raw.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(role)))
                for table in metadata.sorted_tables:
                    raw.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {}.{} TO {}").format(
                        sql.Identifier(schema), sql.Identifier(table.name), sql.Identifier(role)))
                raw.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)))
                other = "language" if schema == "core" else "core"
                raw.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(sql.Identifier(other), sql.Identifier(role)))
            raw.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    finally:
        engine.dispose()
    return {"runtime_roles_configured": True}


def verify(values, medication_path, pharmacy_path):
    from pharmacy_core.medications.catalog import MedicationCatalog
    from pharmacy_core.pharmacies.directory import PharmacyDirectory
    from pharmacy_core.storage.postgres.catalogue import reconstruct
    from sqlalchemy.exc import DBAPIError
    engine = create_database_engine(values["CORE_DATABASE_URL"])
    try:
        with engine.connect() as db:
            records, pharmacies = reconstruct(db)
        expected = MedicationCatalog.from_path(medication_path).records
        expected_pharmacies = PharmacyDirectory.from_path(pharmacy_path).records
        if [r.model_dump(mode="json") for r in records] != [r.model_dump(mode="json") for r in expected]:
            raise ValueError("Medication round-trip differs from the input.")
        if [r.model_dump(mode="json") for r in pharmacies] != [r.model_dump(mode="json") for r in expected_pharmacies]:
            raise ValueError("Pharmacy round-trip differs from the input.")
    finally:
        engine.dispose()
    for key, forbidden in (("CORE_DATABASE_URL", "language.quota_state"),
                            ("LANGUAGE_DATABASE_URL", "core.presentations")):
        engine = create_database_engine(values[key])
        try:
            with engine.connect() as db:
                try:
                    db.execute(text(f"SELECT 1 FROM {forbidden} LIMIT 1"))
                except DBAPIError as error:
                    if getattr(error.orig, "sqlstate", None) != "42501":
                        raise ValueError("Permission check failed for an unexpected reason.") from None
                else:
                    raise ValueError("A runtime role can access the other service's tables.")
        finally:
            engine.dispose()
    return {"round_trip_passed": True, "presentations": len(records), "pharmacies": len(pharmacies),
            "cross_service_access_denied": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init-env", "migrate", "grant", "import", "verify", "import-quota"))
    parser.add_argument("--env-file", type=Path, default=ENV)
    parser.add_argument("--from-environment", action="store_true",
                        help="Use explicitly supplied setup-job environment instead of a host credential file")
    parser.add_argument("--medications", type=Path, default=ROOT / "data/imports/ammps_medications_enriched.jsonl")
    parser.add_argument("--pharmacies", type=Path, default=ROOT / "data/imports/pharmacies_rabat.jsonl")
    parser.add_argument("--legacy-ledger", type=Path, default=ROOT / ".runtime/inference_quota.sqlite3")
    args = parser.parse_args()
    try:
        if args.action == "init-env":
            result = init_env(args.env_file)
        else:
            values = ({key: os.environ[key] for key in (
                "MIGRATION_DATABASE_URL", "CORE_DATABASE_URL", "LANGUAGE_DATABASE_URL",
                "CORE_DB_PASSWORD", "LANGUAGE_DB_PASSWORD") if key in os.environ}
                if args.from_environment else configuration(args.env_file))
            if args.action == "migrate":
                result = migrate(None if args.from_environment else args.env_file)
            elif args.action == "grant":
                result = grant(values)
            elif args.action == "verify":
                result = verify(values, args.medications, args.pharmacies)
            elif args.action == "import-quota":
                from pharmacy_language.storage.postgres.quota import PostgresQuotaStore
                engine = create_database_engine(values["MIGRATION_DATABASE_URL"])
                try:
                    result = PostgresQuotaStore(engine).import_sqlite(args.legacy_ledger)
                finally:
                    engine.dispose()
            else:
                from pharmacy_core.storage.postgres.catalogue import import_catalogue
                engine = create_database_engine(values["MIGRATION_DATABASE_URL"])
                try:
                    result = import_catalogue(engine, args.medications, args.pharmacies)
                finally:
                    engine.dispose()
    except FileExistsError:
        parser.exit(1, "Configuration already exists; it was not overwritten.\n")
    except Exception:
        # SQL exceptions may contain connection/SQL parameters; never print them.
        parser.exit(1, "Database operation failed. Verify service readiness, configuration, and migration/import state. Credentials and SQL parameters were not printed.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
