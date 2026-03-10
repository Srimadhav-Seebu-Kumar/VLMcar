from __future__ import annotations

from io import BytesIO

from PIL import Image

from backend.app.services.preprocess import preprocess_frame


def test_preprocess_frame_returns_metrics_and_normalized_bytes() -> None:
    image = Image.new("RGB", (24, 24), color=(80, 120, 200))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    result = preprocess_frame(buffer.getvalue())

    assert result.width == 24
    assert result.height == 24
    assert result.normalized_jpeg
    assert 0.0 <= result.metrics.quality_score <= 1.0
    assert result.metrics.mean_brightness >= 0.0
