#pragma once

#include <Arduino.h>

namespace fwpins {
inline constexpr uint8_t MOTOR_IN1 = 12;
inline constexpr uint8_t MOTOR_IN2 = 13;
inline constexpr uint8_t MOTOR_IN3 = 14;
inline constexpr uint8_t MOTOR_IN4 = 15;
inline constexpr uint8_t MOTOR_ENA = 2;
inline constexpr uint8_t MOTOR_ENB = 4;

inline constexpr uint8_t ESTOP_PIN = 33;

// AI Thinker ESP32-CAM pins
inline constexpr int CAM_PIN_PWDN = 32;
inline constexpr int CAM_PIN_RESET = -1;
inline constexpr int CAM_PIN_XCLK = 0;
inline constexpr int CAM_PIN_SIOD = 26;
inline constexpr int CAM_PIN_SIOC = 27;
inline constexpr int CAM_PIN_D7 = 35;
inline constexpr int CAM_PIN_D6 = 34;
inline constexpr int CAM_PIN_D5 = 39;
inline constexpr int CAM_PIN_D4 = 36;
inline constexpr int CAM_PIN_D3 = 21;
inline constexpr int CAM_PIN_D2 = 19;
inline constexpr int CAM_PIN_D1 = 18;
inline constexpr int CAM_PIN_D0 = 5;
inline constexpr int CAM_PIN_VSYNC = 25;
inline constexpr int CAM_PIN_HREF = 23;
inline constexpr int CAM_PIN_PCLK = 22;
}
