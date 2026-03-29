#pragma once

#include <Arduino.h>

enum class DeviceMode : uint8_t {
  AUTO,
  MANUAL,
  ESTOP,
  IDLE,
};

enum class FirmwareState : uint8_t {
  BOOTING,
  WIFI_CONNECTING,
  BACKEND_WAIT,
  IDLE,
  ACK_READY,
  CAPTURE,
  UPLOAD,
  EXECUTE,
  STOPPED,
  ERROR,
  ESTOP,
};

struct FrameBuffer {
  const uint8_t* data = nullptr;
  size_t len = 0;
  uint16_t width = 0;
  uint16_t height = 0;
  uint8_t jpeg_quality = 0;
};

struct FrameMetadata {
  uint32_t seq = 0;
  uint64_t timestamp_ms = 0;
  DeviceMode mode = DeviceMode::AUTO;
  uint16_t frame_width = 0;
  uint16_t frame_height = 0;
  uint8_t jpeg_quality = 0;
};

struct MotionCommand {
  int8_t heading_deg = 0;       // -90 (full left) to +90 (full right), 0 = straight
  float throttle = 0.0f;        // 0.0 (stop) to 1.0 (full speed)
  uint8_t left_pwm = 0;
  uint8_t right_pwm = 0;
  uint16_t duration_ms = 0;
  float confidence = 0.0f;
  String reason_code = "SAFE_DEFAULT";
  bool safe_to_execute = true;
  String trace_id;
  String session_id;
  uint32_t issued_at_ms = 0;
  uint32_t lease_ms = 0;
};

struct AckReadyResponse {
  bool request_frame = false;
  String session_id;
};

struct TelemetrySnapshot {
  uint32_t uptime_ms = 0;
  int32_t wifi_rssi_dbm = -127;
  uint16_t battery_mv = 0;
  uint32_t frame_counter = 0;
  float avg_loop_latency_ms = 0.0f;
  String last_error;
};
