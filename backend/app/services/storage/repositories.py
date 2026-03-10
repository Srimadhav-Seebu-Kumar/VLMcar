from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.frame import FrameRequest
from backend.app.schemas.session import SessionMetadata
from backend.app.schemas.telemetry import TelemetryPayload
from backend.app.services.preprocess import FrameQualityMetrics
from backend.app.services.storage.models import (
    DecisionRecord,
    ErrorRecord,
    FrameRecord,
    SessionRecord,
    TelemetryRecord,
)


class SessionRepository:
    """Persistence operations for session lifecycle records."""

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def create(self, metadata: SessionMetadata) -> SessionRecord:
        record = SessionRecord(
            id=str(metadata.session_id),
            device_id=metadata.device_id,
            prompt_version=metadata.prompt_version,
            model_name=metadata.model_name,
            operator_notes=metadata.operator_notes,
            started_at_ms=metadata.started_at_ms,
            ended_at_ms=metadata.ended_at_ms,
            status=metadata.status.value,
        )
        self._db.add(record)
        self._db.flush()
        return record

    def get(self, session_id: UUID | str) -> SessionRecord | None:
        return self._db.get(SessionRecord, str(session_id))

    def close(self, session_id: UUID | str, ended_at_ms: int) -> SessionRecord | None:
        record = self.get(session_id)
        if record is None:
            return None
        record.status = "CLOSED"
        record.ended_at_ms = ended_at_ms
        self._db.flush()
        return record


class FrameRepository:
    """Persistence operations for frame metadata records."""

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def create(
        self,
        metadata: FrameRequest,
        file_path: str,
        content_type: str,
        payload_size_bytes: int,
        quality_metrics: FrameQualityMetrics | None = None,
    ) -> FrameRecord:
        record = FrameRecord(
            session_id=str(metadata.session_id) if metadata.session_id else None,
            device_id=metadata.device_id,
            seq=metadata.seq,
            timestamp_ms=metadata.timestamp_ms,
            frame_width=metadata.frame_width,
            frame_height=metadata.frame_height,
            jpeg_quality=metadata.jpeg_quality,
            battery_mv=metadata.battery_mv,
            mode=metadata.mode.value,
            firmware_version=metadata.firmware_version,
            ir_left=metadata.ir_left,
            ir_right=metadata.ir_right,
            gps_lat=metadata.gps.lat if metadata.gps else None,
            gps_lon=metadata.gps.lon if metadata.gps else None,
            content_type=content_type,
            payload_size_bytes=payload_size_bytes,
            file_path=file_path,
            mean_brightness=quality_metrics.mean_brightness if quality_metrics else None,
            contrast=quality_metrics.contrast if quality_metrics else None,
            blur_score=quality_metrics.blur_score if quality_metrics else None,
            quality_score=quality_metrics.quality_score if quality_metrics else None,
        )
        self._db.add(record)
        self._db.flush()
        return record

    def get(self, frame_id: int) -> FrameRecord | None:
        return self._db.get(FrameRecord, frame_id)

    def list_by_session(self, session_id: UUID | str) -> list[FrameRecord]:
        statement = select(FrameRecord).where(FrameRecord.session_id == str(session_id))
        return list(self._db.scalars(statement))


class DecisionRepository:
    """Persistence operations for backend action decisions."""

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def create(self, command: CommandResponse, frame_id: int | None) -> DecisionRecord:
        record = DecisionRecord(
            frame_id=frame_id,
            session_id=str(command.session_id),
            trace_id=str(command.trace_id),
            seq=command.seq,
            action=command.action.value,
            left_pwm=command.left_pwm,
            right_pwm=command.right_pwm,
            duration_ms=command.duration_ms,
            confidence=command.confidence,
            reason_code=command.reason_code,
            message=command.message,
            backend_latency_ms=command.backend_latency_ms,
            model_latency_ms=command.model_latency_ms,
            safe_to_execute=command.safe_to_execute,
        )
        self._db.add(record)
        self._db.flush()
        return record

    def list_by_session(self, session_id: UUID | str) -> list[DecisionRecord]:
        statement = select(DecisionRecord).where(DecisionRecord.session_id == str(session_id))
        return list(self._db.scalars(statement))


class TelemetryRepository:
    """Persistence operations for telemetry events."""

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def create(self, payload: TelemetryPayload) -> TelemetryRecord:
        record = TelemetryRecord(
            session_id=str(payload.session_id) if payload.session_id else None,
            device_id=payload.device_id,
            timestamp_ms=payload.timestamp_ms,
            uptime_ms=payload.uptime_ms,
            free_heap_bytes=payload.free_heap_bytes,
            wifi_rssi_dbm=payload.wifi_rssi_dbm,
            battery_mv=payload.battery_mv,
            frame_counter=payload.frame_counter,
            avg_loop_latency_ms=payload.avg_loop_latency_ms,
            last_action=payload.last_action.value if payload.last_action else None,
            last_error=payload.last_error,
            mode=payload.mode.value,
        )
        self._db.add(record)
        self._db.flush()
        return record


class ErrorRepository:
    """Persistence operations for backend and edge error records."""

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def create(
        self,
        error_code: str,
        error_message: str,
        session_id: UUID | None = None,
        device_id: str | None = None,
        trace_id: UUID | None = None,
    ) -> ErrorRecord:
        record = ErrorRecord(
            session_id=str(session_id) if session_id else None,
            device_id=device_id,
            trace_id=str(trace_id) if trace_id else None,
            error_code=error_code,
            error_message=error_message,
        )
        self._db.add(record)
        self._db.flush()
        return record
