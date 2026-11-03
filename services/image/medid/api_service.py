from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .api_schemas import (
    CatalogStatsOut,
    HealthOut,
    IdentificationOut,
    IdentifyOptions,
    identification_out,
    validate_weights,
)
from .catalog import Catalog, load_catalog
from .config import MATCH_FIELDS, Settings
from .logging_config import get_logger
from .matching import FuzzyMatcher
from .normalization import normalize_text
from .ocr import EasyOCREngine, OCREngine
from .pipeline import IdentificationPipeline

logger = get_logger("api.service")

SERVICE_NAME = "medid-api"
SERVICE_VERSION = "0.2.0"


class MedicationAPIService:
    def __init__(
        self,
        settings: Settings | None = None,
        catalog: Catalog | None = None,
        ocr_engine: OCREngine | None = None,
    ) -> None:
        self.settings = settings or Settings()
        logger.info(
            "Starting %s %s with catalogue %s",
            SERVICE_NAME,
            SERVICE_VERSION,
            self.settings.catalog_path,
        )
        self.catalog = catalog or load_catalog(self.settings.catalog_path)
        self.ocr_engine = ocr_engine or EasyOCREngine(
            languages=self.settings.ocr_languages,
            use_gpu=self.settings.use_gpu,
            max_image_side=self.settings.max_image_side,
            min_image_side=self.settings.min_image_side,
            model_storage_directory=self.settings.model_dir,
        )
        self.pipeline = self._build_pipeline(self.settings)
        self.stats = self._build_stats()
        logger.info(
            "API service ready: %d records, %d brands, %d groups",
            self.stats.records,
            self.stats.unique_brands,
            self.stats.presentation_groups,
        )

    def _build_pipeline(self, settings: Settings) -> IdentificationPipeline:
        return IdentificationPipeline(
            catalog=self.catalog,
            matcher=FuzzyMatcher(
                weights=settings.weights,
                mode=settings.scoring_mode,
            ),
            ocr_engine=self.ocr_engine,
            settings=settings,
        )

    def _pipeline_for(self, options: IdentifyOptions) -> IdentificationPipeline:
        validate_weights(options.weights)
        changes: dict[str, object] = {}
        if options.top_k is not None:
            changes["top_k"] = options.top_k
        if options.min_score is not None:
            changes["min_score"] = options.min_score
        if options.scoring_mode is not None:
            changes["scoring_mode"] = options.scoring_mode
        if options.group_presentations is not None:
            changes["group_presentations"] = options.group_presentations
        if options.ocr_min_confidence is not None:
            changes["ocr_min_confidence"] = options.ocr_min_confidence
        if options.weights is not None:
            changes["weights"] = {
                **dict(self.settings.weights),
                **options.weights,
            }
        if not changes:
            return self.pipeline
        return self._build_pipeline(self.settings.with_updates(**changes))

    def _build_stats(self) -> CatalogStatsOut:
        brands = {
            normalize_text(record.brand_name)
            for record in self.catalog.records
        }
        groups = {
            (
                normalize_text(record.brand_name),
                normalize_text(record.dosage),
                normalize_text(record.active_substance),
                normalize_text(record.form),
            )
            for record in self.catalog.records
        }
        path = Path(self.catalog.source_path)
        stat = path.stat()
        return CatalogStatsOut(
            records=self.catalog.size,
            unique_brands=len(brands),
            presentation_groups=len(groups),
            duplicate_ids=self.catalog.duplicate_count,
            source_path=str(path),
            source_size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(
                stat.st_mtime, tz=UTC
            ).isoformat(),
            match_fields=list(MATCH_FIELDS),
        )

    def health(self) -> HealthOut:
        return HealthOut(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            catalog_size=self.catalog.size,
            ocr_languages=list(self.settings.ocr_languages),
            use_gpu=self.settings.use_gpu,
            ocr_min_confidence=self.settings.ocr_min_confidence,
        )

    def identify_text(
        self,
        text: str,
        options: IdentifyOptions | None = None,
        request_id: str | None = None,
    ) -> IdentificationOut:
        options = options or IdentifyOptions()
        logger.info(
            "Text identification requested (request_id=%s, chars=%d)",
            request_id,
            len(text),
        )
        result = self._pipeline_for(options).identify_text(
            text,
            top_k=options.top_k,
            request_id=request_id,
        )
        return identification_out(result)

    def identify_image(
        self,
        image_bytes: bytes,
        options: IdentifyOptions | None = None,
        request_id: str | None = None,
    ) -> IdentificationOut:
        options = options or IdentifyOptions()
        logger.info(
            "Image identification requested (request_id=%s, bytes=%d)",
            request_id,
            len(image_bytes),
        )
        result = self._pipeline_for(options).identify_image(
            image_bytes,
            top_k=options.top_k,
            request_id=request_id,
        )
        return identification_out(result)
