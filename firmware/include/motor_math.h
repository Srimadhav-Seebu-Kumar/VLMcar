#pragma once

#include <algorithm>
#include <cstdint>

constexpr uint8_t motor_clamp_pwm_constexpr(int value) {
  return static_cast<uint8_t>(value < 0 ? 0 : (value > 255 ? 255 : value));
}

constexpr uint16_t motor_clamp_duration_constexpr(uint32_t duration_ms, uint16_t max_duration_ms) {
  return static_cast<uint16_t>(duration_ms > max_duration_ms ? max_duration_ms : duration_ms);
}

static_assert(motor_clamp_pwm_constexpr(-20) == 0, "PWM clamp must floor at 0");
static_assert(motor_clamp_pwm_constexpr(300) == 255, "PWM clamp must cap at 255");
static_assert(motor_clamp_duration_constexpr(800, 500) == 500,
              "Duration clamp must cap at configured max");

inline uint8_t motor_clamp_pwm(int value) {
  return motor_clamp_pwm_constexpr(value);
}

inline uint16_t motor_clamp_duration(uint32_t duration_ms, uint16_t max_duration_ms) {
  return motor_clamp_duration_constexpr(duration_ms, max_duration_ms);
}
