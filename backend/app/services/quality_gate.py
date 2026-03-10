from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.preprocess import FrameQualityMetrics


@dataclass(frozen=True)
class QualityGateDecision:
    """Outcome of frame quality validation before model inference."""

    accepted: bool
    reason_code: str
    message: str


def evaluate_quality(
    metrics: FrameQualityMetrics,
    min_quality_score: float,
    min_brightness: float,
    max_brightness: float,
    min_blur_score: float,
) -> QualityGateDecision:
    """Apply deterministic quality checks and return STOP rationale when rejected."""

    if metrics.mean_brightness < min_brightness:
        return QualityGateDecision(
            accepted=False,
            reason_code="FRAME_TOO_DARK",
            message="frame brightness below configured minimum",
        )

    if metrics.mean_brightness > max_brightness:
        return QualityGateDecision(
            accepted=False,
            reason_code="FRAME_TOO_BRIGHT",
            message="frame brightness above configured maximum",
        )

    if metrics.blur_score < min_blur_score:
        return QualityGateDecision(
            accepted=False,
            reason_code="FRAME_TOO_BLURRY",
            message="frame appears too low-detail for safe inference",
        )

    if metrics.quality_score < min_quality_score:
        return QualityGateDecision(
            accepted=False,
            reason_code="FRAME_QUALITY_LOW",
            message="composite quality score below threshold",
        )

    return QualityGateDecision(
        accepted=True,
        reason_code="FRAME_QUALITY_OK",
        message="frame quality accepted",
    )
