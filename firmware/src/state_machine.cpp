#include "state_machine.h"

#include <Arduino.h>

#include "camera_capture.h"
#include "config.h"
#include "failsafe.h"
#include "http_client.h"
#include "motor_driver.h"
#include "serial_console.h"
#include "wifi_client.h"

FirmwareStateMachine::FirmwareStateMachine()
    : state_(FirmwareState::BOOTING),
      sequence_(0),
      command_started_(false),
      frame_(),
      frame_metadata_(),
      pending_command_(),
      last_error_("") {}

void FirmwareStateMachine::step() {
  if (failsafe_estop_active()) {
    transition_to(FirmwareState::ESTOP, "failsafe estop active");
  }

  if (failsafe_watchdog_expired() && state_ != FirmwareState::ESTOP) {
    last_error_ = "watchdog timeout";
    transition_to(FirmwareState::ERROR, "watchdog expired");
  }

  switch (state_) {
    case FirmwareState::BOOTING:
      if (!camera_capture_init()) {
        last_error_ = "camera init failed";
        transition_to(FirmwareState::ERROR, "camera init failed");
        break;
      }
      transition_to(FirmwareState::WIFI_CONNECTING, "boot complete");
      break;

    case FirmwareState::WIFI_CONNECTING:
      if (wifi_client_connect()) {
        transition_to(FirmwareState::BACKEND_WAIT, "wifi connected");
      }
      break;

    case FirmwareState::BACKEND_WAIT:
      if (!wifi_client_is_connected()) {
        transition_to(FirmwareState::WIFI_CONNECTING, "wifi disconnected");
        break;
      }
      if (http_client_health_check()) {
        transition_to(FirmwareState::IDLE, "backend reachable");
      }
      break;

    case FirmwareState::IDLE:
      if (motor_driver_is_busy()) {
        break;
      }
      transition_to(FirmwareState::CAPTURE, "loop ready");
      break;

    case FirmwareState::CAPTURE:
      if (capture_frame()) {
        transition_to(FirmwareState::UPLOAD, "frame captured");
      } else {
        last_error_ = "capture failed";
        transition_to(FirmwareState::ERROR, "capture failed");
      }
      break;

    case FirmwareState::UPLOAD:
      if (upload_frame_for_command()) {
        transition_to(FirmwareState::EXECUTE, "command received");
      } else {
        transition_to(FirmwareState::ERROR, "upload failed");
      }
      break;

    case FirmwareState::EXECUTE:
      if (execute_pending_command()) {
        transition_to(FirmwareState::STOPPED, "pulse complete");
      }
      break;

    case FirmwareState::STOPPED:
      motor_driver_stop();
      command_started_ = false;
      transition_to(FirmwareState::IDLE, "stopped safely");
      break;

    case FirmwareState::ERROR:
      motor_driver_stop();
      camera_capture_release();
      command_started_ = false;
      if (!wifi_client_is_connected()) {
        transition_to(FirmwareState::WIFI_CONNECTING, "recover wifi");
      } else {
        transition_to(FirmwareState::BACKEND_WAIT, "recover backend");
      }
      break;

    case FirmwareState::ESTOP:
      motor_driver_stop();
      command_started_ = false;
      camera_capture_release();
      if (!failsafe_estop_active()) {
        transition_to(FirmwareState::STOPPED, "estop cleared");
      }
      break;
  }

  ++sequence_;
}

FirmwareState FirmwareStateMachine::state() const { return state_; }

const String& FirmwareStateMachine::last_error() const { return last_error_; }

void FirmwareStateMachine::transition_to(FirmwareState next, const char* reason) {
  if (next == state_) {
    return;
  }
  serial_console_log_state(state_, next, reason);
  state_ = next;
}

bool FirmwareStateMachine::capture_frame() {
  if (!camera_capture_frame(frame_)) {
    return false;
  }

  frame_metadata_.seq = sequence_;
  frame_metadata_.timestamp_ms = millis();
  frame_metadata_.mode = DeviceMode::AUTO;
  frame_metadata_.frame_width = frame_.width;
  frame_metadata_.frame_height = frame_.height;
  frame_metadata_.jpeg_quality = frame_.jpeg_quality;
  return true;
}

bool FirmwareStateMachine::upload_frame_for_command() {
  String upload_error;
  const bool ok =
      http_client_send_frame(frame_, frame_metadata_, pending_command_, upload_error);
  camera_capture_release();

  if (!ok) {
    last_error_ = upload_error;
    serial_console_log_error(last_error_.c_str());
    pending_command_ = MotionCommand{};
    pending_command_.action = DriveAction::STOP;
    return false;
  }
  return true;
}

bool FirmwareStateMachine::execute_pending_command() {
  if (failsafe_command_expired(pending_command_, millis())) {
    last_error_ = "command expired";
    pending_command_ = MotionCommand{};
    pending_command_.action = DriveAction::STOP;
    return true;
  }

  if (!pending_command_.safe_to_execute) {
    pending_command_ = MotionCommand{};
    pending_command_.action = DriveAction::STOP;
    return true;
  }

  if (pending_command_.action == DriveAction::STOP) {
    motor_driver_stop();
    serial_console_log_command(pending_command_);
    command_started_ = false;
    return true;
  }

  if (!command_started_) {
    if (!motor_driver_execute_pulse(pending_command_)) {
      last_error_ = "motor busy overlap";
      serial_console_log_error(last_error_.c_str());
      return false;
    }
    serial_console_log_command(pending_command_);
    command_started_ = true;
  }

  if (!motor_driver_is_busy()) {
    command_started_ = false;
    return true;
  }
  return false;
}
