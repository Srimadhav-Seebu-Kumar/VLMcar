from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import Action
from simulator.control_client import BackendControlError, ControlFrameRequest
from simulator.episode import EpisodeConfig, EpisodeStatus, run_episode


def _command(
    *,
    seq: int,
    session_id: UUID,
    action: Action,
    duration_ms: int,
    reason_code: str = "TEST",
) -> CommandResponse:
    pwm = 120 if action is Action.FORWARD else 0
    return CommandResponse(
        trace_id=uuid4(),
        session_id=session_id,
        seq=seq,
        action=action,
        left_pwm=pwm,
        right_pwm=pwm,
        duration_ms=duration_ms,
        confidence=0.9,
        reason_code=reason_code,
        message="test",
        backend_latency_ms=2,
        model_latency_ms=1,
        safe_to_execute=True,
    )


class ScriptedClient:
    def __init__(self, actions: list[Action], *, duration_ms: int = 250) -> None:
        self._actions = actions
        self._duration_ms = duration_ms
        self._idx = 0

    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse:
        action = Action.STOP if self._idx >= len(self._actions) else self._actions[self._idx]
        self._idx += 1
        session = frame.session_id or uuid4()
        return _command(
            seq=frame.seq,
            session_id=session,
            action=action,
            duration_ms=self._duration_ms if action is not Action.STOP else 0,
        )


class ErrorClient:
    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse:
        _ = frame
        raise BackendControlError("simulated transport failure")


def test_episode_reaches_goal_with_forward_commands(tmp_path: Path) -> None:
    client = ScriptedClient(actions=[Action.FORWARD] * 20)
    result = run_episode(
        config=EpisodeConfig(
            map_name="straight_corridor",
            max_steps=20,
            output_root=tmp_path,
            frame_width=160,
            frame_height=120,
            jpeg_quality=75,
            device_id="sim-edge-01",
            save_topdown=False,
            sleep_per_step_s=0.0,
            stop_on_backend_stop=True,
        ),
        control_client=client,
    )

    assert result.status is EpisodeStatus.GOAL_REACHED
    assert result.goal_reached is True
    assert result.steps_jsonl_path.exists()


def test_episode_uses_stop_fallback_on_backend_error(tmp_path: Path) -> None:
    result = run_episode(
        config=EpisodeConfig(
            map_name="straight_corridor",
            max_steps=5,
            output_root=tmp_path,
            frame_width=160,
            frame_height=120,
            jpeg_quality=75,
            device_id="sim-edge-01",
            save_topdown=False,
            sleep_per_step_s=0.0,
            stop_on_backend_stop=True,
        ),
        control_client=ErrorClient(),
    )

    assert result.status is EpisodeStatus.BACKEND_ERROR
    lines = result.steps_jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    first_record = json.loads(lines[0])
    assert first_record["action"] == "STOP"
    assert first_record["reason_code"] == "SIM_BACKEND_ERROR"


def test_episode_stops_on_backend_stop(tmp_path: Path) -> None:
    client = ScriptedClient(actions=[Action.STOP])
    result = run_episode(
        config=EpisodeConfig(
            map_name="straight_corridor",
            max_steps=10,
            output_root=tmp_path,
            frame_width=160,
            frame_height=120,
            jpeg_quality=75,
            device_id="sim-edge-01",
            save_topdown=False,
            sleep_per_step_s=0.0,
            stop_on_backend_stop=True,
        ),
        control_client=client,
    )

    assert result.status is EpisodeStatus.BACKEND_STOP
    assert result.steps_executed == 1


@pytest.mark.parametrize("max_steps", [1, 3])
def test_episode_writes_summary_json(tmp_path: Path, max_steps: int) -> None:
    client = ScriptedClient(actions=[Action.STOP])
    result = run_episode(
        config=EpisodeConfig(
            map_name="straight_corridor",
            max_steps=max_steps,
            output_root=tmp_path,
            frame_width=160,
            frame_height=120,
            jpeg_quality=75,
            device_id="sim-edge-01",
            save_topdown=False,
            sleep_per_step_s=0.0,
            stop_on_backend_stop=True,
        ),
        control_client=client,
    )

    summary = json.loads(result.summary_json_path.read_text(encoding="utf-8"))
    assert summary["session_id"] == str(result.session_id)
