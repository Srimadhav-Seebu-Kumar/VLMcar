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

/**
 * Convert heading_deg (-90..90) + throttle (0..1) to differential PWM.
 * heading > 0 turns right (left motor faster), heading < 0 turns left.
 */
inline void motor_heading_to_pwm(
    int8_t heading_deg,
    float throttle,
    uint8_t base_pwm,
    uint8_t& out_left_pwm,
    uint8_t& out_right_pwm) {
  if (throttle <= 0.0f) {
    out_left_pwm = 0;
    out_right_pwm = 0;
    return;
  }
  float clamped_throttle = throttle > 1.0f ? 1.0f : throttle;
  float scaled_pwm = static_cast<float>(base_pwm) * clamped_throttle;
  int8_t clamped_heading = heading_deg < -90 ? -90 : (heading_deg > 90 ? 90 : heading_deg);
  float turn_ratio = static_cast<float>(clamped_heading) / 90.0f;
  out_left_pwm = motor_clamp_pwm(static_cast<int>(scaled_pwm * (1.0f + turn_ratio)));
  out_right_pwm = motor_clamp_pwm(static_cast<int>(scaled_pwm * (1.0f - turn_ratio)));
}
