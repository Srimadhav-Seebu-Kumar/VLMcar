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

## Control loop

```text
BOOT -> WIFI_CONNECTING -> BACKEND_WAIT -> CAPTURE -> UPLOAD -> DECIDE -> EXECUTE_PULSE -> STOP -> CAPTURE
                                              |            |
                                              | failure    | parse/timeout/low confidence
                                              v            v
                                            ERROR ------- STOP
```

## Backend boundaries
- API layer: input validation and typed responses.
- Decision pipeline: preprocess, quality gate, inference, parse, policy.
- Persistence layer: session/frame/decision/error metadata in SQLite.
- Operator controls: emergency stop and mode toggles.

## Firmware boundaries
- Camera module: configured JPEG capture only.
- Network module: Wi-Fi connect/reconnect and HTTP transport.
- State machine: explicit transitions with deterministic STOP fallback.
- Motor module: PWM pulse execution with overlap protection.

## Data boundaries
- `contracts/` stores canonical JSON schemas.
- `backend/app/schemas/` mirrors contract types in Pydantic.
- Simulator uses the same API contract as firmware.

## Runtime safety posture
- Backend timeout returns STOP.
- Model parse failure returns STOP.
- Invalid frame returns STOP.
- Command expiry on firmware forces STOP.
- Startup default is stationary.
