#include "command_parser.h"

#include <ArduinoJson.h>

#include "config.h"
#include "motor_math.h"

namespace {
bool parse_action(const String& action_text, DriveAction& out_action) {
  if (action_text == "FORWARD") {
    out_action = DriveAction::FORWARD;
    return true;
  }
  if (action_text == "LEFT") {
    out_action = DriveAction::LEFT;
    return true;
  }
  if (action_text == "RIGHT") {
    out_action = DriveAction::RIGHT;
    return true;
  }
  if (action_text == "STOP") {
    out_action = DriveAction::STOP;
    return true;
  }
  return false;
}
}  // namespace

bool command_parser_parse(const String& payload, MotionCommand& out_command, String& out_error) {
  JsonDocument doc;
  const DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    out_error = String("json parse failed: ") + error.c_str();
    return false;
  }

  if (!doc["action"].is<const char*>()) {
    out_error = "missing action";
    return false;
  }
  if (!doc["left_pwm"].is<int>() || !doc["right_pwm"].is<int>()) {
    out_error = "missing pwm values";
    return false;
  }
  if (!doc["duration_ms"].is<int>()) {
    out_error = "missing duration_ms";
    return false;
  }
  if (!doc["safe_to_execute"].is<bool>()) {
    out_error = "missing safe_to_execute";
    return false;
  }

  const String action_text = String(static_cast<const char*>(doc["action"]));
  DriveAction action = DriveAction::STOP;
  if (!parse_action(action_text, action)) {
    out_error = "invalid action value";
    return false;
  }

  const int left_pwm_raw = doc["left_pwm"].as<int>();
  const int right_pwm_raw = doc["right_pwm"].as<int>();
  const int duration_raw = doc["duration_ms"].as<int>();
  if (duration_raw < 0) {
    out_error = "duration_ms must be non-negative";
    return false;
  }

  out_command.action = action;
  out_command.left_pwm = motor_clamp_pwm(left_pwm_raw);
  out_command.right_pwm = motor_clamp_pwm(right_pwm_raw);
  out_command.duration_ms = motor_clamp_duration(duration_raw, fwconfig::MAX_PULSE_MS);
  out_command.confidence = doc["confidence"].is<float>() ? doc["confidence"].as<float>() : 0.0f;
  if (doc["reason_code"].is<const char*>()) {
    out_command.reason_code = String(static_cast<const char*>(doc["reason_code"]));
  } else {
    out_command.reason_code = "SAFE_DEFAULT";
  }
  out_command.safe_to_execute = doc["safe_to_execute"].as<bool>();
  out_command.issued_at_ms = millis();
  out_command.lease_ms = fwconfig::COMMAND_LEASE_MS;

  out_error = "";
  return true;
}
