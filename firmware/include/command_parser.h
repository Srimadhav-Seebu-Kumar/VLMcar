#pragma once

#include "types.h"

bool command_parser_parse(const String& payload, MotionCommand& out_command, String& out_error);
