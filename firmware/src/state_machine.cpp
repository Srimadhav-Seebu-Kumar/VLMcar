#include "state_machine.h"

#include <Arduino.h>

#include "camera_capture.h"
#include "failsafe.h"
#include "http_client.h"
#include "motor_driver.h"
#include "serial_console.h"
#include "wifi_client.h"

FirmwareStateMachine::FirmwareStateMachine() : state_(FirmwareState::BOOTING), sequence_(0) {}

void FirmwareStateMachine::step() {
  switch (state_) {
    case FirmwareState::BOOTING:
      transition_to(FirmwareState::WIFI_CONNECTING, "boot complete");
      break;
    case FirmwareState::WIFI_CONNECTING:
      if (wifi_client_connect()) {
        transition_to(FirmwareState::BACKEND_WAIT, "wifi connected");
      }
      break;
    case FirmwareState::BACKEND_WAIT:
      if (http_client_health_check()) {
        transition_to(FirmwareState::IDLE, "backend healthy");
      }
      break;
    case FirmwareState::IDLE:
      transition_to(FirmwareState::CAPTURE, "next loop");
      break;
    case FirmwareState::CAPTURE:
      transition_to(FirmwareState::UPLOAD, "capture scheduled");
      break;
    case FirmwareState::UPLOAD:
      transition_to(FirmwareState::STOPPED, "upload not yet implemented");
      break;
    case FirmwareState::EXECUTE:
      transition_to(FirmwareState::STOPPED, "execute complete");
      break;
    case FirmwareState::STOPPED:
      motor_driver_stop();
      transition_to(FirmwareState::IDLE, "stopped safely");
      break;
    case FirmwareState::ERROR:
      motor_driver_stop();
      transition_to(FirmwareState::BACKEND_WAIT, "recover from error");
      break;
    case FirmwareState::ESTOP:
      motor_driver_stop();
      break;
  }
  ++sequence_;
}

FirmwareState FirmwareStateMachine::state() const { return state_; }

void FirmwareStateMachine::transition_to(FirmwareState next, const char* reason) {
  if (next == state_) {
    return;
  }
  serial_console_log_state(state_, next, reason);
  state_ = next;
}
