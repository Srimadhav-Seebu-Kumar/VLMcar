#pragma once

#include "types.h"

class FirmwareStateMachine {
 public:
  FirmwareStateMachine();

  void step();
  FirmwareState state() const;

 private:
  void transition_to(FirmwareState next, const char* reason);

  FirmwareState state_;
  uint32_t sequence_;
};
