#pragma once

#include "types.h"

void serial_console_init();
void serial_console_log_state(FirmwareState from, FirmwareState to, const char* reason);
void serial_console_log_error(const char* message);
void serial_console_log_command(const MotionCommand& command);
