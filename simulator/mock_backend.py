from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile

ScenarioName = Literal["always_stop", "always_forward", "alternating_turns", "timeout"]


@dataclass
class MockBackendConfig:
    scenario: ScenarioName
    timeout_seconds: float = 5.0


@dataclass
class ScenarioState:
    turn_counter: int = 0


def build_command(
    seq: int,
    session_id: UUID | None,
    action: str,
    left_pwm: int,
    right_pwm: int,
    duration_ms: int,
    reason_code: str,
) -> dict[str, object]:
    resolved_session = session_id or uuid4()
    return {
        "trace_id": str(uuid4()),
        "session_id": str(resolved_session),
        "seq": seq,
        "action": action,
        "left_pwm": left_pwm,
        "right_pwm": right_pwm,
        "duration_ms": duration_ms,
        "confidence": 1.0,
        "reason_code": reason_code,
        "message": f"mock scenario: {reason_code}",
        "backend_latency_ms": 1,
        "model_latency_ms": 0,
        "safe_to_execute": True,
    }


def create_mock_app(config: MockBackendConfig) -> FastAPI:
    state = ScenarioState()
    app = FastAPI(title="RC Car Mock Backend")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "scenario": config.scenario}

    @app.post("/api/v1/control/frame")
    async def control_frame(
        image: Annotated[UploadFile, File(...)],
        device_id: Annotated[str, Form(...)],
        seq: Annotated[int, Form(...)],
        timestamp_ms: Annotated[int, Form(...)],
        frame_width: Annotated[int, Form(...)],
        frame_height: Annotated[int, Form(...)],
        jpeg_quality: Annotated[int, Form(...)],
        mode: Annotated[str, Form(...)],
        session_id: Annotated[UUID | None, Form()] = None,
    ) -> dict[str, object]:
        _ = (device_id, timestamp_ms, frame_width, frame_height, jpeg_quality, mode)
        await image.read()

        if config.scenario == "timeout":
            await asyncio.sleep(config.timeout_seconds)

        if config.scenario == "always_stop":
            return build_command(seq, session_id, "STOP", 0, 0, 0, "MOCK_ALWAYS_STOP")

        if config.scenario == "always_forward":
            return build_command(seq, session_id, "FORWARD", 120, 120, 220, "MOCK_ALWAYS_FORWARD")

        if config.scenario == "alternating_turns":
            state.turn_counter += 1
            if state.turn_counter % 2 == 1:
                return build_command(seq, session_id, "LEFT", 85, 125, 200, "MOCK_TURN_LEFT")
            return build_command(seq, session_id, "RIGHT", 125, 85, 200, "MOCK_TURN_RIGHT")

        return build_command(seq, session_id, "STOP", 0, 0, 0, "MOCK_DEFAULT_STOP")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic mock backend for firmware bring-up")
    parser.add_argument(
        "--scenario",
        choices=["always_stop", "always_forward", "alternating_turns", "timeout"],
        default="always_stop",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_mock_app(
        MockBackendConfig(
            scenario=args.scenario,
            timeout_seconds=args.timeout_seconds,
        )
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
