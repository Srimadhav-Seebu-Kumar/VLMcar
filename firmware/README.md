# Firmware

## Target
- ESP32-CAM (AI Thinker)
- Arduino framework via PlatformIO

## Build
```bash
python -m platformio run -d firmware -e esp32cam
```

## Flash (when hardware is connected)
```bash
python -m platformio run -d firmware -e esp32cam -t upload
```

## Serial monitor
```bash
python -m platformio device monitor -b 115200
```

## Configuration
Centralized firmware runtime configuration is in:
- `include/config.h`
- `include/pins.h`
- `include/protocol.h`
- `include/types.h`

Set Wi-Fi and backend values in `include/config.h` before flashing hardware.

## Safety baseline
- Startup state is stationary.
- Motor pulses are bounded and auto-stop.
- Overlapping pulse execution is rejected.
- Motor clamp behavior is compile-time checked via `static_assert` in `motor_math.h`.
- Scaffold failsafe and explicit state-machine transitions are included.
