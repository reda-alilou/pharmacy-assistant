"""AMMPS medication packaging identification - OCR branch."""

from .catalog import Catalog, CatalogError, load_catalog
from .config import DEFAULT_WEIGHTS, MATCH_FIELDS, Settings
from .matching import FuzzyMatcher
from .models import (
    IdentificationResult,
    MatchResult,
    MedicationRecord,
    OCRResult,
    OCRToken,
)
from .ocr import EasyOCREngine, OCREngine, preprocess_image
from .pipeline import IdentificationPipeline

__all__ = [
    "Catalog",
    "CatalogError",
    "DEFAULT_WEIGHTS",
    "EasyOCREngine",
    "FuzzyMatcher",
    "IdentificationPipeline",
    "IdentificationResult",
    "MATCH_FIELDS",
    "MatchResult",
    "MedicationRecord",
    "OCREngine",
    "OCRResult",
    "OCRToken",
    "Settings",
    "load_catalog",
    "preprocess_image",
]
