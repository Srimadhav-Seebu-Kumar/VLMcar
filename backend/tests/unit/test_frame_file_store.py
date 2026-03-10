from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from backend.app.services.storage.files import FrameFileStore


def test_frame_file_store_saves_session_frame_file(tmp_path: Path) -> None:
    store = FrameFileStore(artifacts_dir=tmp_path)

    result = store.save_frame(
        session_id=uuid4(),
        seq=5,
        timestamp_ms=1710000000000,
        payload=b"frame-bytes",
    )

    assert result.payload_size_bytes == 11
    assert result.file_path.exists()
    assert result.sha256
