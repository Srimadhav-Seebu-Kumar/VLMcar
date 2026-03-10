#include "failsafe.h"

#include <Arduino.h>

#include "config.h"
#include "pins.h"

namespace {
uint32_t g_last_kick_ms = 0;
bool g_estop_active = false;

bool read_estop_pin_active() {
  const int raw_value = digitalRead(fwpins::ESTOP_PIN);
  if (fwconfig::ESTOP_ACTIVE_LOW) {
    return raw_value == LOW;
  }
  return raw_value == HIGH;
}
}  // namespace

void failsafe_init() {
  pinMode(fwpins::ESTOP_PIN, INPUT_PULLUP);
  g_last_kick_ms = millis();
  g_estop_active = false;
}

void failsafe_kick() { g_last_kick_ms = millis(); }

void failsafe_update_inputs() {
  const bool pin_estop = read_estop_pin_active();
  if (pin_estop != g_estop_active) {
    g_estop_active = pin_estop;
    Serial.printf("[failsafe] estop %s\n", g_estop_active ? "ACTIVE" : "CLEARED");
  }
}

bool failsafe_watchdog_expired() { return (millis() - g_last_kick_ms) > fwconfig::WATCHDOG_TIMEOUT_MS; }

void failsafe_set_estop(bool active) { g_estop_active = active; }

bool failsafe_estop_active() { return g_estop_active; }

bool failsafe_command_expired(const MotionCommand& command, uint32_t now_ms) {
  if (command.lease_ms == 0) {
    return false;
  }
  return (now_ms - command.issued_at_ms) > command.lease_ms;
}
