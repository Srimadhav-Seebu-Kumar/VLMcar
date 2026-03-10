#include "http_client.h"

#include <HTTPClient.h>

#include <cstring>
#include <memory>

#include "command_parser.h"
#include "config.h"
#include "wifi_client.h"

namespace {
String mode_to_string(DeviceMode mode) {
  switch (mode) {
    case DeviceMode::AUTO:
      return "AUTO";
    case DeviceMode::MANUAL:
      return "MANUAL";
    case DeviceMode::ESTOP:
      return "ESTOP";
    case DeviceMode::IDLE:
      return "IDLE";
  }
  return "AUTO";
}

void append_form_field(String& out, const char* boundary, const char* name, const String& value) {
  out += "--";
  out += boundary;
  out += "\r\n";
  out += "Content-Disposition: form-data; name=\"";
  out += name;
  out += "\"\r\n\r\n";
  out += value;
  out += "\r\n";
}

void set_safe_stop(MotionCommand& command, const String& reason) {
  command = MotionCommand{};
  command.action = DriveAction::STOP;
  command.reason_code = reason;
  command.safe_to_execute = false;
  command.duration_ms = 0;
  command.left_pwm = 0;
  command.right_pwm = 0;
  command.issued_at_ms = millis();
  command.lease_ms = fwconfig::COMMAND_LEASE_MS;
}
}  // namespace

bool http_client_health_check() {
  if (!wifi_client_is_connected()) {
    return false;
  }

  HTTPClient client;
  const String url = String(fwconfig::BACKEND_BASE_URL) + fwconfig::HEALTH_PATH;
  if (!client.begin(url)) {
    return false;
  }

  client.setTimeout(fwconfig::BACKEND_TIMEOUT_MS);
  const int status = client.GET();
  client.end();
  return status == 200;
}

bool http_client_send_frame(const FrameBuffer& frame, const FrameMetadata& metadata,
                            MotionCommand& out_command, String& out_error) {
  if (!wifi_client_is_connected()) {
    out_error = "wifi disconnected";
    set_safe_stop(out_command, out_error);
    return false;
  }

  if (frame.data == nullptr || frame.len == 0) {
    out_error = "empty frame payload";
    set_safe_stop(out_command, out_error);
    return false;
  }

  const String boundary = "----vlmcarboundary";
  String head;
  append_form_field(head, boundary.c_str(), "device_id", fwconfig::DEVICE_ID);
  append_form_field(head, boundary.c_str(), "seq", String(metadata.seq));
  append_form_field(head, boundary.c_str(), "timestamp_ms", String(metadata.timestamp_ms));
  append_form_field(head, boundary.c_str(), "frame_width", String(metadata.frame_width));
  append_form_field(head, boundary.c_str(), "frame_height", String(metadata.frame_height));
  append_form_field(head, boundary.c_str(), "jpeg_quality", String(metadata.jpeg_quality));
  append_form_field(head, boundary.c_str(), "mode", mode_to_string(metadata.mode));

  head += "--";
  head += boundary;
  head += "\r\n";
  head += "Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n";
  head += "Content-Type: image/jpeg\r\n\r\n";

  String tail;
  tail += "\r\n--";
  tail += boundary;
  tail += "--\r\n";

  const size_t total_size = head.length() + frame.len + tail.length();
  std::unique_ptr<uint8_t[]> body(new uint8_t[total_size]);
  std::memcpy(body.get(), head.c_str(), head.length());
  std::memcpy(body.get() + head.length(), frame.data, frame.len);
  std::memcpy(body.get() + head.length() + frame.len, tail.c_str(), tail.length());

  HTTPClient client;
  const String url = String(fwconfig::BACKEND_BASE_URL) + fwconfig::CONTROL_PATH;
  if (!client.begin(url)) {
    out_error = "http begin failed";
    set_safe_stop(out_command, out_error);
    return false;
  }

  client.setTimeout(fwconfig::BACKEND_TIMEOUT_MS);
  client.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  const int status = client.POST(body.get(), total_size);
  const String response = client.getString();
  client.end();

  if (status != 200) {
    out_error = "backend status=" + String(status) + " body=" + response;
    set_safe_stop(out_command, out_error);
    return false;
  }

  if (!command_parser_parse(response, out_command, out_error)) {
    set_safe_stop(out_command, out_error);
    return false;
  }

  out_command.issued_at_ms = millis();
  out_command.lease_ms = fwconfig::COMMAND_LEASE_MS;
  return true;
}
