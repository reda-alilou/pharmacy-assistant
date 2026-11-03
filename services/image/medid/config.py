from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = (
    PROJECT_ROOT / "data" / "metadata" / "ammps_medications_enriched.jsonl"
)

MATCH_FIELDS: tuple[str, ...] = (
    "brand_name",
    "active_substance",
    "epi",
    "dosage",
    "form",
    "presentation",
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "brand_name": 0.35,
    "active_substance": 0.25,
    "epi": 0.10,
    "dosage": 0.15,
    "form": 0.075,
    "presentation": 0.075,
}

ScoringMode = Literal["field_aware", "baseline"]
OCR_LANGUAGES = ("fr", "ar", "en")


def default_catalog_path() -> Path:
    configured = os.environ.get("MEDID_CATALOG_PATH")
    if configured:
        return Path(configured)
    if DEFAULT_CATALOG_PATH.is_file():
        return DEFAULT_CATALOG_PATH
    return PROJECT_ROOT.parents[1] / "data" / "imports" / "ammps_medications_enriched.jsonl"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def default_ocr_languages() -> tuple[str, ...]:
    raw = os.environ.get("MEDID_OCR_LANGUAGES", "fr")
    languages = tuple(
        part.strip() for part in raw.split(",") if part.strip()
    )
    return languages or ("fr",)


def default_ocr_min_confidence() -> float:
    try:
        return float(
            os.environ.get("MEDID_OCR_MIN_CONFIDENCE", "0.20")
        )
    except ValueError:
        return 0.20


def default_use_gpu() -> bool:
    return _env_bool("MEDID_USE_GPU", False)


def default_model_dir() -> Path | None:
    raw = os.environ.get("MEDID_MODEL_DIR")
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True)
class Settings:
    catalog_path: Path = field(default_factory=default_catalog_path)
    ocr_languages: tuple[str, ...] = field(
        default_factory=default_ocr_languages
    )
    ocr_min_confidence: float = field(
        default_factory=default_ocr_min_confidence
    )
    use_gpu: bool = field(default_factory=default_use_gpu)
    model_dir: Path | None = field(default_factory=default_model_dir)
    top_k: int = 5
    min_score: float = 0.0
    scoring_mode: ScoringMode = "field_aware"
    group_presentations: bool = True
    weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )
    max_image_side: int = 2400
    min_image_side: int = 900

    def with_updates(self, **changes: object) -> Settings:
        values = {
            "catalog_path": self.catalog_path,
            "ocr_languages": self.ocr_languages,
            "ocr_min_confidence": self.ocr_min_confidence,
            "use_gpu": self.use_gpu,
            "model_dir": self.model_dir,
            "top_k": self.top_k,
            "min_score": self.min_score,
            "scoring_mode": self.scoring_mode,
            "group_presentations": self.group_presentations,
            "weights": self.weights,
            "max_image_side": self.max_image_side,
            "min_image_side": self.min_image_side,
        }
        values.update(changes)
        return Settings(**values)
