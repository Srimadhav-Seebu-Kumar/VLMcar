from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class StoredFrame:
    """Metadata for a frame persisted to disk."""

    file_path: Path
    payload_size_bytes: int
    sha256: str


class FrameFileStore:
    """Store raw frame payloads in a session-oriented directory structure."""

    def __init__(self, artifacts_dir: Path) -> None:
        self._artifacts_dir = artifacts_dir

    def save_frame(self, session_id: UUID, seq: int, timestamp_ms: int, payload: bytes) -> StoredFrame:
        frame_dir = self._artifacts_dir / "sessions" / str(session_id) / "frames"
        frame_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{seq:06d}_{timestamp_ms}.jpg"
        file_path = frame_dir / filename
        file_path.write_bytes(payload)

        checksum = hashlib.sha256(payload).hexdigest()
        return StoredFrame(
            file_path=file_path,
            payload_size_bytes=len(payload),
            sha256=checksum,
        )
