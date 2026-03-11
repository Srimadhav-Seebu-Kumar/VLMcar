from __future__ import annotations

from uuid import UUID, uuid4

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import Action
from simulator.control_client import ControlFrameRequest
from simulator.webcam import WebcamConfig, run_webcam_loop


def _command(seq: int, session_id: UUID, action: Action) -> CommandResponse:
    pulse = 220 if action is not Action.STOP else 0
    pwm = 110 if action is not Action.STOP else 0
    return CommandResponse(
        trace_id=uuid4(),
        session_id=session_id,
        seq=seq,
        action=action,
        left_pwm=pwm,
        right_pwm=pwm,
        duration_ms=pulse,
        confidence=0.9,
        reason_code="WEBCAM_TEST",
        message="ok",
        backend_latency_ms=1,
        model_latency_ms=1,
        safe_to_execute=True,
    )


class FakeCapture:
    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self._released = False

    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, bytes]:
        if not self._frames:
            return (False, b"")
        value = self._frames.pop(0)
        return (True, value)

    def set(self, prop_id: int, value: float) -> bool:
        _ = (prop_id, value)
        return True

    def release(self) -> None:
        self._released = True


class ScriptedClient:
    def __init__(self, actions: list[Action]) -> None:
        self._actions = actions
        self._idx = 0

    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse:
        action = self._actions[self._idx]
        self._idx += 1
        session = frame.session_id or uuid4()
        return _command(seq=frame.seq, session_id=session, action=action)


def test_webcam_loop_stops_after_backend_stop_command() -> None:
    capture = FakeCapture(frames=[b"a", b"b", b"c"])
    client = ScriptedClient(actions=[Action.FORWARD, Action.STOP, Action.FORWARD])

    result = run_webcam_loop(
        config=WebcamConfig(
            device_id="laptop-cam",
            camera_index=0,
            frame_width=640,
            frame_height=480,
            jpeg_quality=80,
            max_frames=10,
            stop_on_backend_stop=True,
            show_preview=False,
        ),
        control_client=client,
        capture_factory=lambda _idx: capture,
        frame_encoder=lambda frame, _quality: (True, bytes(frame)),
    )

    assert result.frames_processed == 2
    assert result.stopped_by_backend is True
    assert result.stopped_by_capture_error is False


def test_webcam_loop_marks_capture_error_when_camera_read_fails() -> None:
    capture = FakeCapture(frames=[])
    client = ScriptedClient(actions=[Action.FORWARD])

    result = run_webcam_loop(
        config=WebcamConfig(
            device_id="laptop-cam",
            camera_index=0,
            frame_width=640,
            frame_height=480,
            jpeg_quality=80,
            max_frames=5,
            stop_on_backend_stop=True,
            show_preview=False,
        ),
        control_client=client,
        capture_factory=lambda _idx: capture,
        frame_encoder=lambda frame, _quality: (True, bytes(frame)),
    )

    assert result.frames_processed == 0
    assert result.stopped_by_capture_error is True
