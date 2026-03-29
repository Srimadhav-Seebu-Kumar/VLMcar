#pragma once

#include "types.h"

bool http_client_health_check();
bool http_client_send_frame(
    const FrameBuffer& frame,
    const FrameMetadata& metadata,
    MotionCommand& out_command,
    String& out_error);
bool http_client_send_ack(
    const String& device_id,
    const String& session_id,
    uint32_t seq,
    AckReadyResponse& out_response,
    String& out_error);
