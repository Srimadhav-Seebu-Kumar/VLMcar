#include "wifi_client.h"

#include <WiFi.h>

#include "config.h"

bool wifi_client_connect() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(fwconfig::WIFI_SSID, fwconfig::WIFI_PASSWORD);

  const uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - started) < fwconfig::WIFI_CONNECT_TIMEOUT_MS) {
    delay(200);
  }
  return WiFi.status() == WL_CONNECTED;
}

bool wifi_client_is_connected() { return WiFi.status() == WL_CONNECTED; }

int32_t wifi_client_rssi_dbm() { return WiFi.RSSI(); }
