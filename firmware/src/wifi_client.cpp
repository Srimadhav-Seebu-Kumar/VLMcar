#include "wifi_client.h"

#include <WiFi.h>

#include "config.h"

namespace {
uint32_t g_last_connect_attempt_ms = 0;
inline constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 2000;
}

bool wifi_client_connect() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  const uint32_t now = millis();
  if ((now - g_last_connect_attempt_ms) < WIFI_RETRY_INTERVAL_MS) {
    return false;
  }
  g_last_connect_attempt_ms = now;

  WiFi.mode(WIFI_STA);
  WiFi.begin(fwconfig::WIFI_SSID, fwconfig::WIFI_PASSWORD);

  const uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - started) < fwconfig::WIFI_CONNECT_TIMEOUT_MS) {
    delay(200);
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[wifi] connected ip=%s\n", WiFi.localIP().toString().c_str());
    return true;
  }

  Serial.println("[wifi] connection timeout");
  return false;
}

bool wifi_client_is_connected() { return WiFi.status() == WL_CONNECTED; }

int32_t wifi_client_rssi_dbm() {
  if (!wifi_client_is_connected()) {
    return -127;
  }
  return WiFi.RSSI();
}
