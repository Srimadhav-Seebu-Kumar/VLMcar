#include "command_parser.h"

#include <ArduinoJson.h>

bool command_parser_parse(const String& payload, MotionCommand& out_command, String& out_error) {
  JsonDocument doc;
  const DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    out_error = String("json parse failed: ") + error.c_str();
    return false;
  }

  const char* action = doc["action"] | "STOP";
  if (String(action) == "FORWARD") {
    out_command.action = DriveAction::FORWARD;
  } else if (String(action) == "LEFT") {
    out_command.action = DriveAction::LEFT;
  } else if (String(action) == "RIGHT") {
    out_command.action = DriveAction::RIGHT;
  } else {
    out_command.action = DriveAction::STOP;
  }

  out_command.left_pwm = doc["left_pwm"] | 0;
  out_command.right_pwm = doc["right_pwm"] | 0;
  out_command.duration_ms = doc["duration_ms"] | 0;
  out_command.confidence = doc["confidence"] | 0.0f;
  out_command.reason_code = String(static_cast<const char*>(doc["reason_code"] | "SAFE_DEFAULT"));
  out_command.safe_to_execute = doc["safe_to_execute"] | false;
  out_command.issued_at_ms = millis();
  out_command.lease_ms = doc["duration_ms"] | 0;
  out_error = "";
  return true;
}
