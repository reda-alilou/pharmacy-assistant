"""Repository paths independent of package depth and editable/wheel installation."""

import os
from pathlib import Path
import tomllib


def project_root():
    explicit = os.environ.get("PHARMACY_PROJECT_ROOT")
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute() or not path.is_dir():
            raise ValueError("PHARMACY_PROJECT_ROOT must be an existing absolute directory.")
        return path.resolve()
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for parent in (start, *start.parents):
            manifest = parent / "pyproject.toml"
            if manifest.is_file():
                try:
                    values = tomllib.loads(manifest.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if values.get("project", {}).get("name") == "pharmacy-assistant":
                    return parent.resolve()
    # Installed applications need no source checkout in PostgreSQL mode.
    # Only this explicit working directory is eligible for a local .env file.
    return Path.cwd().resolve()


ROOT = project_root()
ENV_FILE = ROOT / ".env"
