#include <Arduino.h>

#include "config.h"
#include "failsafe.h"
#include "motor_driver.h"
#include "serial_console.h"
#include "state_machine.h"

namespace {
FirmwareStateMachine g_state_machine;
}

void setup() {
  serial_console_init();
  motor_driver_init();
  failsafe_init();
  serial_console_log_error("firmware boot complete");
}

void loop() {
  failsafe_update_inputs();
  failsafe_kick();
  g_state_machine.step();
  motor_driver_update();
  delay(fwconfig::LOOP_DELAY_MS);
}
