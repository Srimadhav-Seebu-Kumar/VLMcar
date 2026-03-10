# API Design

## Base conventions
- Base path: `/api/v1`
- Content type for frame ingress: `multipart/form-data`
- Response format: JSON matching command contract
- Safety fallback: backend returns `STOP` on validation/inference errors

## Core endpoints
- `GET /health`: liveness probe.
- `GET /version`: service version and model config.
- `POST /api/v1/control/frame`: image + frame metadata -> command response.
- `POST /api/v1/sessions`: create a driving session.
- `GET /api/v1/sessions/{session_id}`: read session info.
- `POST /api/v1/sessions/{session_id}/close`: close a session.
- `POST /api/v1/manual/estop`: trigger emergency stop.

## Frame control request
Multipart fields:
- `image`: JPEG file bytes.
- `device_id`: string.
- `session_id`: optional UUID.
- `seq`: monotonic integer.
- `timestamp_ms`: Unix epoch milliseconds.
- `frame_width`: integer.
- `frame_height`: integer.
- `jpeg_quality`: integer.
- `battery_mv`: optional integer.
- `mode`: enum (`AUTO`, `MANUAL`, `ESTOP`, `IDLE`).

## Command response
- `trace_id`: UUID for end-to-end trace.
- `session_id`: session UUID.
- `seq`: frame sequence number.
- `action`: enum (`FORWARD`, `LEFT`, `RIGHT`, `STOP`).
- `left_pwm`, `right_pwm`: 0-255.
- `duration_ms`: bounded pulse duration.
- `confidence`: 0.0-1.0.
- `reason_code`: machine-friendly reason.
- `backend_latency_ms`, `model_latency_ms`: timing metadata.
- `safe_to_execute`: boolean.

## Canonical contracts
JSON schemas in `contracts/` are the source of truth:
- [frame_request.schema.json](../contracts/frame_request.schema.json)
- [command_response.schema.json](../contracts/command_response.schema.json)
- [telemetry.schema.json](../contracts/telemetry.schema.json)
- [session.schema.json](../contracts/session.schema.json)

Pydantic mirrors are in `backend/app/schemas/`. Any contract update must change both and add/update validation tests.
