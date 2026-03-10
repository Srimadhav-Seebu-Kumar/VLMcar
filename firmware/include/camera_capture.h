#pragma once

#include "types.h"

bool camera_capture_init();
bool camera_capture_frame(FrameBuffer& out_frame);
void camera_capture_release();
