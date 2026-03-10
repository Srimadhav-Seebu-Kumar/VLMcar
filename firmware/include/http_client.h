#pragma once

#include "types.h"

bool http_client_health_check();
bool http_client_send_frame(
    const FrameBuffer& frame,
    const FrameMetadata& metadata,
    MotionCommand& out_command,
    String& out_error);
