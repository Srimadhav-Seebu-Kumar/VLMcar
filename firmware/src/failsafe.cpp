#include "failsafe.h"

#include <Arduino.h>

#include "config.h"

namespace {
uint32_t g_last_kick_ms = 0;
bool g_estop_active = false;
}  // namespace

void failsafe_init() {
  g_last_kick_ms = millis();
  g_estop_active = false;
}

void failsafe_kick() { g_last_kick_ms = millis(); }

bool failsafe_watchdog_expired() { return (millis() - g_last_kick_ms) > fwconfig::WATCHDOG_TIMEOUT_MS; }

void failsafe_set_estop(bool active) { g_estop_active = active; }

bool failsafe_estop_active() { return g_estop_active; }

bool failsafe_command_expired(const MotionCommand& command, uint32_t now_ms) {
  if (command.lease_ms == 0) {
    return false;
  }
  return (now_ms - command.issued_at_ms) > command.lease_ms;
}
