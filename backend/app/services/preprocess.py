from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class FrameQualityMetrics:
    """Computed frame-quality metrics used for safety gating and analysis."""

    mean_brightness: float
    contrast: float
    blur_score: float
    quality_score: float


@dataclass(frozen=True)
class PreprocessResult:
    """Normalized image bytes plus quality metadata."""

    normalized_jpeg: bytes
    width: int
    height: int
    metrics: FrameQualityMetrics


def _compute_blur_score(gray_array: np.ndarray) -> float:
    gradient_x, gradient_y = np.gradient(gray_array)
    return float(np.var(gradient_x) + np.var(gradient_y))


def _quality_score(mean_brightness: float, contrast: float, blur_score: float) -> float:
    brightness_factor = max(0.0, 1.0 - abs(mean_brightness - 127.5) / 127.5)
    contrast_factor = min(1.0, contrast / 64.0)
    blur_factor = min(1.0, blur_score / 150.0)
    return round(0.4 * brightness_factor + 0.3 * contrast_factor + 0.3 * blur_factor, 4)


def preprocess_frame(image_bytes: bytes) -> PreprocessResult:
    """Decode JPEG, normalize color space, and compute quality metrics."""

    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    gray = image.convert("L")
    gray_array = np.asarray(gray, dtype=np.float32)

    mean_brightness = float(np.mean(gray_array))
    contrast = float(np.std(gray_array))
    blur_score = _compute_blur_score(gray_array)
    quality = _quality_score(mean_brightness, contrast, blur_score)

    output = BytesIO()
    image.save(output, format="JPEG", quality=85, optimize=True)

    return PreprocessResult(
        normalized_jpeg=output.getvalue(),
        width=image.width,
        height=image.height,
        metrics=FrameQualityMetrics(
            mean_brightness=round(mean_brightness, 4),
            contrast=round(contrast, 4),
            blur_score=round(blur_score, 4),
            quality_score=quality,
        ),
    )
