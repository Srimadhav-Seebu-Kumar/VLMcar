# Firmware Architecture

## Target platform
- PlatformIO + Arduino framework
- ESP32-CAM board
- L298N motor driver for differential steering

## Firmware module map
- `camera_capture.*`: initialize sensor and capture JPEG bytes.
- `wifi_client.*`: connect and reconnect to configured WLAN.
- `http_client.*`: health checks and multipart frame upload.
- `command_parser.*`: parse backend command JSON safely.
- `motor_driver.*`: PWM control and pulse execution.
- `state_machine.*`: explicit state transitions.
- `failsafe.*`: watchdog, timeout, ESTOP behavior.

## Control policy
- Firmware never executes a command without successful parse and validation.
- Every motion command has finite `duration_ms`.
- Motors are stopped at end of pulse and on every error path.
- Camera capture requires explicit frame release before next capture.

## State transitions

```text
BOOTING -> WIFI_CONNECTING -> BACKEND_WAIT -> IDLE
IDLE -> CAPTURE -> UPLOAD -> EXECUTE -> IDLE
UPLOAD failure -> ERROR -> BACKEND_WAIT
parse failure -> STOPPED
ESTOP asserted -> ESTOP (terminal until cleared)
```

## Configuration
All configurable values live in firmware headers:
- Wi-Fi SSID/password
- backend URL
- camera frame size and JPEG quality
- PWM limits and pulse duration caps
- timeout and watchdog intervals

## Diagnostics
Serial logs must include:
- state transitions
- backend status and HTTP code
- command summary (action, pwm, duration)
- explicit reason for every STOP event
