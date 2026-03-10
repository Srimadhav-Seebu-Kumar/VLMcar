#include "motor_driver.h"

#include <Arduino.h>

#include "config.h"
#include "motor_math.h"
#include "pins.h"

namespace {
bool g_busy = false;
uint32_t g_deadline_ms = 0;

void apply_motor_raw(uint8_t in1, uint8_t in2, uint8_t in3, uint8_t in4, uint8_t left_pwm,
                     uint8_t right_pwm) {
  digitalWrite(fwpins::MOTOR_IN1, in1);
  digitalWrite(fwpins::MOTOR_IN2, in2);
  digitalWrite(fwpins::MOTOR_IN3, in3);
  digitalWrite(fwpins::MOTOR_IN4, in4);
  analogWrite(fwpins::MOTOR_ENA, left_pwm);
  analogWrite(fwpins::MOTOR_ENB, right_pwm);
}

void apply_action(DriveAction action, uint8_t left_pwm, uint8_t right_pwm) {
  switch (action) {
    case DriveAction::FORWARD:
      apply_motor_raw(HIGH, LOW, HIGH, LOW, left_pwm, right_pwm);
      return;
    case DriveAction::LEFT:
      apply_motor_raw(LOW, HIGH, HIGH, LOW, left_pwm, right_pwm);
      return;
    case DriveAction::RIGHT:
      apply_motor_raw(HIGH, LOW, LOW, HIGH, left_pwm, right_pwm);
      return;
    case DriveAction::STOP:
      apply_motor_raw(LOW, LOW, LOW, LOW, 0, 0);
      return;
  }
}
}  // namespace

void motor_driver_init() {
  pinMode(fwpins::MOTOR_IN1, OUTPUT);
  pinMode(fwpins::MOTOR_IN2, OUTPUT);
  pinMode(fwpins::MOTOR_IN3, OUTPUT);
  pinMode(fwpins::MOTOR_IN4, OUTPUT);
  pinMode(fwpins::MOTOR_ENA, OUTPUT);
  pinMode(fwpins::MOTOR_ENB, OUTPUT);
  motor_driver_stop();
}

void motor_driver_stop() {
  apply_action(DriveAction::STOP, 0, 0);
  g_busy = false;
  g_deadline_ms = 0;
}

void motor_driver_forward(uint8_t left_pwm, uint8_t right_pwm) {
  apply_action(DriveAction::FORWARD, motor_clamp_pwm(left_pwm), motor_clamp_pwm(right_pwm));
}

void motor_driver_left(uint8_t left_pwm, uint8_t right_pwm) {
  apply_action(DriveAction::LEFT, motor_clamp_pwm(left_pwm), motor_clamp_pwm(right_pwm));
}

void motor_driver_right(uint8_t left_pwm, uint8_t right_pwm) {
  apply_action(DriveAction::RIGHT, motor_clamp_pwm(left_pwm), motor_clamp_pwm(right_pwm));
}

bool motor_driver_execute_pulse(const MotionCommand& command) {
  if (g_busy) {
    return false;
  }

  const uint8_t left_pwm = motor_clamp_pwm(command.left_pwm);
  const uint8_t right_pwm = motor_clamp_pwm(command.right_pwm);
  const uint16_t duration_ms = motor_clamp_duration(command.duration_ms, fwconfig::MAX_PULSE_MS);

  if (command.action == DriveAction::STOP) {
    motor_driver_stop();
    return true;
  }

  apply_action(command.action, left_pwm, right_pwm);
  if (duration_ms == 0) {
    motor_driver_stop();
    return true;
  }

  g_busy = true;
  g_deadline_ms = millis() + duration_ms;
  return true;
}

bool motor_driver_is_busy() { return g_busy; }

void motor_driver_update() {
  if (g_busy && millis() >= g_deadline_ms) {
    motor_driver_stop();
  }
}
