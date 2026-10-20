"""Atomic report writes shared by offline scoring and explicit live tools."""
import json
from pathlib import Path
from pharmacy_infrastructure.paths import ROOT


def validate_output(path):
    target=Path(path).resolve()
    for directory in ('data','reports','archive'):
        if target.is_relative_to((ROOT/directory).resolve()):
            raise ValueError('Generated reports belong in artifacts; historical evidence and data inputs are read-only.')

def write_report(path: Path, report: dict):
    validate_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
