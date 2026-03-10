#include "camera_capture.h"

#include <Arduino.h>

bool camera_capture_init() {
  Serial.println("camera init scaffold");
  return false;
}

bool camera_capture_frame(FrameBuffer& out_frame) {
  out_frame = FrameBuffer{};
  return false;
}

void camera_capture_release() {}
