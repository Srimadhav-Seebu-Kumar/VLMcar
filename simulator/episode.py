from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from PIL import Image

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import DeviceMode
from simulator.control_client import BackendControlError, ControlFrameRequest
from simulator.fallback import build_stop_command
from simulator.maps import get_builtin_map
from simulator.world import EgoCameraConfig, GridWorld, VehicleState


class ControlClientProtocol(Protocol):
    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse: ...


class EpisodeStatus(StrEnum):
    GOAL_REACHED = "GOAL_REACHED"
    COLLISION = "COLLISION"
    BACKEND_STOP = "BACKEND_STOP"
    BACKEND_ERROR = "BACKEND_ERROR"
    MAX_STEPS = "MAX_STEPS"


@dataclass(frozen=True)
class EpisodeConfig:
    """Runtime settings for one simulator episode."""

    map_name: str
    max_steps: int
    output_root: Path
    frame_width: int
    frame_height: int
    jpeg_quality: int
    device_id: str
    save_topdown: bool
    sleep_per_step_s: float
    stop_on_backend_stop: bool
    mode: DeviceMode = DeviceMode.AUTO


@dataclass(frozen=True)
class EpisodeResult:
    """Episode summary persisted to disk and printed by CLI."""

    status: EpisodeStatus
    session_id: UUID
    steps_executed: int
    goal_reached: bool
    collided: bool
    episode_dir: Path
    steps_jsonl_path: Path
    summary_json_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "session_id": str(self.session_id),
            "steps_executed": self.steps_executed,
            "goal_reached": self.goal_reached,
            "collided": self.collided,
            "episode_dir": str(self.episode_dir),
            "steps_jsonl_path": str(self.steps_jsonl_path),
            "summary_json_path": str(self.summary_json_path),
        }


def _is_stopped(command: CommandResponse) -> bool:
    """Check if a command is a stop (throttle=0)."""
    return command.throttle <= 0.0


def run_episode(
    *,
    config: EpisodeConfig,
    control_client: ControlClientProtocol,
    session_id: UUID | None = None,
) -> EpisodeResult:
    """Run one simulator-control loop against the backend contract."""

    world = GridWorld(get_builtin_map(config.map_name))
    camera = EgoCameraConfig(width=config.frame_width, height=config.frame_height)
    active_session_id = session_id or uuid4()

    episode_dir = config.output_root / str(active_session_id)
    frames_dir = episode_dir / "frames"
    topdown_dir = episode_dir / "topdown"
    frames_dir.mkdir(parents=True, exist_ok=True)
    if config.save_topdown:
        topdown_dir.mkdir(parents=True, exist_ok=True)

    steps_jsonl_path = episode_dir / "steps.jsonl"
    summary_json_path = episode_dir / "summary.json"

    state = world.initial_state()
    status = EpisodeStatus.MAX_STEPS
    reached_goal = False
    collided = False
    steps_executed = 0

    with steps_jsonl_path.open("w", encoding="utf-8") as log_file:
        for seq in range(1, config.max_steps + 1):
            steps_executed = seq
            timestamp_ms = int(time.time() * 1000)
            frame_image = world.render_ego_frame(state, camera)
            frame_bytes = _encode_jpeg(frame_image, quality=config.jpeg_quality)
            frame_path = frames_dir / f"frame_{seq:04d}.jpg"
            frame_path.write_bytes(frame_bytes)

            backend_error: str | None = None
            try:
                command = control_client.send_frame(
                    ControlFrameRequest(
                        image_jpeg=frame_bytes,
                        device_id=config.device_id,
                        seq=seq,
                        timestamp_ms=timestamp_ms,
                        frame_width=config.frame_width,
                        frame_height=config.frame_height,
                        jpeg_quality=config.jpeg_quality,
                        mode=config.mode,
                        session_id=active_session_id,
                    )
                )
            except BackendControlError as exc:
                backend_error = str(exc)
                command = build_stop_command(
                    seq=seq,
                    session_id=active_session_id,
                    reason_code="SIM_BACKEND_ERROR",
                    message=backend_error,
                    safe_to_execute=False,
                )

            state_before = state
            state = world.apply_command(
                state, command.heading_deg, command.throttle, command.duration_ms
            )
            reached_goal = world.is_goal_reached(state)
            collided = state.collided

            topdown_path = ""
            if config.save_topdown:
                topdown_image = world.render_topdown(state)
                topdown_path_obj = topdown_dir / f"topdown_{seq:04d}.png"
                topdown_image.save(topdown_path_obj, format="PNG")
                topdown_path = str(topdown_path_obj)

            record = _build_step_record(
                seq=seq,
                timestamp_ms=timestamp_ms,
                frame_path=frame_path,
                topdown_path=topdown_path,
                frame_width=config.frame_width,
                frame_height=config.frame_height,
                jpeg_quality=config.jpeg_quality,
                state_before=state_before,
                state_after=state,
                command=command,
                goal_reached=reached_goal,
                backend_error=backend_error,
            )
            log_file.write(json.dumps(record) + "\n")

            if backend_error is not None:
                status = EpisodeStatus.BACKEND_ERROR
                break
            if collided:
                status = EpisodeStatus.COLLISION
                break
            if reached_goal:
                status = EpisodeStatus.GOAL_REACHED
                break
            if _is_stopped(command) and config.stop_on_backend_stop:
                status = EpisodeStatus.BACKEND_STOP
                break

            if config.sleep_per_step_s > 0:
                time.sleep(config.sleep_per_step_s)

    summary = EpisodeResult(
        status=status,
        session_id=active_session_id,
        steps_executed=steps_executed,
        goal_reached=reached_goal,
        collided=collided,
        episode_dir=episode_dir,
        steps_jsonl_path=steps_jsonl_path,
        summary_json_path=summary_json_path,
    )
    summary_json_path.write_text(json.dumps(summary.as_dict(), indent=2), encoding="utf-8")
    return summary


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def _build_step_record(
    *,
    seq: int,
    timestamp_ms: int,
    frame_path: Path,
    topdown_path: str,
    frame_width: int,
    frame_height: int,
    jpeg_quality: int,
    state_before: VehicleState,
    state_after: VehicleState,
    command: CommandResponse,
    goal_reached: bool,
    backend_error: str | None,
) -> dict[str, object]:
    return {
        "seq": seq,
        "timestamp_ms": timestamp_ms,
        "frame_path": str(frame_path),
        "topdown_path": topdown_path,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "jpeg_quality": jpeg_quality,
        "state_before": state_before.as_dict(),
        "state_after": state_after.as_dict(),
        "trace_id": str(command.trace_id),
        "session_id": str(command.session_id),
        "heading_deg": command.heading_deg,
        "throttle": command.throttle,
        "left_pwm": command.left_pwm,
        "right_pwm": command.right_pwm,
        "duration_ms": command.duration_ms,
        "confidence": command.confidence,
        "reason_code": command.reason_code,
        "message": command.message,
        "backend_latency_ms": command.backend_latency_ms,
        "model_latency_ms": command.model_latency_ms,
        "safe_to_execute": command.safe_to_execute,
        "goal_reached": goal_reached,
        "collided": state_after.collided,
        "backend_error": backend_error,
    }
