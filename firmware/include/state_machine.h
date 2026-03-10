#pragma once

#include <Arduino.h>

#include "types.h"

class FirmwareStateMachine {
 public:
  FirmwareStateMachine();

  void step();
  FirmwareState state() const;
  const String& last_error() const;

 private:
  void transition_to(FirmwareState next, const char* reason);
  bool capture_frame();
  bool upload_frame_for_command();
  bool execute_pending_command();

  FirmwareState state_;
  uint32_t sequence_;
  bool command_started_;
  FrameBuffer frame_;
  FrameMetadata frame_metadata_;
  MotionCommand pending_command_;
  String last_error_;
};
