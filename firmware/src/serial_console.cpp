#include "serial_console.h"

#include <Arduino.h>

namespace {
const char* state_name(FirmwareState state) {
  switch (state) {
    case FirmwareState::BOOTING:
      return "BOOTING";
    case FirmwareState::WIFI_CONNECTING:
      return "WIFI_CONNECTING";
    case FirmwareState::BACKEND_WAIT:
      return "BACKEND_WAIT";
    case FirmwareState::IDLE:
      return "IDLE";
    case FirmwareState::CAPTURE:
      return "CAPTURE";
    case FirmwareState::UPLOAD:
      return "UPLOAD";
    case FirmwareState::EXECUTE:
      return "EXECUTE";
    case FirmwareState::STOPPED:
      return "STOPPED";
    case FirmwareState::ERROR:
      return "ERROR";
    case FirmwareState::ESTOP:
      return "ESTOP";
  }
  return "UNKNOWN";
}
}  // namespace

void serial_console_init() { Serial.begin(115200); }

void serial_console_log_state(FirmwareState from, FirmwareState to, const char* reason) {
  Serial.printf("[state] %s -> %s (%s)\n", state_name(from), state_name(to), reason);
}

void serial_console_log_error(const char* message) { Serial.printf("[error] %s\n", message); }

void serial_console_log_command(const MotionCommand& command) {
  Serial.printf(
      "[cmd] action=%d left=%u right=%u duration=%u reason=%s trace=%s session=%s\n",
      static_cast<int>(command.action), command.left_pwm, command.right_pwm, command.duration_ms,
      command.reason_code.c_str(), command.trace_id.c_str(), command.session_id.c_str());
}
