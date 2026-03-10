from __future__ import annotations

from backend.app.services.preprocess import FrameQualityMetrics
from backend.app.services.quality_gate import evaluate_quality


def test_quality_gate_accepts_good_frame_metrics() -> None:
    decision = evaluate_quality(
        metrics=FrameQualityMetrics(
            mean_brightness=120.0,
            contrast=45.0,
            blur_score=50.0,
            quality_score=0.85,
        ),
        min_quality_score=0.2,
        min_brightness=20.0,
        max_brightness=235.0,
        min_blur_score=2.0,
    )

    assert decision.accepted is True
    assert decision.reason_code == "FRAME_QUALITY_OK"


def test_quality_gate_rejects_dark_frame() -> None:
    decision = evaluate_quality(
        metrics=FrameQualityMetrics(
            mean_brightness=3.0,
            contrast=10.0,
            blur_score=30.0,
            quality_score=0.5,
        ),
        min_quality_score=0.2,
        min_brightness=20.0,
        max_brightness=235.0,
        min_blur_score=2.0,
    )

    assert decision.accepted is False
    assert decision.reason_code == "FRAME_TOO_DARK"
