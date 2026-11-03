from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Protocol

from PIL import Image, ImageOps

from .logging_config import get_logger
from .models import OCRResult, OCRToken

logger = get_logger("ocr")


class OCREngine(Protocol):
    def read(
        self, image_bytes: bytes, min_confidence: float = 0.20
    ) -> OCRResult: ...


def preprocess_image(
    image_bytes: bytes,
    max_side: int = 2400,
    min_side: int = 900,
) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    width, height = image.size
    scale = 1.0
    if min_side > 0 and min(width, height) < min_side:
        scale = min_side / min(width, height)
    if max_side > 0 and max(width, height) * scale > max_side:
        scale = max_side / max(width, height)

    if abs(scale - 1.0) > 1e-3:
        new_size = (
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    return image


class EasyOCREngine:
    def __init__(
        self,
        languages: tuple[str, ...] = ("fr",),
        use_gpu: bool = False,
        max_image_side: int = 2400,
        min_image_side: int = 900,
        model_storage_directory: Path | None = None,
    ) -> None:
        self.languages = languages
        self.use_gpu = use_gpu
        self.max_image_side = max_image_side
        self.min_image_side = min_image_side
        self.model_storage_directory = model_storage_directory
        self._reader = None
        logger.info(
            "OCR engine configured: languages=%s gpu=%s "
            "image_side=%s..%s",
            ",".join(languages),
            use_gpu,
            min_image_side,
            max_image_side,
        )

    @property
    def reader(self):
        if self._reader is None:
            logger.info("Initializing EasyOCR reader...")
            started = perf_counter()
            import easyocr

            model_dir = self.model_storage_directory
            user_network_dir = None
            if model_dir is not None:
                model_dir.mkdir(parents=True, exist_ok=True)
                user_network_dir = model_dir / "user_network"
                user_network_dir.mkdir(parents=True, exist_ok=True)
            self._reader = easyocr.Reader(
                list(self.languages),
                gpu=self.use_gpu,
                verbose=False,
                model_storage_directory=(
                    str(model_dir) if model_dir is not None else None
                ),
                user_network_directory=(
                    str(user_network_dir)
                    if user_network_dir is not None
                    else None
                ),
            )
            logger.info(
                "EasyOCR reader ready in %.0f ms",
                (perf_counter() - started) * 1000,
            )
        return self._reader

    def read(
        self, image_bytes: bytes, min_confidence: float = 0.20
    ) -> OCRResult:
        import numpy as np

        started = perf_counter()
        logger.info(
            "OCR started: %.1f KB, languages=%s, min_confidence=%.2f",
            len(image_bytes) / 1024,
            ",".join(self.languages),
            min_confidence,
        )
        image = preprocess_image(
            image_bytes,
            max_side=self.max_image_side,
            min_side=self.min_image_side,
        )
        logger.debug("Preprocessed image size: %dx%d", image.width, image.height)

        raw_results = self.reader.readtext(
            np.asarray(image),
            detail=1,
            paragraph=False,
        )

        tokens: list[OCRToken] = []
        for bbox, text, confidence in raw_results:
            cleaned = str(text).strip()
            if not cleaned or float(confidence) < min_confidence:
                continue
            points = tuple(
                (float(point[0]), float(point[1])) for point in bbox
            )
            tokens.append(
                OCRToken(
                    text=cleaned,
                    confidence=float(confidence),
                    bbox=points,
                )
            )

        result = OCRResult(
            text=" ".join(token.text for token in tokens),
            tokens=tuple(tokens),
            languages=self.languages,
            width=image.width,
            height=image.height,
        )
        logger.info(
            "OCR finished: %d token(s), %d raw detection(s), %.0f ms, "
            "text=%r",
            len(tokens),
            len(raw_results),
            (perf_counter() - started) * 1000,
            result.text[:160],
        )
        return result
