#pragma once

#include "types.h"

void failsafe_init();
void failsafe_kick();
bool failsafe_watchdog_expired();
void failsafe_set_estop(bool active);
bool failsafe_estop_active();
bool failsafe_command_expired(const MotionCommand& command, uint32_t now_ms);
