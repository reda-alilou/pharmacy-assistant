"""Fingerprint and lock resumable live runs; saved output is never a live substitute."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from pharmacy_assistant.config import Settings
from pharmacy_assistant.nlu import PROMPT_VERSION, SYSTEM_PROMPT
from pharmacy_assistant.nlu_models import Interpretation


def fingerprint(settings: Settings, cases: list[dict]) -> str:
    configuration = {
        "provider": settings.inference_provider, "model": settings.inference_model,
        "output_mode": settings.inference_output_mode, "prompt_version": PROMPT_VERSION,
        "prompt": SYSTEM_PROMPT, "schema": Interpretation.model_json_schema(), "cases": cases,
        "max_output_tokens": getattr(settings, f"{settings.inference_provider}_max_" + (
            "output_tokens" if settings.inference_provider == "gemini" else "completion_tokens")),
    }
    return hashlib.sha256(json.dumps(configuration, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@contextmanager
def report_lock(output: Path):
    """OS lock is released even after a process crash; lock file may remain."""
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = output.with_suffix(output.suffix + ".lock").open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise ValueError("This report is already in use by another evaluation process.") from None
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
