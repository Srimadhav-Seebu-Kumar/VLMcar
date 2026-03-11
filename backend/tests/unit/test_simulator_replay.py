from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import Action
from simulator.control_client import ControlFrameRequest
from simulator.replay import ReplayConfig, replay_episode


def _write_jpeg(path: Path, color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (32, 24), color=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    path.write_bytes(buffer.getvalue())


def _command(seq: int, session_id: UUID, action: Action) -> CommandResponse:
    return CommandResponse(
        trace_id=uuid4(),
        session_id=session_id,
        seq=seq,
        action=action,
        left_pwm=100 if action is not Action.STOP else 0,
        right_pwm=100 if action is not Action.STOP else 0,
        duration_ms=220 if action is not Action.STOP else 0,
        confidence=0.9,
        reason_code="REPLAY_TEST",
        message="ok",
        backend_latency_ms=3,
        model_latency_ms=2,
        safe_to_execute=True,
    )


class ScriptedReplayClient:
    def __init__(self, actions: list[Action]) -> None:
        self._actions = actions
        self._idx = 0

    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse:
        action = self._actions[self._idx]
        self._idx += 1
        session = frame.session_id or uuid4()
        return _command(seq=frame.seq, session_id=session, action=action)


def test_replay_matches_actions_and_writes_output(tmp_path: Path) -> None:
    image1 = tmp_path / "frame1.jpg"
    image2 = tmp_path / "frame2.jpg"
    _write_jpeg(image1, (120, 120, 120))
    _write_jpeg(image2, (10, 220, 20))

    session_id = uuid4()
    steps_path = tmp_path / "steps.jsonl"
    steps = [
        {
            "seq": 1,
            "timestamp_ms": 1710000000001,
            "session_id": str(session_id),
            "frame_path": str(image1),
            "frame_width": 32,
            "frame_height": 24,
            "jpeg_quality": 80,
            "action": "FORWARD",
        },
        {
            "seq": 2,
            "timestamp_ms": 1710000000002,
            "session_id": str(session_id),
            "frame_path": str(image2),
            "frame_width": 32,
            "frame_height": 24,
            "jpeg_quality": 80,
            "action": "STOP",
        },
    ]
    with steps_path.open("w", encoding="utf-8") as handle:
        for row in steps:
            handle.write(json.dumps(row) + "\n")

    output_path = tmp_path / "replay.jsonl"
    result = replay_episode(
        config=ReplayConfig(
            steps_jsonl_path=steps_path,
            output_jsonl_path=output_path,
            device_id="sim-replay-01",
            jpeg_quality=80,
            stop_on_backend_stop=True,
        ),
        control_client=ScriptedReplayClient(actions=[Action.FORWARD, Action.STOP]),
    )

    assert result.total_steps == 2
    assert result.matched_actions == 2
    assert output_path.exists()
