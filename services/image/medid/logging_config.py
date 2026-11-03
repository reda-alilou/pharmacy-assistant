from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_FILE = PROJECT_ROOT / "logs" / "medid.log"
_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_CONFIGURED = False


def configure_logging(
    level: str | int | None = None,
    log_file: str | Path | None = None,
    force: bool = False,
) -> None:
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    resolved_level = level or os.environ.get("MEDID_LOG_LEVEL", "INFO")
    if isinstance(resolved_level, str):
        resolved_level = resolved_level.upper()

    logger = logging.getLogger("medid")
    logger.setLevel(resolved_level)
    logger.propagate = False

    if force or logger.handlers:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is None:
        log_file = os.environ.get("MEDID_LOG_FILE", str(DEFAULT_LOG_FILE))

    log_file_text = str(log_file).strip()
    if log_file_text.lower() not in {"", "none", "off"}:
        path = Path(log_file_text).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _CONFIGURED = True
    logger.debug("Logging configured at level %s", resolved_level)


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    if name.startswith("medid"):
        return logging.getLogger(name)
    return logging.getLogger(f"medid.{name}")
