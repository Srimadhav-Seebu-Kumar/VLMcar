from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from backend.app.schemas import (
    Action,
    CommandResponse,
    DeviceMode,
    FrameRequest,
    SessionMetadata,
    SessionStatus,
    TelemetryPayload,
)
from backend.app.services.storage import (
    DecisionRepository,
    ErrorRepository,
    FrameRepository,
    SessionRepository,
    TelemetryRepository,
    clear_cached_db_handles,
    init_db,
    session_scope,
)


def build_database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'storage_test.db'}"


def test_session_frame_and_decision_linking(tmp_path: Path) -> None:
    database_url = build_database_url(tmp_path)
    clear_cached_db_handles()
    init_db(database_url)

    session_id = uuid4()
    with session_scope(database_url) as db:
        session_repo = SessionRepository(db)
        frame_repo = FrameRepository(db)
        decision_repo = DecisionRepository(db)

        session_repo.create(
            SessionMetadata(
                session_id=session_id,
                device_id="rc-car-01",
                prompt_version="v1",
                model_name="llava",
                operator_notes="integration-test",
                started_at_ms=1710000000000,
                ended_at_ms=None,
                status=SessionStatus.ACTIVE,
            )
        )

        frame = frame_repo.create(
            FrameRequest(
                device_id="rc-car-01",
                session_id=session_id,
                seq=10,
                timestamp_ms=1710000000050,
                frame_width=320,
                frame_height=240,
                jpeg_quality=12,
                battery_mv=7400,
                mode=DeviceMode.AUTO,
            ),
            file_path="data/frames/frame_10.jpg",
            content_type="image/jpeg",
            payload_size_bytes=2048,
        )

        decision = decision_repo.create(
            CommandResponse(
                trace_id=uuid4(),
                session_id=session_id,
                seq=10,
                action=Action.STOP,
                left_pwm=0,
                right_pwm=0,
                duration_ms=0,
                confidence=1.0,
                reason_code="SAFE_DEFAULT",
                message="stop",
                backend_latency_ms=15,
                model_latency_ms=0,
                safe_to_execute=True,
            ),
            frame_id=frame.id,
        )

        assert frame.session_id == str(session_id)
        assert decision.frame_id == frame.id
        assert decision.session_id == str(session_id)

    with session_scope(database_url) as db:
        frame_records = FrameRepository(db).list_by_session(session_id)
        decision_records = DecisionRepository(db).list_by_session(session_id)

    assert len(frame_records) == 1
    assert len(decision_records) == 1
    assert decision_records[0].frame_id == frame_records[0].id


def test_telemetry_and_error_repositories_persist_records(tmp_path: Path) -> None:
    database_url = build_database_url(tmp_path)
    clear_cached_db_handles()
    init_db(database_url)

    with session_scope(database_url) as db:
        telemetry_repo = TelemetryRepository(db)
        error_repo = ErrorRepository(db)

        telemetry = telemetry_repo.create(
            TelemetryPayload(
                device_id="rc-car-01",
                session_id=None,
                timestamp_ms=1710000001000,
                uptime_ms=9000,
                free_heap_bytes=180000,
                wifi_rssi_dbm=-52,
                battery_mv=7350,
                frame_counter=30,
                avg_loop_latency_ms=260.4,
                last_action=Action.STOP,
                last_error=None,
                mode=DeviceMode.AUTO,
            )
        )
        error = error_repo.create(
            error_code="MODEL_TIMEOUT",
            error_message="inference timed out",
            device_id="rc-car-01",
        )

        assert telemetry.id > 0
        assert error.id > 0
        assert error.error_code == "MODEL_TIMEOUT"
