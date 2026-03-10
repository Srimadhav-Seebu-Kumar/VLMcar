#pragma once

#include "types.h"

void motor_driver_init();
void motor_driver_stop();

void motor_driver_forward(uint8_t left_pwm, uint8_t right_pwm);
void motor_driver_left(uint8_t left_pwm, uint8_t right_pwm);
void motor_driver_right(uint8_t left_pwm, uint8_t right_pwm);

bool motor_driver_execute_pulse(const MotionCommand& command);
bool motor_driver_is_busy();
void motor_driver_update();
