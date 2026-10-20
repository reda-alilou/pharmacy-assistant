"""Explicit backups and restore verification; excludes temporary conversation data."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url

from pharmacy_assistant.database import create_database_engine
from pharmacy_assistant.database_setup import ENV, configuration


def tool(name):
    path = shutil.which(name)
    if not path:
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL/17/bin" / f"{name}.exe"
        if candidate.is_file():
            path = str(candidate)
    if not path:
        raise ValueError("Install PostgreSQL 17 client tools or put them on PATH.")
    return path


def run_tool(name, url, arguments):
    parsed = make_url(url)
    environment = {**os.environ, "PGPASSWORD": parsed.password or "", "PGCONNECT_TIMEOUT": "5"}
    command = [tool(name), "--host", parsed.host, "--port", str(parsed.port or 5432),
               "--username", parsed.username, "--dbname", parsed.database, *arguments]
    result = subprocess.run(command, env=environment, capture_output=True, timeout=180)
    if result.returncode:
        raise ValueError("PostgreSQL backup/restore command failed; diagnostic output was withheld to protect credentials.")


def backup(values, output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation prevents overwriting an existing backup.
    with output.open("xb"):
        pass
    try:
        run_tool("pg_dump", values["MIGRATION_DATABASE_URL"], ["--format=custom", "--no-owner", "--no-privileges",
            "--exclude-table-data=core.conversations", "--exclude-table-data=core.conversation_messages",
            "--exclude-table-data=core.conversation_states", "--exclude-table-data=core.pending_choices",
            "--file", str(output)])
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {"backup": str(output), "temporary_conversations_excluded": True}


def verify_backup(values, backup_path):
    from pharmacy_assistant.core.storage.catalogue import reconstruct
    from pharmacy_assistant.core.storage.models import conversations
    from pharmacy_assistant.language.storage.models import quota_state, evaluation_budgets, quota_imports
    from sqlalchemy import func, select
    name = "pharmacy_backup_verify_" + uuid.uuid4().hex
    source_url = make_url(values["MIGRATION_DATABASE_URL"])
    admin = create_database_engine(source_url.set(database="postgres").render_as_string(hide_password=False))
    restored = create_database_engine(source_url.set(database=name).render_as_string(hide_password=False))
    original = create_database_engine(values["MIGRATION_DATABASE_URL"])
    created = False
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
            db.execute(text(f'CREATE DATABASE "{name}"'))
        created = True
        run_tool("pg_restore", source_url.set(database=name).render_as_string(hide_password=False),
                 ["--exit-on-error", "--no-owner", "--no-privileges", str(Path(backup_path).resolve())])
        with original.connect() as source, restored.connect() as target:
            before, before_pharmacies = reconstruct(source)
            after, after_pharmacies = reconstruct(target)
            if [r.model_dump(mode="json") for r in before] != [r.model_dump(mode="json") for r in after]:
                raise ValueError("Restored catalogue differs from the source database.")
            if [r.model_dump(mode="json") for r in before_pharmacies] != [r.model_dump(mode="json") for r in after_pharmacies]:
                raise ValueError("Restored pharmacy directory differs from the source database.")
            if source.execute(select(quota_state).order_by(quota_state.c.scope)).all() != target.execute(select(quota_state).order_by(quota_state.c.scope)).all():
                raise ValueError("Quota state changed between backup and verification; repeat while inference is idle.")
            for table in (evaluation_budgets, quota_imports):
                order = list(table.primary_key.columns)
                if source.execute(select(table).order_by(*order)).all() != target.execute(select(table).order_by(*order)).all():
                    raise ValueError("Restored quota accounting differs from the backup source.")
            if target.scalar(select(func.count()).select_from(conversations)) != 0:
                raise ValueError("Backup unexpectedly retained temporary conversations.")
        return {"restore_verified": True, "presentations": len(after), "pharmacies": len(after_pharmacies),
                "quota_state_preserved": True, "temporary_history_absent": True}
    finally:
        restored.dispose()
        original.dispose()
        if created:
            assert name.startswith("pharmacy_backup_verify_") and name.replace("_", "").isalnum()
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
                db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "verify"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--env-file", type=Path, default=ENV)
    args = parser.parse_args()
    try:
        values = configuration(args.env_file)
        result = backup(values, args.path) if args.action == "backup" else verify_backup(values, args.path)
    except Exception:
        parser.exit(1, "Backup operation failed; no existing database was overwritten. Check service/client readiness and use a new output path.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
