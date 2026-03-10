#include "motor_driver.h"

#include <Arduino.h>

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
  apply_motor_raw(LOW, LOW, LOW, LOW, 0, 0);
  g_busy = false;
  g_deadline_ms = 0;
}

bool motor_driver_execute_pulse(const MotionCommand& command) {
  if (g_busy) {
    return false;
  }

  switch (command.action) {
    case DriveAction::FORWARD:
      apply_motor_raw(HIGH, LOW, HIGH, LOW, command.left_pwm, command.right_pwm);
      break;
    case DriveAction::LEFT:
      apply_motor_raw(LOW, HIGH, HIGH, LOW, command.left_pwm, command.right_pwm);
      break;
    case DriveAction::RIGHT:
      apply_motor_raw(HIGH, LOW, LOW, HIGH, command.left_pwm, command.right_pwm);
      break;
    case DriveAction::STOP:
      motor_driver_stop();
      return true;
  }

  g_busy = command.duration_ms > 0;
  g_deadline_ms = millis() + command.duration_ms;
  if (!g_busy) {
    motor_driver_stop();
  }
  return true;
}

bool motor_driver_is_busy() { return g_busy; }

void motor_driver_update() {
  if (g_busy && millis() >= g_deadline_ms) {
    motor_driver_stop();
  }
}
