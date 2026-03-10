#include "camera_capture.h"

#include <Arduino.h>
#include <esp_camera.h>

#include "config.h"
#include "pins.h"

namespace {
bool g_camera_ready = false;
camera_fb_t* g_last_fb = nullptr;

framesize_t resolve_frame_size(uint16_t width, uint16_t height) {
  if (width <= 160 && height <= 120) {
    return FRAMESIZE_QQVGA;
  }
  if (width <= 320 && height <= 240) {
    return FRAMESIZE_QVGA;
  }
  return FRAMESIZE_VGA;
}

void log_camera_error(const char* context, esp_err_t error) {
  Serial.printf("[camera] %s failed with error=0x%x\n", context, static_cast<unsigned int>(error));
}
}  // namespace

bool camera_capture_init() {
  if (g_camera_ready) {
    return true;
  }

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = fwpins::CAM_PIN_D0;
  config.pin_d1 = fwpins::CAM_PIN_D1;
  config.pin_d2 = fwpins::CAM_PIN_D2;
  config.pin_d3 = fwpins::CAM_PIN_D3;
  config.pin_d4 = fwpins::CAM_PIN_D4;
  config.pin_d5 = fwpins::CAM_PIN_D5;
  config.pin_d6 = fwpins::CAM_PIN_D6;
  config.pin_d7 = fwpins::CAM_PIN_D7;
  config.pin_xclk = fwpins::CAM_PIN_XCLK;
  config.pin_pclk = fwpins::CAM_PIN_PCLK;
  config.pin_vsync = fwpins::CAM_PIN_VSYNC;
  config.pin_href = fwpins::CAM_PIN_HREF;
  config.pin_sccb_sda = fwpins::CAM_PIN_SIOD;
  config.pin_sccb_scl = fwpins::CAM_PIN_SIOC;
  config.pin_pwdn = fwpins::CAM_PIN_PWDN;
  config.pin_reset = fwpins::CAM_PIN_RESET;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = resolve_frame_size(fwconfig::CAMERA_FRAME_WIDTH, fwconfig::CAMERA_FRAME_HEIGHT);
  config.jpeg_quality = fwconfig::CAMERA_JPEG_QUALITY;
  config.fb_count = 1;
  config.grab_mode = CAMERA_GRAB_LATEST;

  const esp_err_t init_error = esp_camera_init(&config);
  if (init_error != ESP_OK) {
    log_camera_error("init", init_error);
    g_camera_ready = false;
    return false;
  }

  g_camera_ready = true;
  Serial.printf("[camera] init success frame=%ux%u quality=%u\n", fwconfig::CAMERA_FRAME_WIDTH,
                fwconfig::CAMERA_FRAME_HEIGHT, fwconfig::CAMERA_JPEG_QUALITY);
  return true;
}

bool camera_capture_frame(FrameBuffer& out_frame) {
  out_frame = FrameBuffer{};

  if (!g_camera_ready) {
    Serial.println("[camera] capture requested before init");
    return false;
  }

  if (g_last_fb != nullptr) {
    Serial.println("[camera] previous frame not released");
    return false;
  }

  g_last_fb = esp_camera_fb_get();
  if (g_last_fb == nullptr) {
    Serial.println("[camera] capture failed: null framebuffer");
    return false;
  }

  out_frame.data = g_last_fb->buf;
  out_frame.len = g_last_fb->len;
  out_frame.width = g_last_fb->width;
  out_frame.height = g_last_fb->height;
  out_frame.jpeg_quality = fwconfig::CAMERA_JPEG_QUALITY;
  return true;
}

void camera_capture_release() {
  if (g_last_fb != nullptr) {
    esp_camera_fb_return(g_last_fb);
    g_last_fb = nullptr;
  }
}
