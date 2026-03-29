from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import DeviceMode
from simulator.control_client import BackendControlError, ControlFrameRequest
from simulator.fallback import build_stop_command


class ControlClientProtocol(Protocol):
    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse: ...


@dataclass(frozen=True)
class ReplayConfig:
    """Configuration for replaying stored simulator frames against backend."""

    steps_jsonl_path: Path
    output_jsonl_path: Path
    device_id: str
    jpeg_quality: int
    stop_on_backend_stop: bool
    mode: DeviceMode = DeviceMode.AUTO


@dataclass(frozen=True)
class ReplayResult:
    """Summary of replay run quality."""

    total_steps: int
    matched_actions: int
    backend_errors: int
    output_jsonl_path: Path

    def as_dict(self) -> dict[str, object]:
        match_rate = 0.0 if self.total_steps == 0 else self.matched_actions / self.total_steps
        return {
            "total_steps": self.total_steps,
            "matched_actions": self.matched_actions,
            "match_rate": round(match_rate, 4),
            "backend_errors": self.backend_errors,
            "output_jsonl_path": str(self.output_jsonl_path),
        }


def replay_episode(
    *,
    config: ReplayConfig,
    control_client: ControlClientProtocol,
) -> ReplayResult:
    """Replay stored simulator frames through backend and compare actions."""

    steps = _load_steps(config.steps_jsonl_path)
    config.output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    matched = 0
    backend_errors = 0
    written = 0
    with config.output_jsonl_path.open("w", encoding="utf-8") as output_file:
        for step in steps:
            written += 1
            # Compare heading_deg (new format) or fall back to action (old format)
            expected_heading = step.get("heading_deg", 0)
            expected_throttle = step.get("throttle", 0.0)
            seq = _read_int(step.get("seq"), default=written)
            session_id = UUID(str(step["session_id"]))
            frame_path = Path(str(step["frame_path"]))
            frame_bytes = frame_path.read_bytes()
            frame_width, frame_height = _read_frame_dimensions(step)
            jpeg_quality = _read_int(step.get("jpeg_quality"), default=config.jpeg_quality)
            timestamp_ms = _read_int(step.get("timestamp_ms"), default=0)

            backend_error: str | None = None
            try:
                command = control_client.send_frame(
                    ControlFrameRequest(
                        image_jpeg=frame_bytes,
                        device_id=config.device_id,
                        seq=seq,
                        timestamp_ms=timestamp_ms,
                        frame_width=frame_width,
                        frame_height=frame_height,
                        jpeg_quality=jpeg_quality,
                        mode=config.mode,
                        session_id=session_id,
                    )
                )
            except BackendControlError as exc:
                backend_errors += 1
                backend_error = str(exc)
                command = build_stop_command(
                    seq=seq,
                    session_id=session_id,
                    reason_code="REPLAY_BACKEND_ERROR",
                    message=backend_error,
                    safe_to_execute=False,
                )

            # Match on heading direction and throttle state
            heading_match = command.heading_deg == expected_heading
            throttle_match = (command.throttle > 0) == (expected_throttle > 0)
            action_match = heading_match and throttle_match
            if action_match:
                matched += 1

            output_record = {
                "seq": seq,
                "expected_heading_deg": expected_heading,
                "expected_throttle": expected_throttle,
                "actual_heading_deg": command.heading_deg,
                "actual_throttle": command.throttle,
                "action_match": action_match,
                "trace_id": str(command.trace_id),
                "session_id": str(command.session_id),
                "reason_code": command.reason_code,
                "backend_error": backend_error,
            }
            output_file.write(json.dumps(output_record) + "\n")

            if command.throttle <= 0.0 and config.stop_on_backend_stop:
                break

    return ReplayResult(
        total_steps=written,
        matched_actions=matched,
        backend_errors=backend_errors,
        output_jsonl_path=config.output_jsonl_path,
    )


def _load_steps(path: Path) -> list[dict[str, object]]:
    steps: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            raw = json.loads(stripped)
            if not isinstance(raw, dict):
                raise ValueError(f"invalid step record in {path}")
            steps.append(raw)
    return steps


def _read_frame_dimensions(step: dict[str, object]) -> tuple[int, int]:
    width = _read_int(step.get("frame_width"), default=320)
    height = _read_int(step.get("frame_height"), default=240)
    return (width, height)


def _read_int(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
