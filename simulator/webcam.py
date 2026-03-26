from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import Action, DeviceMode
from simulator.control_client import BackendControlError, ControlFrameRequest
from simulator.fallback import build_stop_command


class ControlClientProtocol(Protocol):
    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse: ...


class CaptureDevice(Protocol):
    """Protocol for camera devices used by webcam loop."""

    def isOpened(self) -> bool: ...

    def read(self) -> tuple[bool, Any]: ...

    def set(self, prop_id: int, value: float) -> bool: ...

    def release(self) -> None: ...


FrameEncoder = Callable[[Any, int], tuple[bool, bytes]]
CaptureFactory = Callable[[int], CaptureDevice]


@dataclass(frozen=True)
class WebcamConfig:
    """Runtime configuration for laptop camera control loop."""

    device_id: str
    camera_index: int
    frame_width: int
    frame_height: int
    jpeg_quality: int
    max_frames: int
    stop_on_backend_stop: bool
    show_preview: bool
    mode: DeviceMode = DeviceMode.AUTO
    sleep_per_frame_s: float = 0.0


@dataclass(frozen=True)
class WebcamResult:
    """Summary for one webcam backend loop session."""

    session_id: UUID
    frames_processed: int
    backend_errors: int
    stopped_by_backend: bool
    stopped_by_capture_error: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "session_id": str(self.session_id),
            "frames_processed": self.frames_processed,
            "backend_errors": self.backend_errors,
            "stopped_by_backend": self.stopped_by_backend,
            "stopped_by_capture_error": self.stopped_by_capture_error,
        }


def run_webcam_loop(
    *,
    config: WebcamConfig,
    control_client: ControlClientProtocol,
    session_id: UUID | None = None,
    capture_factory: CaptureFactory | None = None,
    frame_encoder: FrameEncoder | None = None,
) -> WebcamResult:
    """Capture laptop camera frames and send them to backend control API."""

    cv2_mod: Any | None = None
    if capture_factory is None or frame_encoder is None or config.show_preview:
        cv2_mod = _import_cv2()

    active_capture_factory = capture_factory
    if active_capture_factory is None:
        if cv2_mod is None:
            raise RuntimeError("OpenCV is required when capture_factory is not provided")

        def _default_capture_factory(camera_index: int) -> CaptureDevice:
            return cast(CaptureDevice, cv2_mod.VideoCapture(camera_index))

        active_capture_factory = _default_capture_factory

    active_encoder = frame_encoder
    if active_encoder is None:
        if cv2_mod is None:
            raise RuntimeError("OpenCV is required when frame_encoder is not provided")
        active_encoder = _build_default_encoder(cv2_mod)

    capture = active_capture_factory(config.camera_index)
    if not capture.isOpened():
        raise RuntimeError(f"camera index {config.camera_index} could not be opened")

    if cv2_mod is not None:
        capture.set(cv2_mod.CAP_PROP_FRAME_WIDTH, float(config.frame_width))
        capture.set(cv2_mod.CAP_PROP_FRAME_HEIGHT, float(config.frame_height))

    # Warmup: discard initial frames while camera auto-exposure settles
    time.sleep(1)
    for _ in range(5):
        capture.read()

    resolved_session = session_id or uuid4()
    frames_processed = 0
    backend_errors = 0
    stopped_by_backend = False
    stopped_by_capture_error = False

    try:
        for seq in range(1, config.max_frames + 1):
            ok, frame = capture.read()
            if not ok:
                stopped_by_capture_error = True
                break

            encoded_ok, jpeg_bytes = active_encoder(frame, config.jpeg_quality)
            if not encoded_ok:
                stopped_by_capture_error = True
                break

            timestamp_ms = int(time.time() * 1000)
            try:
                command = control_client.send_frame(
                    ControlFrameRequest(
                        image_jpeg=jpeg_bytes,
                        device_id=config.device_id,
                        seq=seq,
                        timestamp_ms=timestamp_ms,
                        frame_width=config.frame_width,
                        frame_height=config.frame_height,
                        jpeg_quality=config.jpeg_quality,
                        mode=config.mode,
                        session_id=resolved_session,
                    )
                )
            except BackendControlError as exc:
                backend_errors += 1
                command = build_stop_command(
                    seq=seq,
                    session_id=resolved_session,
                    reason_code="WEBCAM_BACKEND_ERROR",
                    message=str(exc),
                    safe_to_execute=False,
                )

            frames_processed = seq
            print(command.model_dump_json())

            if config.show_preview and cv2_mod is not None:
                _render_preview(cv2_mod=cv2_mod, frame=frame, command_action=command.action.value)
                key = cv2_mod.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

            if command.action is Action.STOP and config.stop_on_backend_stop:
                stopped_by_backend = True
                break

            if config.sleep_per_frame_s > 0:
                time.sleep(config.sleep_per_frame_s)
    finally:
        capture.release()
        if config.show_preview and cv2_mod is not None:
            cv2_mod.destroyAllWindows()

    return WebcamResult(
        session_id=resolved_session,
        frames_processed=frames_processed,
        backend_errors=backend_errors,
        stopped_by_backend=stopped_by_backend,
        stopped_by_capture_error=stopped_by_capture_error,
    )


def _import_cv2() -> Any:
    import cv2

    return cv2


def _build_default_encoder(cv2_mod: Any) -> FrameEncoder:
    def encode(frame: Any, quality: int) -> tuple[bool, bytes]:
        encoded_ok, encoded = cv2_mod.imencode(
            ".jpg",
            frame,
            [int(cv2_mod.IMWRITE_JPEG_QUALITY), int(quality)],
        )
        if not encoded_ok:
            return (False, b"")
        return (True, encoded.tobytes())

    return encode


def _render_preview(*, cv2_mod: Any, frame: Any, command_action: str) -> None:
    annotated = frame.copy()
    cv2_mod.putText(
        annotated,
        f"Action: {command_action}",
        (10, 30),
        cv2_mod.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        2,
    )
    cv2_mod.imshow("VLM RC Car Laptop Camera Loop", annotated)
