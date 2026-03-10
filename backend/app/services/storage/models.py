from __future__ import annotations

import time

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.services.storage.db import Base


def now_ms() -> int:
    """Return current Unix time in milliseconds."""

    return int(time.time() * 1000)


class SessionRecord(Base):
    """Session lifecycle record."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    operator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ended_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)

    frames: Mapped[list[FrameRecord]] = relationship(back_populates="session")
    decisions: Mapped[list[DecisionRecord]] = relationship(back_populates="session")
    telemetry: Mapped[list[TelemetryRecord]] = relationship(back_populates="session")
    errors: Mapped[list[ErrorRecord]] = relationship(back_populates="session")


class FrameRecord(Base):
    """Stored frame metadata and file pointer."""

    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    frame_width: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_height: Mapped[int] = mapped_column(Integer, nullable=False)
    jpeg_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    battery_mv: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ir_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    ir_right: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)

    session: Mapped[SessionRecord | None] = relationship(back_populates="frames")
    decisions: Mapped[list[DecisionRecord]] = relationship(back_populates="frame")


class DecisionRecord(Base):
    """Final command emitted by backend control policy."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    frame_id: Mapped[int | None] = mapped_column(ForeignKey("frames.id"), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    left_pwm: Mapped[int] = mapped_column(Integer, nullable=False)
    right_pwm: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    backend_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    model_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    safe_to_execute: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)

    frame: Mapped[FrameRecord | None] = relationship(back_populates="decisions")
    session: Mapped[SessionRecord | None] = relationship(back_populates="decisions")


class TelemetryRecord(Base):
    """Device telemetry records for monitoring and debugging."""

    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uptime_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    free_heap_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    wifi_rssi_dbm: Mapped[int] = mapped_column(Integer, nullable=False)
    battery_mv: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_counter: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_loop_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    last_action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)

    session: Mapped[SessionRecord | None] = relationship(back_populates="telemetry")


class ErrorRecord(Base):
    """Captured backend/edge errors for safety and observability."""

    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)

    session: Mapped[SessionRecord | None] = relationship(back_populates="errors")
