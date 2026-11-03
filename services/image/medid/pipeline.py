from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from .catalog import Catalog, load_catalog
from .config import Settings
from .logging_config import get_logger
from .matching import FuzzyMatcher
from .models import IdentificationResult, OCRResult
from .ocr import EasyOCREngine, OCREngine
from .workflow import WorkflowTracker

logger = get_logger("pipeline")


class IdentificationPipeline:
    def __init__(
        self,
        catalog: Catalog,
        matcher: FuzzyMatcher,
        ocr_engine: OCREngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.catalog = catalog
        self.matcher = matcher
        self.ocr_engine = ocr_engine
        self.settings = settings or Settings()

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        catalog: Catalog | None = None,
        ocr_engine: OCREngine | None = None,
    ) -> IdentificationPipeline:
        catalog = catalog or load_catalog(settings.catalog_path)
        ocr_engine = ocr_engine or EasyOCREngine(
            languages=settings.ocr_languages,
            use_gpu=settings.use_gpu,
            max_image_side=settings.max_image_side,
            min_image_side=settings.min_image_side,
            model_storage_directory=settings.model_dir,
        )
        return cls(
            catalog=catalog,
            matcher=FuzzyMatcher(
                weights=settings.weights,
                mode=settings.scoring_mode,
            ),
            ocr_engine=ocr_engine,
            settings=settings,
        )

    def identify_image(
        self,
        image_bytes: bytes,
        top_k: int | None = None,
        request_id: str | None = None,
    ) -> IdentificationResult:
        request_id = request_id or uuid4().hex
        tracker = WorkflowTracker()
        tracker.add(
            "request",
            f"Image identification request {request_id} received",
        )
        if not image_bytes:
            logger.warning("Request %s rejected: empty image", request_id)
            tracker.add("validation", "Request rejected: image is empty")
            raise ValueError("The image is empty.")
        if self.ocr_engine is None:
            logger.error(
                "Request %s rejected: no OCR engine configured",
                request_id,
            )
            tracker.add("validation", "Request rejected: no OCR engine")
            raise RuntimeError("No OCR engine is configured.")

        tracker.add(
            "image",
            f"Image received ({len(image_bytes) / 1024:.1f} KB)",
        )
        start = perf_counter()
        ocr_started = perf_counter()
        tracker.add("ocr", "Running OCR...")
        try:
            ocr_result = self.ocr_engine.read(
                image_bytes,
                min_confidence=self.settings.ocr_min_confidence,
            )
        except Exception:
            logger.exception("OCR failed for request %s", request_id)
            raise
        tracker.add(
            "ocr",
            f"OCR extracted {len(ocr_result.tokens)} token(s): "
            f"{ocr_result.text[:160]!r}",
            (perf_counter() - ocr_started) * 1000,
        )
        return self._finish(
            query=ocr_result.text,
            ocr_result=ocr_result,
            start=start,
            top_k=top_k,
            tracker=tracker,
            request_id=request_id,
        )

    def identify_text(
        self,
        text: str,
        top_k: int | None = None,
        request_id: str | None = None,
    ) -> IdentificationResult:
        request_id = request_id or uuid4().hex
        tracker = WorkflowTracker()
        tracker.add(
            "request",
            f"Text identification request {request_id} received",
        )
        start = perf_counter()
        ocr_result = OCRResult(
            text=text.strip(),
            languages=self.settings.ocr_languages,
        )
        tracker.add("text", f"Input text: {ocr_result.text[:160]!r}")
        return self._finish(
            query=ocr_result.text,
            ocr_result=ocr_result,
            start=start,
            top_k=top_k,
            tracker=tracker,
            request_id=request_id,
        )

    def _finish(
        self,
        query: str,
        ocr_result: OCRResult,
        start: float,
        top_k: int | None,
        tracker: WorkflowTracker,
        request_id: str,
    ) -> IdentificationResult:
        match_started = perf_counter()
        tracker.add(
            "matching",
            f"Ranking query against {self.catalog.size} records "
            f"(mode={self.matcher.mode})",
        )
        try:
            matches = self.matcher.rank(
                query=query,
                catalog=self.catalog,
                top_k=top_k or self.settings.top_k,
                min_score=self.settings.min_score,
                group_presentations=self.settings.group_presentations,
            )
        except Exception:
            logger.exception("Matching failed for request %s", request_id)
            raise
        best_text = (
            f", best={matches[0].record.brand_name!r} "
            f"score={matches[0].score:.1f}"
            if matches
            else ""
        )
        tracker.add(
            "matching",
            f"Found {len(matches)} match(es){best_text}",
            (perf_counter() - match_started) * 1000,
        )

        elapsed_ms = (perf_counter() - start) * 1000
        tracker.add(
            "complete",
            f"Identification completed in {elapsed_ms:.0f} ms",
        )
        logger.info(
            "Request %s complete: query=%r matches=%d elapsed=%.0f ms",
            request_id,
            query,
            len(matches),
            elapsed_ms,
        )
        return IdentificationResult(
            query=query,
            matches=matches,
            ocr=ocr_result,
            catalog_size=self.catalog.size,
            elapsed_ms=elapsed_ms,
            scoring_mode=self.matcher.mode,
            grouped=self.settings.group_presentations,
            request_id=request_id,
            workflow=tracker.events,
        )
