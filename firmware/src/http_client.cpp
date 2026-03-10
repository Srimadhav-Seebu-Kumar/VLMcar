#include "http_client.h"

#include <HTTPClient.h>

#include "command_parser.h"
#include "config.h"

bool http_client_health_check() {
  HTTPClient client;
  const String url = String(fwconfig::BACKEND_BASE_URL) + fwconfig::HEALTH_PATH;
  if (!client.begin(url)) {
    return false;
  }

  const int status = client.GET();
  client.end();
  return status == 200;
}

bool http_client_send_frame(const FrameBuffer& frame, const FrameMetadata& metadata,
                            MotionCommand& out_command, String& out_error) {
  (void)frame;
  (void)metadata;
  (void)out_command;
  out_error = "multipart upload scaffold pending";
  return false;
}
