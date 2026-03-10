#pragma once

#include <Arduino.h>

namespace fwconfig {
inline constexpr char WIFI_SSID[] = "REPLACE_WITH_WIFI_SSID";
inline constexpr char WIFI_PASSWORD[] = "REPLACE_WITH_WIFI_PASSWORD";
inline constexpr char DEVICE_ID[] = "rc-car-01";

inline constexpr char BACKEND_BASE_URL[] = "http://192.168.1.2:8000";
inline constexpr char CONTROL_PATH[] = "/api/v1/control/frame";
inline constexpr char HEALTH_PATH[] = "/health";

inline constexpr uint16_t CAMERA_FRAME_WIDTH = 320;
inline constexpr uint16_t CAMERA_FRAME_HEIGHT = 240;
inline constexpr uint8_t CAMERA_JPEG_QUALITY = 12;

inline constexpr uint8_t DEFAULT_FORWARD_PWM = 120;
inline constexpr uint8_t DEFAULT_TURN_PWM = 105;
inline constexpr uint16_t DEFAULT_PULSE_MS = 200;
inline constexpr uint16_t MAX_PULSE_MS = 500;
inline constexpr uint16_t COMMAND_LEASE_MS = 600;

inline constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
inline constexpr uint32_t BACKEND_TIMEOUT_MS = 3000;
inline constexpr uint32_t LOOP_DELAY_MS = 20;
inline constexpr uint32_t WATCHDOG_TIMEOUT_MS = 2500;

inline constexpr bool ESTOP_ACTIVE_LOW = true;
}
