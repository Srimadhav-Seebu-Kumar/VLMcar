
# Zero-Shot RC Car Software Monorepo Plan for Codex

## What this plan is for

This is a full build plan for Codex to create the entire software repository for the project:

**Zero-Shot Autonomous Driving Using Vision-Language Models for RC Car Navigation**

It assumes:
- the RC car uses an ESP32-CAM as the edge device
- the backend runs on a local PC with GPU
- the vision-language model runs locally through Ollama
- the software must work offline at runtime
- the repo should be testable even before the real car is assembled
- the repo should be research-friendly, not just demo-friendly

This plan is intentionally written as a **task-by-task execution backlog** that can be given to Codex in sequence.

---

## 1. Frozen technical decisions

These decisions should be locked before asking Codex to write code.

### 1.1 Repo strategy
Use a **single monorepo** containing:
- backend server
- firmware for ESP32-CAM
- shared API/command contracts
- simulator/replay tooling
- evaluation tools
- docs
- CI

### 1.2 Backend stack
Use:
- Python 3.11
- FastAPI
- Pydantic v2
- httpx
- Pillow
- OpenCV (headless) only where useful
- SQLAlchemy + SQLite
- pytest
- ruff
- mypy

### 1.3 Firmware stack
Use:
- C++
- PlatformIO with Arduino framework
- ESP32-CAM target
- HTTP-based communication to backend
- PWM-based motor control through L298N

### 1.4 Model stack
Use:
- Ollama running locally on the PC
- a vision-capable model, defaulting to `llava`
- a backend abstraction so the model can later be swapped to `llava-llama3`, `llama3.2-vision`, or another local vision model without changing business logic

### 1.5 Runtime interaction model
Use a **capture -> send frame -> receive action -> execute short motion pulse -> stop -> repeat** loop.

Do **not** make the car keep driving indefinitely after one inference result.  
Instead, each response should contain:
- action
- left/right speed or a high-level speed preset
- duration in milliseconds
- confidence
- reason code
- trace/session metadata

This design reduces runaway behavior when the VLM is slow.

### 1.6 Safety model
Safety rules must be part of the repo from day one:
- default to STOP on any error
- STOP on parse failure
- STOP on backend timeout
- STOP on invalid frame
- STOP on low-confidence or malformed model output
- manual emergency stop endpoint
- firmware-side watchdog timer
- command lease / pulse duration limit
- no silent failures

### 1.7 Data strategy
The runtime is zero-shot.  
However, the system should still log:
- frames
- timestamps
- preprocessing metadata
- model outputs
- chosen command
- actuation metadata
- latencies
- session IDs
- errors

This allows later analysis, replay, prompt tuning, or fine-tuning if the project grows.

---

## 2. Target monorepo layout

```text
zero-shot-rc-car/
  README.md
  LICENSE
  .gitignore
  .env.example
  Makefile
  pyproject.toml
  docker-compose.dev.yml
  .pre-commit-config.yaml

  backend/
    app/
      main.py
      api/
        deps.py
        routes/
          health.py
          sessions.py
          control.py
          telemetry.py
          manual.py
          dashboard.py
      core/
        config.py
        enums.py
        logging.py
        constants.py
      schemas/
        frame.py
        command.py
        telemetry.py
        session.py
        errors.py
      services/
        preprocess.py
        quality_gate.py
        storage/
          db.py
          models.py
          repositories.py
        inference/
          base.py
          prompt_builder.py
          parser.py
          ollama_native.py
          ollama_openai_compat.py
        decision/
          policy.py
          safety.py
          smoother.py
          state.py
        evaluation/
          replay.py
          metrics.py
          benchmark.py
        utils/
          images.py
          hashing.py
          timing.py
      templates/
        dashboard.html
      static/
        dashboard.js
        dashboard.css

    tests/
      unit/
      integration/
      e2e/
      fixtures/

  firmware/
    platformio.ini
    include/
      config.h
      pins.h
      protocol.h
      types.h
    src/
      main.cpp
      camera_capture.cpp
      wifi_client.cpp
      http_client.cpp
      motor_driver.cpp
      command_parser.cpp
      state_machine.cpp
      failsafe.cpp
      serial_console.cpp
    test/

  contracts/
    frame_request.schema.json
    command_response.schema.json
    telemetry.schema.json
    openapi_snapshot.json

  simulator/
    mock_edge_client.py
    replay_frames.py
    scenario_runner.py
    sample_frames/
    sample_videos/

  tools/
    check_env.py
    benchmark_ollama.py
    export_logs.py
    prune_logs.py
    calibrate_motors.py
    smoke_test_backend.py
    smoke_test_ollama.py

  prompts/
    system_prompt.txt
    decision_prompt_v1.txt
    decision_prompt_v2.txt
    json_schema_decision.json

  docs/
    architecture.md
    api.md
    firmware.md
    wiring.md
    deployment.md
    safety.md
    troubleshooting.md
    evaluation.md
    testing.md
    adr/
      0001-monorepo.md
      0002-frame-command-protocol.md
      0003-ollama-adapter.md
      0004-safety-first-motion-pulses.md

  notebooks/
    latency_analysis.ipynb
    replay_analysis.ipynb

  .github/
    workflows/
      ci.yml
      firmware-build.yml
```

---

## 3. End-to-end behavior that the repo must support

### 3.1 Happy path
1. ESP32-CAM boots.
2. Firmware connects to Wi-Fi.
3. Firmware initializes camera and motor driver.
4. Firmware pings backend health endpoint.
5. Firmware starts a driving session.
6. Firmware captures JPEG frame.
7. Firmware POSTs the frame plus metadata to backend.
8. Backend validates request.
9. Backend preprocesses image.
10. Backend optionally rejects poor-quality frames.
11. Backend sends frame to Ollama model with strict prompt and structured output schema.
12. Backend parses model response.
13. Backend runs safety overrides and motion smoothing.
14. Backend stores logs.
15. Backend returns a command JSON.
16. Firmware parses command.
17. Firmware actuates motors for a short pulse.
18. Firmware stops motors at pulse end.
19. Loop repeats.

### 3.2 Error path
Any of the following should result in STOP:
- Wi-Fi not available
- backend unavailable
- malformed JSON
- model timeout
- invalid frame
- confidence too low
- backend internal exception
- command older than current sequence
- manual emergency stop enabled

---

## 4. Non-functional requirements

These should be included in the repo spec and in tests.

### 4.1 Safety
- STOP must be the fallback action.
- The firmware must not continue moving if the backend stalls.
- All commands must expire automatically.

### 4.2 Latency
- Design for low frame rate but safe control.
- Optimize for latest frame, not high throughput.
- Avoid buffering many stale frames.
- Use small JPEGs (for example 320x240 or similar configurable sizes).

### 4.3 Offline operation
- No cloud inference.
- No cloud telemetry dependency.
- No external paid API required at runtime.

### 4.4 Reproducibility
- One-command local backend startup
- documented env setup
- reproducible firmware build
- repeatable simulator runs

### 4.5 Research usability
- all major decisions logged
- prompt versions versioned in repo
- replayable sessions
- benchmark scripts included

### 4.6 Extensibility
Design extension points for:
- IR distance sensors
- GPS or odometry
- alternate local VLMs
- manual joystick override
- future ROS bridge
- future fine-tuning workflow

---

## 5. Key design rules Codex must follow

Use these as the global instruction block for all Codex tasks.

## Global instruction block for Codex

```text
You are building a production-style research monorepo for a zero-shot RC car navigation project.

Core constraints:
- Runtime must be fully local/offline.
- The car uses ESP32-CAM firmware and a local Python backend.
- The backend uses a local vision-language model via Ollama.
- Default behavior on any uncertainty or error is STOP.
- The car should move in short discrete motion pulses, not indefinite continuous motion.
- The repo must be testable without hardware using simulator and replay tools.
- Add tests whenever you add behavior.
- Keep modules small, typed, and documented.
- Use configuration files and environment variables instead of hardcoded local paths.
- Do not add placeholder TODO-only stubs unless they are clearly marked and isolated.
- When building APIs, define schemas first.
- When building firmware, keep state transitions explicit.
- Prefer deterministic structured outputs from the model rather than free-form text.
- Log every inference decision with trace/session metadata.
- Do not rely on cloud APIs, browser-only hacks, or hidden manual setup.
- Keep the repo clean enough for a university final-year project demo plus future research extension.

Definition of done for each task:
- code compiles or runs
- tests exist and pass for the touched behavior
- docs are updated
- configuration examples are updated if needed
- error handling is explicit
```

---

## 6. Shared interfaces that must be defined early

These contracts should be created before deep implementation.

### 6.1 Frame request contract
Suggested request fields:

```json
{
  "device_id": "rc-car-01",
  "session_id": "optional-session-id",
  "seq": 42,
  "timestamp_ms": 1710000000000,
  "frame_width": 320,
  "frame_height": 240,
  "jpeg_quality": 12,
  "battery_mv": 7430,
  "mode": "AUTO",
  "firmware_version": "0.1.0",
  "ir_left": null,
  "ir_right": null,
  "gps": null
}
```

The frame itself should be sent as:
- multipart file upload named `image`, or
- raw bytes with metadata headers

Preferred MVP: `multipart/form-data`.

### 6.2 Command response contract
Suggested response shape:

```json
{
  "trace_id": "uuid",
  "session_id": "uuid",
  "seq": 42,
  "action": "FORWARD",
  "left_pwm": 115,
  "right_pwm": 115,
  "duration_ms": 250,
  "confidence": 0.81,
  "reason_code": "PATH_CLEAR",
  "message": "clear path",
  "backend_latency_ms": 1380,
  "model_latency_ms": 1120,
  "safe_to_execute": true
}
```

### 6.3 Allowed actions
Use a strict enum:
- FORWARD
- LEFT
- RIGHT
- STOP

### 6.4 Device mode enum
Use:
- AUTO
- MANUAL
- ESTOP
- IDLE

### 6.5 Telemetry contract
Telemetry should include:
- uptime
- free heap
- Wi-Fi RSSI
- battery voltage
- last command
- last error
- frame counter
- average loop latency

---

## 7. Prompting strategy for the VLM

The backend should not trust free-form prose.

### 7.1 Recommended model output contract
The model should produce a structured JSON object such as:

```json
{
  "action": "FORWARD",
  "confidence": 0.82,
  "reason_code": "PATH_CLEAR",
  "scene_summary": "open corridor",
  "hazards": []
}
```

### 7.2 Prompt design goals
The prompt must:
- define the car’s perspective
- define the allowed action set
- bias toward STOP when uncertain
- forbid explanations longer than needed
- ask for one navigation action for the next short motion pulse only
- avoid pretending to know depth precisely
- prefer conservative behavior in clutter or ambiguous lighting

### 7.3 Example system prompt
```text
You are the navigation policy for a small indoor RC rover.
You receive a forward-facing camera image.
Your job is to choose the safest next micro-action for the next short motion pulse.

Allowed actions: FORWARD, LEFT, RIGHT, STOP.

Rules:
- If the path ahead is clearly blocked, choose STOP.
- If the path ahead is unclear or uncertain, choose STOP.
- If the path ahead is open and centered, choose FORWARD.
- If the center is blocked but left side seems safer, choose LEFT.
- If the center is blocked but right side seems safer, choose RIGHT.
- Do not assume depth beyond what is visually plausible.
- Be conservative.
- Output only valid JSON matching the schema.
```

### 7.4 Prompt versions
Store prompts as versioned files:
- `decision_prompt_v1.txt`
- `decision_prompt_v2.txt`

Each replay/eval run must record which prompt version was used.

---

## 8. Recommended backend architecture

### 8.1 Major backend modules
- API layer
- preprocessing
- quality gate
- inference adapter
- output parser
- safety layer
- motion policy / smoothing
- persistence
- telemetry
- dashboard
- evaluation/replay

### 8.2 Important backend design choices
- Keep inference behind an interface.
- Keep prompt building isolated from API routes.
- Keep parsing and safety overrides isolated from model adapter.
- Save original frames to disk with metadata in database.
- Separate operator actions from autonomous control routes.
- Keep all configuration centralized.

### 8.3 Decision pipeline
Suggested internal pipeline:
1. validate request
2. persist raw metadata
3. decode image
4. preprocess
5. compute frame-quality metrics
6. optionally early STOP if frame quality is too poor
7. build prompt
8. run model
9. parse structured output
10. apply safety rules
11. apply motion smoothing / pulse shaping
12. persist decision
13. return command

---

## 9. Recommended firmware architecture

### 9.1 Firmware modules
- boot/init
- camera capture
- Wi-Fi connection manager
- HTTP client
- command parser
- motor driver
- state machine
- failsafe/watchdog
- serial diagnostics

### 9.2 Firmware states
Use explicit states:
- BOOTING
- WIFI_CONNECTING
- BACKEND_WAIT
- IDLE
- CAPTURE
- UPLOAD
- EXECUTE
- STOPPED
- ERROR
- ESTOP

### 9.3 Firmware loop policy
The firmware should:
- capture only when not executing a motion pulse
- never queue multiple unprocessed commands
- stop motors before taking next action unless commanded otherwise
- log errors over serial
- recover from temporary backend loss by retrying, not by continuing motion

---

## 10. Detailed Codex backlog

This section is the task-by-task plan to build the whole repository.

---

# Phase 0 - Foundations

## Task T01 - Bootstrap the monorepo

**Goal**  
Create the repo skeleton, dependency definitions, baseline tooling, and top-level README.

**Dependencies**  
None.

**Codex prompt**
```text
Initialize a monorepo for a zero-shot RC car project with these folders: backend, firmware, contracts, simulator, tools, prompts, docs, notebooks, .github/workflows. Add a top-level README, .gitignore, .env.example, pyproject.toml, Makefile, and pre-commit config. Use Python 3.11 for backend tooling. Configure ruff, mypy, and pytest. Keep the repo clean and reproducible.
```

**Deliverables**
- folder structure
- pyproject with dependencies
- Makefile commands
- pre-commit hooks
- README with repo overview

**Acceptance criteria**
- repo installs locally
- `pytest` runs even if there are few starter tests
- `ruff check` runs
- `mypy` runs
- README explains each major folder

---

## Task T02 - Write architecture and ADR documents

**Goal**  
Create design docs before implementation grows.

**Dependencies**  
T01.

**Codex prompt**
```text
Add architecture documentation for this monorepo. Create docs/architecture.md, docs/api.md, docs/firmware.md, docs/safety.md, docs/testing.md, and 4 ADRs: monorepo choice, frame-command protocol, Ollama adapter, and safety-first motion pulses. Make the docs concrete and aligned with the project goal of zero-shot RC car navigation.
```

**Deliverables**
- architecture overview
- sequence diagrams or ASCII flow diagrams
- ADRs

**Acceptance criteria**
- docs explain backend, firmware, and simulator boundaries
- docs define safety assumptions
- docs define why motion pulses are used

---

## Task T03 - Define shared schemas and contracts

**Goal**  
Create the canonical request/response formats for the whole system.

**Dependencies**  
T01, T02.

**Codex prompt**
```text
Create shared JSON schemas for frame upload requests, command responses, telemetry payloads, and session metadata. Add matching Pydantic models in backend/app/schemas. Include enums for action and device mode. Add schema validation tests and keep these contracts as the single source of truth for backend-firmware communication.
```

**Deliverables**
- `contracts/*.schema.json`
- Pydantic models
- schema tests

**Acceptance criteria**
- strict enum validation exists
- invalid command values fail validation
- schema docs are linked from docs/api.md

---

## Task T04 - Add developer tooling and environment checks

**Goal**  
Make setup reproducible and reduce local environment failure.

**Dependencies**  
T01.

**Codex prompt**
```text
Add developer tooling for this repo: a setup checker, environment validator, and Makefile commands for install, lint, typecheck, test, run-backend, smoke-backend, smoke-ollama, and firmware-build. Add a Python script tools/check_env.py that validates required Python packages, environment variables, and presence of Ollama.
```

**Deliverables**
- Makefile targets
- `tools/check_env.py`
- `.env.example`

**Acceptance criteria**
- a new developer can see all required env vars
- there is a command to verify backend preconditions
- README links setup commands

---

# Phase 1 - Backend Core

## Task T05 - Build the FastAPI application skeleton

**Goal**  
Create the backend entrypoint, app factory, config system, health endpoint, and logging.

**Dependencies**  
T01, T03.

**Codex prompt**
```text
Implement the backend FastAPI application with an app factory, centralized config using Pydantic settings, structured logging, and base routes for /health and /version. Keep code modular under backend/app. Add tests for health and config loading.
```

**Deliverables**
- `backend/app/main.py`
- config module
- logging module
- `/health`, `/version`

**Acceptance criteria**
- app starts locally
- health endpoint returns success JSON
- config can load from env
- tests cover startup and health response

---

## Task T06 - Implement session lifecycle endpoints

**Goal**  
Track driving sessions cleanly for experiments and replays.

**Dependencies**  
T05, T08 (if storage is needed early, this can be split after T08; otherwise use in-memory stub and migrate later).

**Codex prompt**
```text
Add session lifecycle support to the backend. Implement routes to create, fetch, and close sessions for a device. Include session_id, device_id, prompt_version, model_name, operator notes, and timestamps. If persistence is not ready yet, keep a clean interface so storage can be swapped from in-memory to SQLite later.
```

**Deliverables**
- session schemas
- session routes
- tests

**Acceptance criteria**
- session can be created and closed
- session IDs appear in later control responses
- tests cover invalid session handling

---

## Task T07 - Implement frame ingestion endpoint

**Goal**  
Handle image upload from the firmware.

**Dependencies**  
T03, T05.

**Codex prompt**
```text
Implement the core control endpoint that accepts a multipart JPEG image plus metadata fields matching the frame request contract. Validate device_id, seq, timestamps, and content type. Return a placeholder STOP command for now. Add tests for valid and invalid uploads.
```

**Deliverables**
- `/api/v1/control/frame`
- request parsing
- placeholder response
- tests

**Acceptance criteria**
- valid multipart upload is accepted
- invalid content type is rejected
- missing fields are rejected
- response shape matches command schema

---

## Task T08 - Implement storage layer with SQLite

**Goal**  
Persist sessions, frames, decisions, and errors.

**Dependencies**  
T01, T03, T05.

**Codex prompt**
```text
Add a SQLite-backed persistence layer using SQLAlchemy. Create models and repositories for sessions, frame metadata, decisions, command responses, telemetry, and errors. Store frame file paths and metadata in the database rather than image blobs. Add migration/bootstrap support and repository tests.
```

**Deliverables**
- DB engine/session setup
- ORM models
- repositories
- startup DB initialization
- tests

**Acceptance criteria**
- backend can start with empty database
- repositories persist and fetch records
- frame records can link to sessions
- decision records can link to frames

---

## Task T09 - Add frame storage and preprocessing

**Goal**  
Persist incoming frames and normalize them for inference.

**Dependencies**  
T07, T08.

**Codex prompt**
```text
Implement frame storage and preprocessing for uploaded images. Save original uploaded frames to disk under a structured session/device folder layout. Add preprocessing utilities for decode, resize, optional denoise, normalization helpers, and quality metrics such as brightness and blur score. Add tests for image decode and preprocessing behavior.
```

**Deliverables**
- image storage path strategy
- preprocessing module
- quality metrics
- tests

**Acceptance criteria**
- uploaded frame is saved to disk
- preprocessing returns deterministic output shape
- quality metrics are logged
- invalid images fail cleanly

---

## Task T10 - Add quality gate and early-stop logic

**Goal**  
Reject unusable frames before model inference.

**Dependencies**  
T09.

**Codex prompt**
```text
Add a quality gate module that evaluates frame usability using brightness, blur, decode validity, and size checks. If a frame is unusable, return a STOP command with a reason_code and skip model inference. Add unit tests for low-brightness, corrupted, and blurred-frame cases.
```

**Deliverables**
- quality gate service
- reason codes
- early STOP behavior
- tests

**Acceptance criteria**
- poor-quality frames do not reach inference
- STOP response includes clear reason_code
- tests cover the rejection logic

---

## Task T11 - Implement Ollama inference adapter

**Goal**  
Create the model integration boundary.

**Dependencies**  
T05, T09.

**Codex prompt**
```text
Implement a model adapter interface for local vision-language inference. Add a native Ollama client implementation and an optional OpenAI-compatible Ollama implementation behind the same interface. The adapter should accept an image path or bytes plus a prompt and return raw model output and latency metadata. Add integration tests with a mocked Ollama server.
```

**Deliverables**
- base inference interface
- Ollama native adapter
- optional OpenAI-compat adapter
- tests

**Acceptance criteria**
- backend code can switch adapters via config
- adapter returns raw text/json and latency
- failures surface explicit exceptions
- tests mock HTTP responses cleanly

---

## Task T12 - Build prompt manager and structured-output parser

**Goal**  
Make model output deterministic enough for control.

**Dependencies**  
T11, T03.

**Codex prompt**
```text
Create a prompt manager and parser for the driving model. Store versioned prompts in the prompts folder. Build requests that constrain the model to the allowed action set and JSON schema. Implement parsing that validates action, confidence, reason_code, and optional hazard fields. On parse failure, return explicit parser errors for the safety layer to convert into STOP.
```

**Deliverables**
- prompt builder
- prompt version tracking
- parser
- parser tests
- prompt files

**Acceptance criteria**
- only FORWARD/LEFT/RIGHT/STOP are accepted
- malformed model output fails predictably
- prompt version is attached to session and decision logs

---

## Task T13 - Implement decision policy, safety overrides, and pulse shaping

**Goal**  
Turn model output into safe motor commands.

**Dependencies**  
T10, T12.

**Codex prompt**
```text
Implement a decision policy layer that converts parsed model outputs into executable command responses. Add safety overrides, confidence thresholds, command shaping, and short pulse durations. Keep behavior conservative: uncertain outputs must map to STOP. Add a motion smoother that prevents rapid oscillation between LEFT and RIGHT across consecutive frames unless confidence is very high.
```

**Deliverables**
- safety policy
- confidence thresholds
- action-to-PWM mapping
- pulse duration logic
- per-session state or smoothing state
- tests

**Acceptance criteria**
- command response always has valid PWM and duration
- low confidence maps to STOP
- oscillation smoothing works
- tests cover key overrides

---

## Task T14 - Wire the full backend control pipeline

**Goal**  
Connect upload -> preprocess -> infer -> parse -> decide -> persist -> respond.

**Dependencies**  
T07 through T13.

**Codex prompt**
```text
Wire the complete backend control pipeline inside the frame control endpoint. For each request: validate, persist frame metadata, preprocess, run quality gate, call the model when appropriate, parse output, apply safety and pulse shaping, persist decision logs, and return the final command response. Add integration tests with mocked model responses and real request payloads.
```

**Deliverables**
- end-to-end backend route
- persistence hooks
- integration tests

**Acceptance criteria**
- a valid request can exercise the full pipeline
- early-stop and inference branches are both tested
- logs contain trace_id and session_id
- route returns explicit errors only when schema-level failure occurs

---

## Task T15 - Add telemetry, heartbeat, and error reporting routes

**Goal**  
Support operational visibility.

**Dependencies**  
T05, T08, T03.

**Codex prompt**
```text
Add telemetry and heartbeat support to the backend. Implement routes for device heartbeat, recent telemetry lookup, and backend error event ingestion. Persist telemetry records and expose a summarized recent-status view per device. Add tests for telemetry persistence and retrieval.
```

**Deliverables**
- telemetry endpoints
- telemetry storage
- tests

**Acceptance criteria**
- device heartbeat can be recorded
- operator can query recent device state
- telemetry links to device/session when available

---

## Task T16 - Add a minimal operator dashboard and manual override

**Goal**  
Provide demo-time and debug-time visibility plus emergency stop control.

**Dependencies**  
T14, T15.

**Codex prompt**
```text
Build a minimal operator dashboard served by FastAPI. Show recent frame thumbnails, last model action, last final command, confidence, latencies, device connectivity, and session status. Add manual STOP and mode toggle endpoints. Keep the UI simple and robust rather than flashy. Add backend tests for manual override behavior.
```

**Deliverables**
- dashboard template/static files
- manual control routes
- tests

**Acceptance criteria**
- dashboard loads with no frontend build system required
- operator can trigger STOP
- manual mode overrides autonomous decisions
- last frame and recent decisions are visible

---

# Phase 2 - Testing Without Hardware

## Task T17 - Build a simulated edge client

**Goal**  
Allow the full backend to be tested without the physical car.

**Dependencies**  
T14.

**Codex prompt**
```text
Create a simulator client that mimics the ESP32-CAM. It should load sample frames or videos, send them to the backend using the same request contract as firmware, receive command responses, log them, and optionally sleep between frames to emulate real capture cadence. Add CLI flags for device_id, session_id, prompt version, frame rate, and data source path.
```

**Deliverables**
- `simulator/mock_edge_client.py`
- sample frame loading
- CLI docs

**Acceptance criteria**
- simulator can run against local backend
- logs are saved
- command responses are displayed or stored
- it uses the exact same API contract as firmware

---

## Task T18 - Build replay and evaluation tooling

**Goal**  
Enable prompt iteration and research evaluation from saved runs.

**Dependencies**  
T08, T14, T17.

**Codex prompt**
```text
Implement replay and evaluation tools that can read stored sessions or local frame folders, rerun them through the backend decision pipeline, compare outputs across prompt versions or thresholds, and compute metrics such as action distribution, stop rate, parse-failure rate, and average latency. Add tests around metric calculations.
```

**Deliverables**
- replay CLI
- evaluation metrics module
- tests

**Acceptance criteria**
- replay can run offline on stored frames
- prompt versions can be compared
- metrics report is generated

---

## Task T19 - Add backend smoke tests and benchmark scripts

**Goal**  
Give quick confidence that the full local stack is healthy.

**Dependencies**  
T11, T14, T17.

**Codex prompt**
```text
Add smoke-test and benchmark tooling for the backend and local model. Include scripts to verify backend startup, Ollama connectivity, model response shape, and a simple latency benchmark over a small set of frames. Keep the output readable for project demos and debugging.
```

**Deliverables**
- `tools/smoke_test_backend.py`
- `tools/smoke_test_ollama.py`
- `tools/benchmark_ollama.py`

**Acceptance criteria**
- there is a one-command smoke test path
- benchmark reports avg/min/max latency
- failure messages are actionable

---

# Phase 3 - Firmware

## Task T20 - Scaffold the firmware project

**Goal**  
Create a reproducible firmware codebase under version control.

**Dependencies**  
T01, T03, T02.

**Codex prompt**
```text
Create a PlatformIO firmware project for ESP32-CAM using the Arduino framework. Add source files and headers for config, pin definitions, protocol types, state machine, motor driver, camera capture, HTTP client, and failsafe logic. Add a README in firmware/ explaining build and flash steps.
```

**Deliverables**
- `platformio.ini`
- source/header layout
- firmware README

**Acceptance criteria**
- project builds at least to a compile stage
- source layout matches module boundaries
- config values are centralized

---

## Task T21 - Implement motor driver and pulse execution module

**Goal**  
Control the car reliably with safe short-duration commands.

**Dependencies**  
T20.

**Codex prompt**
```text
Implement the motor driver module for L298N control from ESP32-CAM GPIO pins. Add helpers for STOP, FORWARD, LEFT, RIGHT, and explicit left/right PWM control. Implement pulse execution so a command runs for duration_ms and then automatically stops. Add state-safe behavior that prevents overlapping command execution.
```

**Deliverables**
- `motor_driver.cpp`
- command execution timer logic
- tests or host-side logic checks where feasible

**Acceptance criteria**
- every motion command ends in STOP automatically
- invalid PWM values are clamped
- overlapping commands are rejected or replaced safely

---

## Task T22 - Implement camera capture module

**Goal**  
Capture compressed frames from ESP32-CAM for upload.

**Dependencies**  
T20.

**Codex prompt**
```text
Implement the camera capture module for ESP32-CAM. Initialize the camera, capture JPEG frames, expose frame metadata, and support configurable frame size and JPEG quality. Add clean error handling and serial diagnostics for camera init failure and capture failure.
```

**Deliverables**
- `camera_capture.cpp`
- config-driven frame size/quality
- serial logs

**Acceptance criteria**
- camera init path is explicit
- capture returns bytes plus dimensions
- failures are logged and surfaced

---

## Task T23 - Implement Wi-Fi and HTTP client modules

**Goal**  
Connect firmware to backend.

**Dependencies**  
T20, T22, T03.

**Codex prompt**
```text
Implement Wi-Fi connection management and the HTTP client module for firmware. Add startup connection logic, reconnect behavior, backend health check, and multipart image upload to the backend control endpoint. Parse the JSON command response into firmware command structs.
```

**Deliverables**
- `wifi_client.cpp`
- `http_client.cpp`
- response parsing

**Acceptance criteria**
- firmware can reconnect after Wi-Fi loss
- firmware can POST a frame and receive JSON
- JSON parser validates required fields
- failures do not crash into undefined motor behavior

---

## Task T24 - Implement firmware state machine and control loop

**Goal**  
Make device behavior explicit and debuggable.

**Dependencies**  
T21, T22, T23.

**Codex prompt**
```text
Implement the main firmware state machine with states for booting, Wi-Fi connect, backend wait, capture, upload, execute, stopped, error, and estop. The main loop should capture a frame, upload it, parse the response, execute the motion pulse, stop, and repeat. Add serial diagnostics showing state transitions and error reasons.
```

**Deliverables**
- `state_machine.cpp`
- `main.cpp`
- serial state logs

**Acceptance criteria**
- states are explicit and readable
- the loop never drives motors without a valid command
- error state transitions are deterministic

---

## Task T25 - Add firmware failsafes and diagnostics

**Goal**  
Prevent runaway behavior when the backend or model fails.

**Dependencies**  
T24.

**Codex prompt**
```text
Add firmware failsafes: watchdog timeout, command expiry, backend timeout handling, ESTOP mode, and safe startup default. Add serial diagnostics and a simple command summary log for each executed action. Ensure any timeout or parsing failure results in STOP.
```

**Deliverables**
- failsafe module
- ESTOP handling
- timeout logic
- diagnostic logs

**Acceptance criteria**
- timeout forces STOP
- startup state is STOPPED/IDLE, never moving
- ESTOP blocks future motion until cleared
- serial logs show why STOP occurred

---

# Phase 4 - Full Integration

## Task T26 - Add a backend mock for firmware-first testing

**Goal**  
Allow firmware testing before real model integration is stable.

**Dependencies**  
T23, T24.

**Codex prompt**
```text
Create a simple backend mock mode or standalone mock server that returns deterministic command responses for testing firmware. Support scenarios such as always STOP, always FORWARD, alternating turns, and timeout simulation. Document how to use it during hardware bring-up.
```

**Deliverables**
- mock server or backend mock mode
- scenario flags
- docs

**Acceptance criteria**
- firmware can be tested without real Ollama
- timeout scenario exists
- docs describe hardware bring-up flow

---

## Task T27 - Run real end-to-end integration with backend pipeline

**Goal**  
Connect the true backend and firmware.

**Dependencies**  
T14, T25.

**Codex prompt**
```text
Complete the real end-to-end integration between firmware and backend. Ensure the firmware request matches the backend frame contract, the backend response maps to executable motor commands, and session/trace IDs are logged on both sides where feasible. Add integration tests for the backend side and update docs for full local setup.
```

**Deliverables**
- contract alignment fixes
- integration docs
- integration tests

**Acceptance criteria**
- simulator and firmware use the same contract
- backend returns commands firmware can execute directly
- all critical config values are documented

---

## Task T28 - Add optional sensor extension points (IR/GPS stubs)

**Goal**  
Keep the repo ready for future sensor fusion without forcing it into MVP.

**Dependencies**  
T03, T24.

**Codex prompt**
```text
Add optional sensor interfaces and payload fields for IR and GPS data without making them mandatory for MVP. Implement clean stubs and extension points in both backend and firmware so these sensors can be enabled later with minimal refactor. Keep default behavior camera-only.
```

**Deliverables**
- optional schema fields
- firmware stubs
- backend handling paths
- docs

**Acceptance criteria**
- camera-only mode remains the default
- optional fields do not break validation when missing
- docs clearly mark these as future-capable hooks

---

## Task T29 - Add calibration and tuning tools

**Goal**  
Make the physical car tunable without editing code everywhere.

**Dependencies**  
T21, T27.

**Codex prompt**
```text
Add calibration and tuning utilities for motor PWM, pulse duration presets, turn bias, and backend confidence thresholds. Keep tunables centralized in config and expose a small tool or script to help the operator determine good values during field tests.
```

**Deliverables**
- tuning config
- calibration script/docs
- safe defaults

**Acceptance criteria**
- motion constants are not scattered across code
- operator can adjust values through config
- docs explain how to tune in the field

---

# Phase 5 - Quality, CI, and Research Readiness

## Task T30 - Add complete test coverage across layers

**Goal**  
Move from demo code to dependable project code.

**Dependencies**  
Most earlier tasks.

**Codex prompt**
```text
Audit the repo and add missing tests across backend schemas, preprocessing, parser behavior, safety policy, API routes, simulator tooling, and any host-testable firmware logic. Focus on the highest-risk logic first: command validation, STOP fallbacks, timeout behavior, and malformed model output handling.
```

**Deliverables**
- broader unit/integration/e2e coverage
- fixture images
- mocked model responses

**Acceptance criteria**
- highest-risk logic is covered
- tests prove STOP fallback behavior
- malformed outputs and timeouts are tested

---

## Task T31 - Add CI workflows

**Goal**  
Automate quality checks.

**Dependencies**  
T01 onward.

**Codex prompt**
```text
Add GitHub Actions workflows for backend linting, type checking, tests, and firmware build verification. Keep CI practical for a student project: fast enough to use often, strict enough to catch contract and safety regressions.
```

**Deliverables**
- `.github/workflows/ci.yml`
- firmware build workflow

**Acceptance criteria**
- CI runs backend lint/type/test
- firmware compilation is checked
- failures are easy to interpret

---

## Task T32 - Complete deployment and demo documentation

**Goal**  
Make the repo usable by judges, teammates, and future maintainers.

**Dependencies**  
Broadly all implementation tasks.

**Codex prompt**
```text
Finish project documentation for local setup, Ollama setup, backend startup, firmware flash, wiring assumptions, simulator usage, dashboard usage, safety procedure, troubleshooting, and demo-day workflow. Keep docs concrete and include command examples where appropriate.
```

**Deliverables**
- polished docs
- updated README
- quickstart

**Acceptance criteria**
- a teammate can set up the project from docs
- a demo operator can find the emergency-stop instructions quickly
- local model setup is clearly documented

---

## Task T33 - Add final acceptance scripts and demo mode

**Goal**  
Create a repeatable demonstration path.

**Dependencies**  
T17, T27, T32.

**Codex prompt**
```text
Add a final acceptance checklist and demo mode tooling. Include scripts or commands for checking env, starting backend, verifying model availability, launching dashboard, and running either simulator mode or real firmware mode. Add a concise demo-day checklist in docs.
```

**Deliverables**
- acceptance checklist
- demo startup scripts or documented commands

**Acceptance criteria**
- there is a single clear path for a live demo
- simulator fallback is documented in case hardware fails
- operator checklist includes safety verification

---

## Task T34 - Add research output utilities

**Goal**  
Support analysis after experiments.

**Dependencies**  
T08, T18, T32.

**Codex prompt**
```text
Add utilities to export session logs, summarize decision statistics, and package experiment outputs for research reporting. Include CSV/JSON export options and simple summary generation for latency, action counts, stop rate, and error categories.
```

**Deliverables**
- export scripts
- summary utilities
- docs

**Acceptance criteria**
- a session can be exported cleanly
- summary statistics can be generated without notebooks
- outputs are useful for reports and presentations

---

## Task T35 - Final repo polish and consistency pass

**Goal**  
Make the repo feel coherent.

**Dependencies**  
All major tasks.

**Codex prompt**
```text
Perform a final repo polish pass. Standardize naming, tighten docs links, remove dead code, align config names, ensure tests and README match the actual implementation, and verify that backend, firmware, simulator, tools, and docs form one coherent project.
```

**Deliverables**
- consistency cleanup
- final README polish
- docs cross-linking

**Acceptance criteria**
- no obvious naming drift
- stale placeholders removed
- repo reads as one system, not disconnected modules

---

## 11. Implementation order to use in practice

If you want the safest practical order for Codex, use this sequence:

1. T01 Bootstrap monorepo  
2. T02 Architecture docs  
3. T03 Shared schemas  
4. T05 Backend skeleton  
5. T07 Frame ingestion  
6. T08 Storage layer  
7. T09 Preprocessing  
8. T10 Quality gate  
9. T11 Ollama adapter  
10. T12 Prompt/parser  
11. T13 Safety and pulse shaping  
12. T14 Full control pipeline  
13. T15 Telemetry  
14. T16 Dashboard/manual override  
15. T17 Simulator  
16. T18 Replay/eval  
17. T19 Smoke tests/benchmarks  
18. T20 Firmware scaffold  
19. T21 Motor driver  
20. T22 Camera module  
21. T23 Wi-Fi/HTTP  
22. T24 State machine  
23. T25 Failsafes  
24. T26 Mock backend  
25. T27 Real end-to-end integration  
26. T28 Optional sensor stubs  
27. T29 Calibration  
28. T30 Coverage pass  
29. T31 CI  
30. T32 Documentation  
31. T33 Demo mode  
32. T34 Research utilities  
33. T35 Final polish

---

## 12. Hidden gotchas Codex should explicitly account for

These are common failure points that should be handled as design concerns, not afterthoughts.

### 12.1 VLM latency
The model may be too slow for continuous driving.  
Therefore:
- use motion pulses
- keep speed low
- keep frame size small
- log latency every cycle
- provide a simulator to test before field use

### 12.2 Model output instability
Never trust raw text directly for motor control.  
Use:
- strict schema
- parser validation
- fallback STOP
- smoothing/hysteresis

### 12.3 Poor camera frames
Low-cost cameras can produce:
- motion blur
- bad white balance
- darkness
- compression artifacts

So the repo must include:
- frame quality checks
- preprocess module
- rejection reasons

### 12.4 Hardware/backend mismatch
If firmware and backend evolve separately, the project breaks.  
So:
- define contracts first
- keep simulator using same contract
- include integration tests

### 12.5 Logging overload
Storing every frame forever can grow fast.  
So:
- log to session folders
- add retention/pruning tool
- keep metadata in DB, images on disk

### 12.6 Safety during demos
Judges do not care if the model is clever when the car crashes into a wall.  
So:
- emergency stop
- low-speed defaults
- timeouts
- command expiry
- startup in STOP
- manual override

---

## 13. Definition of done for the whole repository

The repo is complete when all of the following are true:

### Backend
- starts with one command
- connects to local Ollama
- accepts frames
- returns validated commands
- logs sessions, frames, decisions, errors
- exposes dashboard and manual STOP

### Firmware
- builds reproducibly
- connects to Wi-Fi
- captures frames
- sends requests
- parses backend responses
- executes motion pulses
- stops on timeout or error

### Shared system
- contracts are versioned
- simulator can test the pipeline without hardware
- replay tooling can compare prompt versions
- smoke tests exist
- CI exists
- docs are complete

### Demo readiness
- operator can start backend
- operator can verify model
- operator can run simulator if hardware is unavailable
- operator can emergency stop at any time

---

## 14. Recommended first 5 Codex prompts to run

If you want to start immediately, use these first five prompts in order.

### Prompt 1
```text
Initialize the full monorepo for the zero-shot RC car project. Create the folder structure, pyproject, Makefile, pre-commit config, .env.example, backend package skeleton, firmware folder skeleton, docs folder, simulator folder, tools folder, and GitHub workflow placeholders. Add a strong top-level README that explains the architecture and repo layout.
```

### Prompt 2
```text
Define the shared communication contracts for the project. Create JSON schemas and matching Pydantic models for frame uploads, command responses, telemetry payloads, session metadata, action enums, and device mode enums. Add tests for validation failures and update docs/api.md accordingly.
```

### Prompt 3
```text
Build the FastAPI backend skeleton with app factory, config, logging, /health, /version, and a placeholder /api/v1/control/frame endpoint that accepts multipart JPEG uploads with metadata and returns a schema-valid STOP command. Add tests for health and frame upload validation.
```

### Prompt 4
```text
Add the backend persistence and image preprocessing layers. Implement SQLite storage for sessions, frame metadata, decisions, and errors. Save uploaded frames to disk, add preprocessing and frame-quality metrics, and integrate this into the frame endpoint. Add tests.
```

### Prompt 5
```text
Implement the local Ollama model adapter, prompt manager, structured-output parser, safety policy, and full control pipeline so that the frame endpoint can run preprocess -> quality gate -> infer -> parse -> safety -> respond. Default to STOP on any inference or parsing problem. Add integration tests with mocked model responses.
```

---

## 15. Recommended repo quality bar

Ask Codex to keep this quality bar throughout:
- strong typing
- explicit errors
- minimal global state
- deterministic tests
- config-driven constants
- no magic numbers scattered around
- no cloud-only assumptions
- no silent pass/fail logic
- docs kept current with implementation

---

## 16. One-line summary

Build this as a **safety-first, offline-first, research-grade monorepo** where the ESP32-CAM is a thin edge client, the Python backend owns the intelligence, the local VLM output is forced into a strict contract, and every motion command is a short pulse that automatically stops.
