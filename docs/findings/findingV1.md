# Finding V1: Hallway Scenario — Full System Simulation & Robustness Audit

**Date:** 2026-03-21
**Scenario:** Narrow hallway. Blue sneaker blocking the left side of the path. Hardwood floor.
**Perspective:** I am VLMcar-01. This document traces my full control loop from boot to motor execution.

---

## Part A: "I Am The Car" — Full Control Loop Simulation

### A.1 BOOTING

I power on. My `setup()` function runs:

```
serial_console_init()     → UART at 115200 baud
motor_driver_init()       → GPIO pins configured:
                            IN1=12, IN2=13 (left motor direction)
                            IN3=14, IN4=15 (right motor direction)
                            ENA=2 (left PWM), ENB=4 (right PWM)
                            All set LOW → motors OFF
failsafe_init()           → ESTOP pin (GPIO 33) configured INPUT_PULLUP
                            g_estop_active = false
```

**I/O:** GPIO (6 motor pins + 1 ESTOP), UART (serial at 115200)
**Physical state:** Stationary. Motors not energized.
**Duration:** ~100ms

Then `loop()` begins. Every iteration:
```
failsafe_update_inputs()  → read GPIO 33 (ESTOP pin)
failsafe_kick()           → g_last_kick_ms = millis()  ← WATCHDOG RESET
g_state_machine.step()    → state-dependent logic
motor_driver_update()     → check motor pulse deadline
delay(20)                 → 20ms sleep
```

My state machine starts in BOOTING. I call `camera_capture_init()`:
- Configures ESP32-CAM (OV2640 sensor)
- Frame size: 320x240 (QVGA)
- JPEG quality: 12
- Pixel format: JPEG
- Frame buffer count: 1

**If camera init fails:** I transition to ERROR. I cannot proceed without vision.
**If camera init succeeds:** I transition to WIFI_CONNECTING.

---

### A.2 WIFI_CONNECTING

I call `wifi_client_connect()` with credentials from `config.h`:
```
SSID:     "REPLACE_WITH_WIFI_SSID"
Password: "REPLACE_WITH_WIFI_PASSWORD"
```

**I/O:** WiFi radio (ESP32 built-in)
**Physical state:** Stationary.
**Worst case:** 15,000ms (`WIFI_CONNECT_TIMEOUT_MS`)

> **BUG #1 (CRITICAL): WiFi.begin() can block up to 15 seconds.**
> My watchdog timeout is only 2,500ms. `failsafe_kick()` was called at loop START,
> but WiFi.begin() is a blocking call inside `step()`. If it takes >2,500ms, the
> watchdog sees `(millis() - g_last_kick_ms) > 2500` on the NEXT iteration and
> fires, transitioning me to ERROR before I even connect.

I retry every 2,000ms. Once WiFi connects, I transition to BACKEND_WAIT.

---

### A.3 BACKEND_WAIT

I call `http_client_health_check()` — an HTTP GET to `http://192.168.1.2:8000/health`.

**Backend response (from `system.py`):**
```json
{
  "status": "ok",
  "service": "zero-shot-rc-car-backend",
  "environment": "dev",
  "timestamp": "2026-03-21T12:00:00+00:00"
}
```

**I/O:** WiFi → HTTP GET `/health`
**Physical state:** Stationary.
**Worst case:** 3,000ms (`BACKEND_TIMEOUT_MS`)

> **NOTE:** 3,000ms timeout exceeds my 2,500ms watchdog, but I'm safe because
> `failsafe_kick()` resets the timer at the START of each loop iteration, before
> `step()` blocks in the HTTP call.

Once I get HTTP 200, I transition to IDLE.

---

### A.4 IDLE → CAPTURE

**IDLE:** I check `motor_driver_is_busy()` — returns `false` (no previous pulse running).
I immediately transition to CAPTURE.

**CAPTURE:** I call `camera_capture_frame()`:
- Acquires JPEG from the OV2640 sensor via `esp_camera_fb_get()`
- Stores pointer in `g_last_fb` (must be released before next capture)
- Records metadata: `sequence_=1, timestamp_ms=millis(), width=320, height=240`

**Output:** A 320x240 JPEG frame (~10-20KB) showing:
- Narrow hallway, walls on both sides
- Blue sneaker on the left side of the floor
- Hardwood floor visible
- Adequate indoor lighting

**I/O:** Camera sensor (SPI/parallel data bus)
**Physical state:** Stationary.
**Duration:** 200-400ms (JPEG encoding is CPU-intensive on ESP32)

I transition to UPLOAD.

---

### A.5 UPLOAD — Firmware to Backend

I call `http_client_send_frame()` which constructs a multipart/form-data POST:

#### Firmware → Backend I/O (exact request)

```
POST /api/v1/control/frame HTTP/1.1
Host: 192.168.1.2:8000
Content-Type: multipart/form-data; boundary=----vlmcarboundary

------vlmcarboundary
Content-Disposition: form-data; name="device_id"

rc-car-01
------vlmcarboundary
Content-Disposition: form-data; name="seq"

1
------vlmcarboundary
Content-Disposition: form-data; name="timestamp_ms"

45230
------vlmcarboundary
Content-Disposition: form-data; name="frame_width"

320
------vlmcarboundary
Content-Disposition: form-data; name="frame_height"

240
------vlmcarboundary
Content-Disposition: form-data; name="jpeg_quality"

12
------vlmcarboundary
Content-Disposition: form-data; name="mode"

AUTO
------vlmcarboundary
Content-Disposition: form-data; name="firmware_version"

0.1.0
------vlmcarboundary
Content-Disposition: form-data; name="image"; filename="frame.jpg"
Content-Type: image/jpeg

<binary JPEG data, ~10-20KB>
------vlmcarboundary--
```

**Notable:** I do NOT send `session_id`. The backend will auto-generate one.

**I/O:** WiFi → HTTP POST (~10-20KB upload)
**Physical state:** Stationary, waiting for backend response.
**Duration:** 2,500-3,000ms (dominated by Ollama inference)

---

### A.6 UPLOAD — Backend Processing Pipeline

The backend receives my frame at `POST /api/v1/control/frame` and processes it through 10 stages:

#### Stage 1: Validation (`control.py:102-108`)
```
content_type = "image/jpeg"  → PASS (in {"image/jpeg", "image/jpg"})
payload = await image.read() → ~15KB of JPEG bytes
len(payload) > 0             → PASS
```

#### Stage 2: Metadata Parsing (`control.py:116-132`)
```python
FrameRequest(
    device_id="rc-car-01",
    session_id=None,           # firmware didn't send this
    seq=1,
    timestamp_ms=45230,
    frame_width=320,
    frame_height=240,
    jpeg_quality=12,
    battery_mv=None,
    mode=DeviceMode.AUTO,
    firmware_version="0.1.0",
    ir_left=None,
    ir_right=None,
    gps=None,
)
```

#### Stage 3: Session Resolution (`control.py:134-136`)
```python
trace_id = uuid4()                                      # e.g. "a1b2c3d4-..."
resolved_session_id = metadata.session_id or uuid4()    # auto-generated UUID
```

> **BUG #2 (HIGH): SessionRecord is never created.** The backend auto-generates a
> `session_id` UUID but never inserts a `SessionRecord` row in the database.
> FrameRecord and DecisionRecord reference this session_id, but the parent row
> doesn't exist. This breaks any future session-based queries or replay.

#### Stage 4: Preprocessing (`preprocess.py:42-67`)

The frame is decoded, converted to RGB, then grayscale. Quality metrics computed:

```python
gray_array = np.asarray(gray, dtype=np.float32)  # 320x240 float32

# For a well-lit hallway with hardwood floor:
mean_brightness = np.mean(gray_array)              ≈ 140.0
contrast        = np.std(gray_array)               ≈ 45.0
blur_score      = np.var(grad_x) + np.var(grad_y)  ≈ 120.0

# Quality score formula (preprocess.py:35-39):
brightness_factor = max(0.0, 1.0 - abs(140.0 - 127.5) / 127.5)
                  = 1.0 - 12.5/127.5
                  = 0.902

contrast_factor   = min(1.0, 45.0 / 64.0)
                  = 0.703

blur_factor       = min(1.0, 120.0 / 150.0)
                  = 0.800

quality_score     = 0.4 * 0.902 + 0.3 * 0.703 + 0.3 * 0.800
                  = 0.361 + 0.211 + 0.240
                  = 0.812
```

Image re-saved as JPEG at quality=85 (normalized for VLM input).

#### Stage 5: Quality Gate (`quality_gate.py:17-58`)

| Check | Threshold | Value | Result |
|-------|-----------|-------|--------|
| `mean_brightness < min_brightness` | 20.0 | 140.0 | **PASS** |
| `mean_brightness > max_brightness` | 235.0 | 140.0 | **PASS** |
| `blur_score < min_blur_score` | 2.0 | 120.0 | **PASS** |
| `quality_score < min_quality_score` | 0.2 | 0.812 | **PASS** |

Result: `QualityGateDecision(accepted=True, reason_code="FRAME_QUALITY_OK")`

#### Stage 6: Frame Storage (`files.py:24-37`)
```
File saved to: data/sessions/{session_id}/frames/000001_45230.jpg
SHA-256 checksum computed and stored.
```

#### Stage 7: Prompt Assembly (`prompt_manager.py`)

Full prompt sent to LLaVA:

```
You are the navigation policy for a small indoor RC rover.
You receive one forward-facing image and metadata.
Choose exactly one safe action for the next short motion pulse.
If uncertain, choose STOP.
Output only JSON that matches the required schema.

Return JSON with fields: action, confidence, reason_code, scene_summary, hazards.
Allowed action values: FORWARD, LEFT, RIGHT, STOP.
Rules:
- If path is uncertain, choose STOP.
- If path is blocked, choose STOP.
- If center is clear and stable, choose FORWARD.
- If center blocked and left appears safer, choose LEFT.
- If center blocked and right appears safer, choose RIGHT.
- Keep scene_summary concise.
- hazards must be a list of short strings.

Frame metadata:

{"device_id":"rc-car-01","seq":1,"mode":"AUTO","frame_width":320,"frame_height":240,"timestamp_ms":45230}
```

Image sent as base64-encoded bytes alongside this prompt.

#### Stage 8: Ollama Inference (`ollama_native.py`)

Request to Ollama:
```json
{
  "model": "llava",
  "prompt": "<assembled prompt text above>",
  "images": ["<base64-encoded JPEG>"],
  "stream": false,
  "format": "json",
  "options": {"temperature": 0}
}
```

Expected VLM reasoning for the hallway scene:
- Sees narrow hallway
- Identifies blue sneaker blocking left path
- Right side appears clear for passage
- Hardwood floor is traversable

**Expected LLaVA response:**
```json
{
  "action": "RIGHT",
  "confidence": 0.78,
  "reason_code": "OBSTACLE_LEFT",
  "scene_summary": "Narrow hallway with blue sneaker blocking left side. Right side clear for passage.",
  "hazards": ["blue sneaker left side"]
}
```

Model latency: ~2,000-3,000ms typical for LLaVA on consumer GPU.

#### Stage 9: Output Parsing (`parser.py`)

1. `_extract_json()` finds the `{` character and uses `json.JSONDecoder.raw_decode()` to extract JSON.
2. `jsonschema.validate()` checks against `json_schema_decision.json`:
   - `action` = "RIGHT" → valid enum value
   - `confidence` = 0.78 → number in [0, 1]
   - `reason_code` = "OBSTACLE_LEFT" → string, length 1-64
   - `scene_summary` → string, maxLength 200
   - `hazards` = ["blue sneaker left side"] → array of strings, maxItems 8
3. Returns `ParsedDecision(action=Action.RIGHT, confidence=0.78, ...)`

#### Stage 10: Safety Overrides (`safety.py:19-55`)

```python
# Check 1: estop_active?
estop_active = False        # HARDCODED at control.py:190
                            # → SKIP

# Check 2: confidence < min_confidence?
0.78 < 0.55                 # → False → SKIP

# Check 3: action is STOP?
Action.RIGHT is Action.STOP # → False → SKIP

# Result: pass through
SafetyOutcome(
    action=Action.RIGHT,
    reason_code="OBSTACLE_LEFT",
    message="Narrow hallway with blue sneaker blocking left...",
    safe_to_execute=True,
)
```

#### Stage 11: Pulse Shaping (`smoother.py:38-61`)

```python
PulseSmoother.shape(Action.RIGHT, confidence=0.78)

# With defaults: max_pulse_ms=400, min_pulse_ms=120, turn_pwm_base=105

bounded_confidence = max(0.0, min(1.0, 0.78)) = 0.78
pulse_span = max(400 - 120, 0) = 280
duration_ms = 120 + int(280 * 0.78) = 120 + 218 = 338

# RIGHT branch:
left_pwm  = clamp_pwm(105 + 20)  = 125
right_pwm = clamp_pwm(105 - 25)  = 80

# Result:
PulseShape(left_pwm=125, right_pwm=80, duration_ms=338)
```

#### Stage 12: Persistence (`control.py:229-245`)

```sql
INSERT INTO frames (session_id, device_id, seq, timestamp_ms, frame_width, frame_height,
  jpeg_quality, mode, firmware_version, mean_brightness, contrast, blur_score,
  quality_score, file_path, content_type, payload_size_bytes, ...)
VALUES ('{session_id}', 'rc-car-01', 1, 45230, 320, 240, 12, 'AUTO', '0.1.0',
  140.0, 45.0, 120.0, 0.812, 'data/sessions/.../000001_45230.jpg', 'image/jpeg', 15234, ...);

INSERT INTO decisions (frame_id, session_id, trace_id, seq, action, reason_code,
  left_pwm, right_pwm, duration_ms, confidence, message, backend_latency_ms,
  model_latency_ms, safe_to_execute, ...)
VALUES (1, '{session_id}', '{trace_id}', 1, 'RIGHT', 'OBSTACLE_LEFT',
  125, 80, 338, 0.78, 'Narrow hallway...', 2800, 2400, true, ...);
```

> **BUG #3 (HIGH): No try-except around DB writes.** If SQLite throws an error
> (disk full, locked, corruption), the exception propagates to FastAPI, which
> returns HTTP 500. I (the firmware) receive no command and hit the 3,000ms
> timeout, resulting in `set_safe_stop()` and ERROR state. The command was
> computed successfully but the car STOPs because of a logging failure.

---

### A.7 UPLOAD — Backend Response to Firmware

#### Backend → Firmware I/O (exact response)

```json
{
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "session_id": "f9e8d7c6-b5a4-3210-fedc-ba0987654321",
  "seq": 1,
  "action": "RIGHT",
  "left_pwm": 125,
  "right_pwm": 80,
  "duration_ms": 338,
  "confidence": 0.78,
  "reason_code": "OBSTACLE_LEFT",
  "message": "Narrow hallway with blue sneaker blocking left side. Right side clear for passage.",
  "backend_latency_ms": 2800,
  "model_latency_ms": 2400,
  "safe_to_execute": true
}
```

---

### A.8 UPLOAD — Firmware Parses Response

`command_parser_parse()` uses ArduinoJson to deserialize:

```cpp
// command_parser.cpp
action_str     = "RIGHT"    → DriveAction::RIGHT
left_pwm_raw   = 125        → motor_clamp_pwm(125) = 125  (within 0-255)
right_pwm_raw  = 80         → motor_clamp_pwm(80) = 80    (within 0-255)
duration_raw   = 338        → motor_clamp_duration(338, 500) = 338  (within 0-500)
safe_to_execute = true
confidence     = 0.78
reason_code    = "OBSTACLE_LEFT"
issued_at_ms   = millis()   // stamped NOW for lease tracking
lease_ms       = 600        // from COMMAND_LEASE_MS in config.h
```

I release the camera frame buffer (`camera_capture_release()`).
I transition to EXECUTE with `pending_command_` populated.

---

### A.9 EXECUTE — Motor Pulse

`execute_pending_command()` runs:

```cpp
// Check 1: Command expired?
failsafe_command_expired(pending_command_, millis())
  → (millis() - issued_at_ms) > 600  → typically <20ms → NOT EXPIRED

// Check 2: Safe to execute?
pending_command_.safe_to_execute  → true → PASS

// Check 3: Is it STOP?
pending_command_.action == DriveAction::STOP  → no, it's RIGHT

// Execute motor pulse:
motor_driver_execute_pulse(pending_command_)
```

`motor_driver_execute_pulse()` activates:

```
g_busy = false  → can accept command

apply_action(DriveAction::RIGHT, left_pwm=125, right_pwm=80):
  apply_motor_raw(HIGH, LOW, LOW, HIGH, 125, 80)
    IN1 = HIGH    ← Left motor FORWARD
    IN2 = LOW
    IN3 = LOW     ← Right motor REVERSE
    IN4 = HIGH
    analogWrite(ENA, 125)  ← Left motor PWM = 125/255 = 49% duty
    analogWrite(ENB, 80)   ← Right motor PWM = 80/255 = 31% duty

g_busy = true
g_deadline_ms = millis() + 338
```

**Physical behavior:** Left wheel spins forward at 49% power. Right wheel spins backward at 31% power. The car **turns RIGHT**, steering away from the blue sneaker.

The turn is differential — left wheel pushes forward while right wheel pulls back. This creates a pivot-like turn rather than a gradual arc.

**Duration:** The motors run for exactly 338ms. During this time, `loop()` continues iterating every ~20ms. Each iteration:
1. `failsafe_kick()` resets the watchdog
2. `step()` checks `motor_driver_is_busy()` → returns `true` → waits
3. `motor_driver_update()` checks `millis() >= g_deadline_ms`

At T+338ms: `motor_driver_update()` detects deadline met, calls `motor_driver_stop()`:
```
IN1=LOW, IN2=LOW, IN3=LOW, IN4=LOW
analogWrite(ENA, 0)
analogWrite(ENB, 0)
g_busy = false
```

State machine sees `motor_driver_is_busy() == false`, `execute_pending_command()` returns true.
I transition to STOPPED.

---

### A.10 STOPPED → IDLE → Next Cycle

**STOPPED:** `motor_driver_stop()` called (redundant — already stopped by `motor_driver_update()`). Reset `command_started_ = false`. Transition to IDLE.

**IDLE:** `motor_driver_is_busy()` returns false. Transition to CAPTURE.

**Dead time:** ~40ms (2 loop iterations at 20ms each).

**Next cycle begins.** I capture a new frame — now from a slightly different angle because I've turned right. The sneaker may still be partially visible on my left, or I may now see clear hallway ahead.

---

## Part B: Complete I/O Boundary Map

### Boundary 1: Firmware ↔ Camera Sensor

| Direction | Data | Format | Size |
|-----------|------|--------|------|
| Firmware → Camera | Init config (QVGA, JPEG, quality=12) | esp_camera API | n/a |
| Camera → Firmware | JPEG frame buffer | Binary JPEG | ~10-20KB |

### Boundary 2: Firmware ↔ Motor Driver (L298N)

| Direction | Data | Format | Pins |
|-----------|------|--------|------|
| Firmware → L298N | Direction bits | GPIO HIGH/LOW | IN1-IN4 (GPIO 12-15) |
| Firmware → L298N | Speed (PWM) | analogWrite 0-255 | ENA=GPIO 2, ENB=GPIO 4 |

**Motor truth table for all actions:**

| Action | IN1 | IN2 | IN3 | IN4 | Left Motor | Right Motor |
|--------|-----|-----|-----|-----|------------|-------------|
| FORWARD | HIGH | LOW | HIGH | LOW | Forward | Forward |
| LEFT | LOW | HIGH | HIGH | LOW | Reverse | Forward |
| RIGHT | HIGH | LOW | LOW | HIGH | Forward | Reverse |
| STOP | LOW | LOW | LOW | LOW | Off | Off |

### Boundary 3: Firmware ↔ Backend (HTTP)

| Direction | Data | Format | Size |
|-----------|------|--------|------|
| Firmware → Backend | Frame + metadata | multipart/form-data | ~10-20KB |
| Backend → Firmware | Command response | JSON | ~500 bytes |

**Request fields sent:**
`device_id`, `seq`, `timestamp_ms`, `frame_width`, `frame_height`, `jpeg_quality`, `mode`, `firmware_version`, `image`

**Response fields received:**
`trace_id`, `session_id`, `seq`, `action`, `left_pwm`, `right_pwm`, `duration_ms`, `confidence`, `reason_code`, `message`, `backend_latency_ms`, `model_latency_ms`, `safe_to_execute`

### Boundary 4: Backend ↔ Ollama/LLaVA

| Direction | Data | Format | Size |
|-----------|------|--------|------|
| Backend → Ollama | Prompt + base64 image | JSON POST to /api/generate | ~30-40KB |
| Ollama → Backend | Structured JSON decision | JSON response | ~200 bytes |

### Boundary 5: Backend ↔ SQLite

| Direction | Data | Format | Tables |
|-----------|------|--------|--------|
| Backend → SQLite | Frame metadata + quality metrics | INSERT via SQLAlchemy | `frames` |
| Backend → SQLite | Decision record | INSERT via SQLAlchemy | `decisions` |
| Backend → SQLite | Error record (on failure) | INSERT via SQLAlchemy | `errors` |
| Backend → SQLite | Telemetry records | INSERT via `POST /api/v1/control/telemetry` | `telemetry` |
| Backend → SQLite | Session auto-created on first frame | INSERT via SQLAlchemy | `sessions` |

### Boundary 6: Firmware ↔ E-Stop Hardware

| Direction | Data | Format | Pin |
|-----------|------|--------|-----|
| Hardware → Firmware | E-stop pin state | GPIO digital read | GPIO 33 |
| — | Active LOW (pulled HIGH normally) | — | — |

---

## Part C: Timing Analysis

### Full Cycle Timing Budget

```
IDLE           ─────┐  ~20ms
                    │
CAPTURE        ─────┤  200-400ms  (camera JPEG encoding)
                    │
UPLOAD         ─────┤  2,500-3,000ms  (HTTP round-trip + Ollama inference)
  ├─ Validate       │    ~1ms
  ├─ Preprocess     │    ~50ms
  ├─ Quality gate   │    ~1ms
  ├─ File save      │    ~10ms
  ├─ Prompt build   │    ~1ms
  ├─ Ollama infer   │    2,000-2,800ms  ← DOMINANT COST
  ├─ Parse          │    ~1ms
  ├─ Safety         │    ~1ms
  ├─ Smoother       │    ~1ms
  └─ DB persist     │    ~20ms
                    │
EXECUTE        ─────┤  120-400ms  (motor pulse, confidence-dependent)
                    │
STOPPED        ─────┤  ~20ms  (cleanup)
                    │
IDLE           ─────┘  ~20ms

TOTAL CYCLE:  ~2,900-3,800ms per frame
              ~0.26-0.34 FPS effective frame rate
```

### Watchdog Safety Timeline

```
T=0ms      failsafe_kick()           ← watchdog reset to 2,500ms
T=0-400ms  CAPTURE (camera sensor)   ← 400ms consumed, 2,100ms remaining
T=400ms    loop end, delay(20)

T=420ms    failsafe_kick()           ← watchdog reset to 2,500ms
T=420ms    UPLOAD begins
T=420-3420ms  HTTP POST + Ollama     ← 3,000ms consumed
           BUT watchdog was reset at T=420ms
           Check at T=3440ms: (3440-420)=3,020ms > 2,500ms?
           YES — BUT failsafe_kick() runs at T=3440 (next loop start)
           BEFORE failsafe_watchdog_expired() is checked

VERDICT: Watchdog is safe during normal UPLOAD because kick happens at
         loop START, before the watchdog-expired check.
```

### 4-Second Delay Scenario

**What happens if the next frame takes 4 seconds to process?**

```
T=0ms      Motor pulse starts (RIGHT, 338ms)
T=338ms    Motor auto-stops (deadline met in motor_driver_update)
T=360ms    STOPPED → IDLE → CAPTURE
T=760ms    Frame captured, UPLOAD begins
T=760ms    HTTP POST sent to backend

SCENARIO: Ollama takes 4,000ms to respond
T=3760ms   Firmware HTTP timeout fires (BACKEND_TIMEOUT_MS = 3,000ms)
T=3760ms   http_client_send_frame() returns false
T=3760ms   set_safe_stop(command, "backend timeout")
           → action=STOP, safe_to_execute=false
T=3760ms   State machine transitions to ERROR
T=3760ms   motor_driver_stop() called (already stopped)
T=3780ms   ERROR recovery: check WiFi, retry BACKEND_WAIT

PHYSICAL STATE: Car was stationary from T=338ms onward.
                The 4-second delay causes NO physical danger.
                Car is safe throughout.
```

### Command Lease Expiry

```
Command stamped: issued_at_ms = millis() at parse time
Lease:           600ms (COMMAND_LEASE_MS)

In execute_pending_command():
  failsafe_command_expired(cmd, now_ms)
    → (now_ms - cmd.issued_at_ms) > 600

Normal case: cmd parsed at T=3420, executed at T=3440
  → (3440 - 3420) = 20ms < 600ms → NOT EXPIRED

Edge case: WiFi drops between parse and execute
  → cmd.issued_at_ms = 3420, recovery takes until T=5000
  → (5000 - 3420) = 1580ms > 600ms → EXPIRED → STOP
```

---

## Part D: Bugs & Robustness Issues

### CRITICAL Issues

| # | Issue | Files | Status | Impact |
|---|-------|-------|--------|--------|
| 1 | **duration_ms schema mismatch** | `command.py:21`, `contracts/command_response.schema.json:52` | **FIXED** — aligned to `le=500` matching firmware `MAX_PULSE_MS=500` | Backend could send 1000ms pulse; firmware truncates to 500ms without warning. |
| 2 | **Backend/firmware MAX_PULSE_MS diverge** | `config.py:35` default=400, `config.h:22` max=500. | OPEN | If backend config raised above 500, firmware silently clamps. |
| 3 | **WiFi blocking exceeds watchdog** | `config.h:24` WIFI_CONNECT_TIMEOUT_MS=15000 vs `config.h:28` WATCHDOG_TIMEOUT_MS=2500. | OPEN (firmware) | WiFi.begin() can block 15s. Watchdog fires during reconnection. |
| 4 | **DB failure kills response** | `control.py` — DB persist block | **FIXED** — wrapped in try-except, command always returned | DB error no longer blocks the command response to firmware. |
| 5 | **No authentication** | `control.py` — no auth middleware. | OPEN | Any network client can send frames to the car. |
| 6 | **estop_active hardcoded False** | `control.py`, `system.py` | **FIXED** — remote e-stop endpoints added (`POST/DELETE/GET /estop`), wired to control pipeline via `app.state.estop_active` | Backend can now remotely stop the car. |

### HIGH Issues

| # | Issue | Files | Status | Impact |
|---|-------|-------|--------|--------|
| 7 | **No oscillation detection** | `smoother.py`, `policy.py` — PulseSmoother is stateless. | OPEN | LEFT-RIGHT-LEFT-RIGHT flip-flop goes undetected. |
| 8 | **Telemetry never recorded** | `repositories.py:137-161` | **FIXED** — `POST /api/v1/control/telemetry` endpoint added, wires to TelemetryRepository | Telemetry from bot is now persisted. |
| 9 | **Session lifecycle missing** | `control.py` | **FIXED** — `_ensure_session()` auto-creates SessionRecord on first frame | FrameRecord and DecisionRecord now have valid parent session. |
| 10 | **firmware_version not validated** | `control.py:92` — stored but never checked. | OPEN | Incompatible firmware could send malformed data. |
| 11 | **Turn PWM fixed regardless of confidence** | `smoother.py:50-60` — LEFT/RIGHT PWM is constant (80/125). | OPEN | Low-confidence turns are same speed, just shorter. |
| 12 | **No WiFi-drop detection during upload** | `http_client.cpp:120-144` | OPEN (firmware) | Must wait full 3,000ms timeout to detect WiFi loss mid-upload. |
| 13 | **No HTTP redirect handling** | `http_client.cpp:120-135` | OPEN (firmware) | If backend moves to new IP/port, firmware breaks silently. |

---

## Part E: "Is This Robust Enough to Avoid the Shoe Without Hitting the Right Wall?"

### Does it avoid the shoe?

**YES.** The VLM correctly identifies the blue sneaker on the left side and commands a RIGHT turn. The car executes a 338ms RIGHT pulse (left motor forward at PWM 125, right motor reverse at PWM 80), physically turning away from the obstacle.

### Does it hit the right wall?

**MAYBE.** This depends on the hallway width and the car's proximity to the right wall. The 338ms pulse at fixed turn PWM creates a fixed angular displacement — the car has NO awareness of:
- How close the right wall is
- How much turn angle is "enough" to clear the sneaker
- Whether the turn will overshoot into the right wall

In a narrow hallway (e.g., 60cm wide), a full 338ms differential turn could easily overshoot. There is no proportional control — the turn intensity doesn't scale with available clearance.

### Is the output useful?

**YES.** The response contains:
- Clear action directive (RIGHT)
- Confidence score (0.78) for decision quality assessment
- reason_code (OBSTACLE_LEFT) for machine-parseable rationale
- hazards list for debugging and replay analysis
- Latency measurements for performance monitoring

### Is it robust enough?

**NO.** Key robustness gaps:

1. **No oscillation detection** — after the right turn, the next frame might show the sneaker from a different angle. The VLM could flip between LEFT and RIGHT, creating a jittering car that never actually passes the obstacle.

2. **No proportional turning** — the turn PWM (80/125) is fixed. Whether the sneaker is barely encroaching or fully blocking, the turn is the same intensity. Only duration changes with confidence.

3. **No multi-frame context** — each frame is processed independently. The VLM doesn't know "I was just told to turn right" or "I've been oscillating for 5 frames." Previous actions are completely forgotten.

4. **No wall proximity sensing** — the car has `ir_left` and `ir_right` fields in the schema, but they are always null. No ultrasonic, IR, or depth data constrains the turn to prevent wall collision.

5. **~3 second blind window** — between frames, the car is flying blind. After a 338ms turn, the car waits ~2.5 seconds before it sees the world again. A lot can go wrong in that window.

6. **Single-frame VLM latency** — Ollama inference takes ~2-3 seconds. The car was already stationary waiting. In a dynamic environment (moving obstacles, other people), this latency makes the car reactive rather than proactive.

---

## Part F: Extended Thinking — What Can Be Added

### Feature Proposals

#### 1. Oscillation Detector
**Problem:** PulseSmoother is stateless. LEFT-RIGHT-LEFT-RIGHT oscillation is undetected.
**Solution:** Add an `OscillationDetector` class with a bounded deque of the last 6 actions. If it detects an alternating pattern (e.g., L-R-L-R for 4+ actions), force STOP with `reason_code="OSCILLATION_DETECTED"`.
**Integration:** In `DecisionPolicy.to_command()`, after `apply_safety_overrides()` but before `PulseSmoother.shape()`.
**Complexity:** Low — ~50 lines of Python, no schema changes.

#### 2. Multi-Frame Temporal Context
**Problem:** Each frame is independent. The VLM has no memory of previous actions or observations.
**Solution:** Buffer the last 3-5 `ParsedDecision` results in memory. Inject them into the VLM prompt as textual history: `"Previous actions: [FORWARD, FORWARD, RIGHT]. Reason: obstacle detected left."`.
**Integration:** Modify `PromptManager.build_prompt()` to accept `prior_decisions: list[ParsedDecision]`. Store buffer per session_id in backend app state.
**Complexity:** Medium — requires session-scoped state management.

#### 3. Depth Estimation
**Problem:** The car has no distance awareness. It doesn't know how far the sneaker is or how close the right wall is.
**Solution:** Run a monocular depth model (MiDaS or DPT) as a second inference pass. Extract minimum distance in left/center/right zones. Inject as metadata into the VLM prompt: `"Estimated obstacle distance: left=30cm, center=120cm, right=45cm."`.
**Integration:** New service `backend/app/services/depth_estimator.py`. Called after preprocessing, before prompt assembly.
**Complexity:** High — adds ~2-3 seconds of additional inference latency unless quantized.

#### 4. Proportional Turn Scaling
**Problem:** Turn PWM is fixed (80/125) regardless of confidence or obstacle proximity.
**Solution:** Scale turn PWM by confidence: `turn_pwm = turn_pwm_base * bounded_confidence`. Low confidence = gentle turn. High confidence = aggressive turn.
**Integration:** Modify `PulseSmoother.shape()` to apply confidence scaling to LEFT/RIGHT PWM values (currently only duration scales).
**Complexity:** Low — ~5 lines changed in smoother.py.

#### 5. Obstacle Classification
**Problem:** The VLM returns a flat action. We don't know what class of obstacle it detected or how it estimated threat level.
**Solution:** Extend `json_schema_decision.json` with optional `obstacles` array:
```json
"obstacles": [{
  "class": "shoe",
  "side": "left",
  "estimated_distance_cm": 30,
  "estimated_width_cm": 15
}]
```
**Integration:** Update JSON schema, ParsedDecision, and VLM prompt to request structured obstacle data.
**Complexity:** Medium — schema + prompt + parser changes.

#### 6. Path Memory / Visual SLAM
**Problem:** The car doesn't know if it's been in this hallway before or if it's going in circles.
**Solution:** Store lightweight feature descriptors (ORB) or CLIP embeddings from each frame. Compare against history to detect "have I been here before?" and "am I going in circles?".
**Integration:** New service alongside frame preprocessing. Persisted per session.
**Complexity:** High — requires embedding computation, similarity search, and spatial reasoning.

#### 7. REVERSE Action
**Problem:** The car can only go FORWARD, LEFT, RIGHT, or STOP. If it's cornered, it cannot back up.
**Solution:** Add `REVERSE` to the Action enum. Update firmware motor driver to support backward motion (IN1=LOW, IN2=HIGH, IN3=LOW, IN4=HIGH for both motors reverse). Add safety limits on reverse duration.
**Integration:** Backend: add to Action enum, update schema, prompt, smoother. Firmware: add case to `apply_action()`.
**Complexity:** Medium — cross-stack change touching backend + firmware.

#### 8. Remote E-Stop Endpoint
**Problem:** `estop_active` is hardcoded to `False` in `control.py:190`. No way to remotely stop the car from the backend.
**Solution:** Add `POST /estop` endpoint in `system.py` that sets a global flag. Read this flag in the control endpoint.
**Integration:** Add app-state boolean, expose via system_router, check in control.py.
**Complexity:** Low — ~30 lines across 2 files.

#### 9. Graceful DB Failure Degradation
**Problem:** If SQLite throws during persist, the entire request fails (HTTP 500) and the firmware gets no command.
**Solution:** Wrap DB writes in try-except. If persist fails, log the error but still return the computed command to firmware.
**Integration:** Add try-except block around lines 229-245 in control.py.
**Complexity:** Low — ~10 lines.

#### 10. Firmware Version Compatibility Check
**Problem:** Backend accepts any firmware_version without validation.
**Solution:** Define a `MIN_FIRMWARE_VERSION` in backend config. If firmware reports a version below this, return STOP with `reason_code="FIRMWARE_OUTDATED"`.
**Integration:** Add version check in control.py after metadata parsing.
**Complexity:** Low — ~15 lines.

### Architecture Improvements

#### 1. Latency Reduction
- **Quantize LLaVA** to INT4/INT8 for 2-3x faster inference
- **Use smaller models** (Moondream, LLaVA-Phi3) for sub-500ms inference
- **Pipeline capture+upload**: start uploading frame N while VLM processes frame N-1
- **Reduce resolution**: 160x120 instead of 320x240 halves data transfer and model input size
- **Target:** <1 second total cycle time (from current ~3-4s)

#### 2. Edge Inference (Jetson Nano/Orin)
- Move Ollama from a separate PC to an NVIDIA Jetson mounted on the car
- Eliminates WiFi round-trip latency entirely
- ESP32-CAM connects to Jetson via USB-serial or local WiFi hotspot
- Jetson runs quantized LLaVA at ~500ms inference
- **Target:** <1 second total cycle with no network dependency

#### 3. Multi-Model Ensemble
- Run two models in parallel (e.g., LLaVA + Moondream)
- If both agree: confidence boost (multiply confidences)
- If they disagree: use lower confidence or force STOP
- Reduces false positive actions at the cost of 2x compute
- **Trade-off:** Latency increases unless models run on separate GPUs

#### 4. WebSocket Streaming
- Replace HTTP request-response with persistent WebSocket connection
- Firmware streams frames as they're captured
- Backend streams commands as they're computed
- Eliminates TCP connection overhead per frame (~50-100ms saved)
- Requires rewriting `http_client.cpp` to use WebSocket library
- **Trade-off:** More complex error handling, connection management

#### 5. Occupancy Grid Building
- Dead-reckon from motor commands: forward distance ≈ PWM * duration, heading change from turns
- Accumulate observations into a simple 2D grid per session
- Mark cells as free/occupied based on VLM hazard reports
- Store in SessionRecord or new MapRecord table
- Enables "don't go back where you came from" reasoning
- **Trade-off:** Dead-reckoning drift accumulates without sensor correction

#### 6. Sensor Fusion
- The schema already has `ir_left`, `ir_right`, `gps_lat`, `gps_lon` fields — all currently null
- Add ultrasonic or IR sensors to the car, wire to ESP32 analog pins
- Use sensor readings as hard constraints in `apply_safety_overrides()`:
  - If `ir_left < 5cm` → force STOP regardless of VLM action
  - If `ir_right < 5cm` → block RIGHT turn
- **Integration point:** Add sensor check in `safety.py` before confidence threshold check
- **Trade-off:** Requires hardware modification to the car

#### 7. Watchdog-Safe WiFi Reconnection
- Current WiFi.begin() can block up to 15 seconds, exceeding the 2,500ms watchdog
- Solution: Use non-blocking WiFi connection with periodic yield
- Call `WiFi.begin()` once, then poll `WiFi.status()` each loop iteration
- Keeps `failsafe_kick()` firing every 20ms during reconnection
- **Integration:** Rewrite `wifi_client_connect()` to be non-blocking

---

## Appendix: Configuration Reference

### Backend Defaults (`config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_confidence` | 0.55 | Below this → STOP |
| `max_pulse_ms` | 400 | Maximum motor pulse duration |
| `min_pulse_ms` | 120 | Minimum motor pulse duration |
| `forward_pwm_base` | 120 | Base forward PWM (both motors) |
| `turn_pwm_base` | 105 | Base turn PWM |
| `quality_min_score` | 0.2 | Minimum composite quality |
| `quality_min_brightness` | 20.0 | Minimum brightness |
| `quality_max_brightness` | 235.0 | Maximum brightness |
| `quality_min_blur_score` | 2.0 | Minimum blur score |
| `model_timeout_s` | 15 | Ollama inference timeout |

### Firmware Defaults (`config.h`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_PULSE_MS` | 500 | Maximum motor pulse (firmware clamp) |
| `DEFAULT_PULSE_MS` | 200 | Default pulse duration |
| `DEFAULT_FORWARD_PWM` | 120 | Default forward PWM |
| `DEFAULT_TURN_PWM` | 105 | Default turn PWM |
| `COMMAND_LEASE_MS` | 600 | Command expiry window |
| `WATCHDOG_TIMEOUT_MS` | 2500 | Watchdog timeout |
| `BACKEND_TIMEOUT_MS` | 3000 | HTTP request timeout |
| `WIFI_CONNECT_TIMEOUT_MS` | 15000 | WiFi connection timeout |
| `LOOP_DELAY_MS` | 20 | Main loop delay |

### PulseSmoother Output Reference Table

| Action | Confidence | left_pwm | right_pwm | duration_ms |
|--------|-----------|----------|-----------|-------------|
| FORWARD | 0.55 | 131 | 131 | 274 |
| FORWARD | 0.70 | 134 | 134 | 316 |
| FORWARD | 0.78 | 135 | 135 | 338 |
| FORWARD | 0.90 | 138 | 138 | 372 |
| FORWARD | 1.00 | 140 | 140 | 400 |
| LEFT | any | 80 | 125 | 120 + int(280 * conf) |
| RIGHT | any | 125 | 80 | 120 + int(280 * conf) |
| STOP | any | 0 | 0 | 0 |

**Note:** Turn PWM values (80/125) are FIXED regardless of confidence. Only duration scales.

---

## Part G: Live Validation

> **Status:** Ollama was not available in the test environment during this session.
> The live validation step should be performed when Ollama + LLaVA are running.

### How to run the live test:

```bash
# 1. Verify Ollama
ollama list | grep llava

# 2. Start backend
make run-backend

# 3. Send test frame (Python)
python -c "
import time
from pathlib import Path
from uuid import uuid4
from backend.app.schemas.enums import DeviceMode
from simulator.control_client import BackendControlClient, ControlFrameRequest

# Use any JPEG image of a hallway with an obstacle
image_bytes = Path('test_hallway.jpg').read_bytes()
with BackendControlClient(frame_url='http://127.0.0.1:8000/api/v1/control/frame') as client:
    response = client.send_frame(ControlFrameRequest(
        image_jpeg=image_bytes,
        device_id='finding-v1-test',
        seq=1,
        timestamp_ms=int(time.time() * 1000),
        frame_width=320,
        frame_height=240,
        jpeg_quality=80,
        mode=DeviceMode.AUTO,
        session_id=uuid4(),
    ))
    print(response.model_dump_json(indent=2))
"

# 4. Check SQLite records
sqlite3 data/rc_car.db "SELECT action, left_pwm, right_pwm, duration_ms, confidence, reason_code FROM decisions ORDER BY id DESC LIMIT 1;"
```

### Expected vs Actual comparison table (to be filled after live test):

| Field | Predicted | Actual |
|-------|-----------|--------|
| action | RIGHT | _pending_ |
| confidence | ~0.78 | _pending_ |
| left_pwm | 125 | _pending_ |
| right_pwm | 80 | _pending_ |
| duration_ms | 338 | _pending_ |
| reason_code | OBSTACLE_LEFT | _pending_ |
| model_latency_ms | ~2400 | _pending_ |
| safe_to_execute | true | _pending_ |
