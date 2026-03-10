#pragma once

#include "types.h"

void motor_driver_init();
void motor_driver_stop();
bool motor_driver_execute_pulse(const MotionCommand& command);
bool motor_driver_is_busy();
void motor_driver_update();
