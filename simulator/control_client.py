from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

import httpx
from pydantic import ValidationError

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import DeviceMode


@dataclass(frozen=True)
class ControlFrameRequest:
    """Frame and metadata payload sent to backend `/api/v1/control/frame`."""

    image_jpeg: bytes
    device_id: str
    seq: int
    timestamp_ms: int
    frame_width: int
    frame_height: int
    jpeg_quality: int
    mode: DeviceMode = DeviceMode.AUTO
    session_id: UUID | None = None
    battery_mv: int | None = None


class BackendControlError(RuntimeError):
    """Raised when backend frame upload/parse fails."""


class BackendControlClient:
    """HTTP client wrapper for deterministic backend control requests."""

    def __init__(
        self,
        *,
        frame_url: str,
        timeout_s: float = 10.0,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=timeout_s, headers=headers)
        self._frame_url = frame_url
        # Derive ack URL from frame URL
        self._ack_url = frame_url.rsplit("/frame", 1)[0] + "/ack"

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> BackendControlClient:
        return self

    def __exit__(self, exc_type: object, exc: object, exc_tb: object) -> None:
        _ = (exc_type, exc, exc_tb)
        self.close()

    def send_ack(self, device_id: str, session_id: UUID, seq: int) -> bool:
        """Send readiness acknowledgment. Returns True if backend requests a frame."""

        payload = {
            "device_id": device_id,
            "session_id": str(session_id),
            "seq": seq,
            "status": "READY",
        }
        try:
            response = self._http_client.post(self._ack_url, json=payload)
        except httpx.HTTPError as exc:
            raise BackendControlError(f"ack request failed: {exc}") from exc

        if response.status_code != 200:
            raise BackendControlError(f"ack status={response.status_code}")

        body = response.json()
        return bool(body.get("request_frame", True))

    def send_frame(self, frame: ControlFrameRequest) -> CommandResponse:
        data: dict[str, str] = {
            "device_id": frame.device_id,
            "seq": str(frame.seq),
            "timestamp_ms": str(frame.timestamp_ms),
            "frame_width": str(frame.frame_width),
            "frame_height": str(frame.frame_height),
            "jpeg_quality": str(frame.jpeg_quality),
            "mode": frame.mode.value,
        }
        if frame.session_id is not None:
            data["session_id"] = str(frame.session_id)
        if frame.battery_mv is not None:
            data["battery_mv"] = str(frame.battery_mv)

        files = {"image": ("frame.jpg", frame.image_jpeg, "image/jpeg")}

        try:
            response = self._http_client.post(self._frame_url, data=data, files=files)
        except httpx.HTTPError as exc:
            raise BackendControlError(f"request failed: {exc}") from exc

        if response.status_code != 200:
            detail = response.text.strip()
            raise BackendControlError(f"backend status={response.status_code} detail={detail}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise BackendControlError("backend returned non-JSON response") from exc

        try:
            return CommandResponse.model_validate(payload)
        except ValidationError as exc:
            raise BackendControlError(f"invalid command response payload: {exc}") from exc
