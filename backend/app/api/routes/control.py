from __future__ import annotations

import logging
import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from backend.app.api.deps import get_app_settings
from backend.app.core.config import AppSettings
from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import Action, DeviceMode
from backend.app.schemas.frame import FrameRequest, GpsData
from backend.app.services.preprocess import preprocess_frame
from backend.app.services.storage import FrameFileStore, FrameRepository, session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/control", tags=["control"])


@router.post("/frame", response_model=CommandResponse)
async def ingest_frame(
    settings: Annotated[AppSettings, Depends(get_app_settings)],
    image: UploadFile = File(...),
    device_id: str = Form(...),
    session_id: UUID | None = Form(default=None),
    seq: int = Form(...),
    timestamp_ms: int = Form(...),
    frame_width: int = Form(...),
    frame_height: int = Form(...),
    jpeg_quality: int = Form(...),
    battery_mv: int | None = Form(default=None),
    mode: DeviceMode = Form(...),
    firmware_version: str | None = Form(default=None),
    ir_left: float | None = Form(default=None),
    ir_right: float | None = Form(default=None),
    gps_lat: float | None = Form(default=None),
    gps_lon: float | None = Form(default=None),
) -> CommandResponse:
    """Accept a multipart frame upload and return conservative placeholder STOP."""

    started = time.perf_counter()

    if image.content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=415, detail="image must be image/jpeg")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=422, detail="image payload cannot be empty")

    if (gps_lat is None) != (gps_lon is None):
        raise HTTPException(status_code=422, detail="gps_lat and gps_lon must be provided together")

    gps = GpsData(lat=gps_lat, lon=gps_lon) if gps_lat is not None and gps_lon is not None else None

    try:
        metadata = FrameRequest(
            device_id=device_id,
            session_id=session_id,
            seq=seq,
            timestamp_ms=timestamp_ms,
            frame_width=frame_width,
            frame_height=frame_height,
            jpeg_quality=jpeg_quality,
            battery_mv=battery_mv,
            mode=mode,
            firmware_version=firmware_version,
            ir_left=ir_left,
            ir_right=ir_right,
            gps=gps,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    trace_id = uuid4()
    resolved_session_id = metadata.session_id or uuid4()
    metadata_with_session = metadata.model_copy(update={"session_id": resolved_session_id})

    preprocess_result = preprocess_frame(payload)
    frame_store = FrameFileStore(settings.artifacts_dir)
    stored_frame = frame_store.save_frame(
        session_id=resolved_session_id,
        seq=metadata_with_session.seq,
        timestamp_ms=metadata_with_session.timestamp_ms,
        payload=payload,
    )

    with session_scope(settings.database_url) as db:
        frame_record = FrameRepository(db).create(
            metadata=metadata_with_session,
            file_path=str(stored_frame.file_path),
            content_type=image.content_type,
            payload_size_bytes=stored_frame.payload_size_bytes,
            quality_metrics=preprocess_result.metrics,
        )

    backend_latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "frame_ingested_placeholder_stop",
        extra={
            "trace_id": str(trace_id),
            "session_id": str(resolved_session_id),
            "device_id": metadata.device_id,
            "route": "/api/v1/control/frame",
            "frame_id": frame_record.id,
        },
    )

    return CommandResponse(
        trace_id=trace_id,
        session_id=resolved_session_id,
        seq=metadata.seq,
        action=Action.STOP,
        left_pwm=0,
        right_pwm=0,
        duration_ms=0,
        confidence=1.0,
        reason_code="PLACEHOLDER_STOP",
        message="Frame accepted; placeholder stop response.",
        backend_latency_ms=backend_latency_ms,
        model_latency_ms=0,
        safe_to_execute=True,
    )
