# Architecture

## Scope
This monorepo contains a full offline control stack for a zero-shot RC car project:
- ESP32-CAM firmware captures frames and executes short motion pulses.
- Local FastAPI backend performs validation, policy, and safety gating.
- Local Ollama model provides vision-language decisions.
- Simulator and replay tooling validate behavior before hardware tests.

## Design principles
- Offline-first runtime: no cloud dependencies in control path.
- Safety-first default: on uncertainty or errors, return `STOP`.
- Contract-first integration: firmware and backend share strict schemas.
- Pulse-based actuation: each command is short-lived and self-terminates.
- Research traceability: store session, frame, inference, and decision metadata.

## High-level components

```text
+--------------------+     HTTP multipart     +------------------------+
| ESP32-CAM Firmware | ---------------------> | FastAPI Backend        |
| capture + execute  |                        | validate + decide      |
+---------+----------+                        +-----------+------------+
          ^                                                   |
          | command JSON                                      | local API
          |                                                   v
+---------+----------+                            +-----------------------+
| Motor driver (L298)|                            | Ollama local VLM      |
| pulse + auto-stop  |                            | structured JSON output |
+--------------------+                            +-----------------------+
```

Hardware-free and real-scene preflight loops use the same frame/command contract:

```text
+--------------------+     HTTP multipart     +------------------------+
| Simulator + Replay | ---------------------> | FastAPI Backend        |
| Laptop Webcam Loop |                        | validate + decide      |
+--------------------+                        +------------------------+
```

## Control loop

```text
BOOT -> WIFI_CONNECTING -> BACKEND_WAIT -> CAPTURE -> UPLOAD -> DECIDE -> EXECUTE_PULSE -> STOP -> CAPTURE
                                              |            |
                                              | failure    | parse/timeout/low confidence
                                              v            v
                                            ERROR ------- STOP
```

Backend `/api/v1/control/frame` pipeline:
1. Validate multipart metadata and JPEG content type.
2. Preprocess frame and compute quality metrics.
3. Apply quality gate (early STOP on poor frame quality).
4. Build prompt from versioned prompt files.
5. Call local Ollama adapter for inference.
6. Parse structured model JSON with schema validation.
7. Apply safety overrides and pulse shaping policy.
8. Persist frame/decision/error records with trace metadata.
9. Return bounded command response.

## Backend boundaries
- API layer: input validation and typed responses.
- Decision pipeline: preprocess, quality gate, inference, parse, policy.
- Persistence layer: session/frame/decision/error metadata in SQLite.
- Operator controls: emergency stop and mode toggles.
- Inference adapter: `OllamaNativeAdapter` wraps `/api/generate` with strict error handling.

## Firmware boundaries
- Camera module: configured JPEG capture only.
- Network module: Wi-Fi connect/reconnect and HTTP transport.
- State machine: explicit transitions with deterministic STOP fallback.
- Motor module: PWM pulse execution with overlap protection.

## Data boundaries
- `contracts/` stores canonical JSON schemas.
- `backend/app/schemas/` mirrors contract types in Pydantic.
- Simulator uses the same API contract as firmware.

## Storage implementation
- Runtime persistence uses SQLite through SQLAlchemy.
- Metadata tables: `sessions`, `frames`, `decisions`, `telemetry`, `errors`.
- Uploaded frame bytes are stored on disk; database stores frame file paths and metadata.
- Preprocess metrics (`mean_brightness`, `contrast`, `blur_score`, `quality_score`) are persisted per frame.

## Runtime safety posture
- Backend timeout returns STOP.
- Model parse failure returns STOP.
- Invalid frame returns STOP.
- Command expiry on firmware forces STOP.
- Startup default is stationary.
