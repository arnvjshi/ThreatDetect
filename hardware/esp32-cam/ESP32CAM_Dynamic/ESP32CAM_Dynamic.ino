#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <ESPmDNS.h>

// Optional: install WiFiManager if you want an automatic captive portal instead.
// This sketch uses a simple config endpoint so SSID/password can be changed without reflashing.

// =====================
// AI Thinker ESP32-CAM pin map
// =====================
#define AI_PWDN_GPIO_NUM     32
#define AI_RESET_GPIO_NUM     -1
#define AI_XCLK_GPIO_NUM       0
#define AI_SIOD_GPIO_NUM      26
#define AI_SIOC_GPIO_NUM      27

#define AI_Y9_GPIO_NUM        35
#define AI_Y8_GPIO_NUM        34
#define AI_Y7_GPIO_NUM        39
#define AI_Y6_GPIO_NUM        36
#define AI_Y5_GPIO_NUM        21
#define AI_Y4_GPIO_NUM        19
#define AI_Y3_GPIO_NUM        18
#define AI_Y2_GPIO_NUM         5
#define AI_VSYNC_GPIO_NUM     25
#define AI_HREF_GPIO_NUM      23
#define AI_PCLK_GPIO_NUM      22

// OV3660-friendly alternate pin profile (common on M5Stack Wide-like layouts)
#define OV_PWDN_GPIO_NUM      -1
#define OV_RESET_GPIO_NUM      15
#define OV_XCLK_GPIO_NUM       27
#define OV_SIOD_GPIO_NUM       25
#define OV_SIOC_GPIO_NUM       23

#define OV_Y9_GPIO_NUM         19
#define OV_Y8_GPIO_NUM         36
#define OV_Y7_GPIO_NUM         18
#define OV_Y6_GPIO_NUM         39
#define OV_Y5_GPIO_NUM          5
#define OV_Y4_GPIO_NUM         34
#define OV_Y3_GPIO_NUM         35
#define OV_Y2_GPIO_NUM         32
#define OV_VSYNC_GPIO_NUM      22
#define OV_HREF_GPIO_NUM       26
#define OV_PCLK_GPIO_NUM       21

#define FLASH_LED_PIN       4

Preferences preferences;
WebServer server(80);

String wifiSsid;
String wifiPassword;
String deviceName = "threatdetect-cam";
bool cameraReady = false;
String cameraError = "not_initialized";
String cameraProfile = "none";
bool mdnsReady = false;
unsigned long lastMdnsAttempt = 0;

struct CameraPins {
  int pin_pwdn;
  int pin_reset;
  int pin_xclk;
  int pin_sccb_sda;
  int pin_sccb_scl;
  int pin_d7;
  int pin_d6;
  int pin_d5;
  int pin_d4;
  int pin_d3;
  int pin_d2;
  int pin_d1;
  int pin_d0;
  int pin_vsync;
  int pin_href;
  int pin_pclk;
};

const CameraPins PINS_AI_THINKER = {
  AI_PWDN_GPIO_NUM,
  AI_RESET_GPIO_NUM,
  AI_XCLK_GPIO_NUM,
  AI_SIOD_GPIO_NUM,
  AI_SIOC_GPIO_NUM,
  AI_Y9_GPIO_NUM,
  AI_Y8_GPIO_NUM,
  AI_Y7_GPIO_NUM,
  AI_Y6_GPIO_NUM,
  AI_Y5_GPIO_NUM,
  AI_Y4_GPIO_NUM,
  AI_Y3_GPIO_NUM,
  AI_Y2_GPIO_NUM,
  AI_VSYNC_GPIO_NUM,
  AI_HREF_GPIO_NUM,
  AI_PCLK_GPIO_NUM
};

const CameraPins PINS_OV3660_ALT = {
  OV_PWDN_GPIO_NUM,
  OV_RESET_GPIO_NUM,
  OV_XCLK_GPIO_NUM,
  OV_SIOD_GPIO_NUM,
  OV_SIOC_GPIO_NUM,
  OV_Y9_GPIO_NUM,
  OV_Y8_GPIO_NUM,
  OV_Y7_GPIO_NUM,
  OV_Y6_GPIO_NUM,
  OV_Y5_GPIO_NUM,
  OV_Y4_GPIO_NUM,
  OV_Y3_GPIO_NUM,
  OV_Y2_GPIO_NUM,
  OV_VSYNC_GPIO_NUM,
  OV_HREF_GPIO_NUM,
  OV_PCLK_GPIO_NUM
};

static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=frame";
static const char* STREAM_BOUNDARY = "\r\n--frame\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

void saveWifiCredentials(const String& ssid, const String& password) {
  preferences.begin("camera", false);
  preferences.putString("ssid", ssid);
  preferences.putString("password", password);
  preferences.end();
}

void loadWifiCredentials() {
  preferences.begin("camera", true);
  wifiSsid = preferences.getString("ssid", "");
  wifiPassword = preferences.getString("password", "");
  preferences.end();
}

String htmlEscape(const String& value) {
  String escaped = value;
  escaped.replace("&", "&amp;");
  escaped.replace("<", "&lt;");
  escaped.replace(">", "&gt;");
  escaped.replace("\"", "&quot;");
  return escaped;
}

String getBaseUrl() {
  return "http://" + WiFi.localIP().toString();
}

String getHostBaseUrl() {
  return "http://" + deviceName + ".local";
}

void startMdnsIfPossible() {
  if (mdnsReady || WiFi.status() != WL_CONNECTED) {
    return;
  }

  lastMdnsAttempt = millis();
  if (MDNS.begin(deviceName.c_str())) {
    MDNS.addService("http", "tcp", 80);
    mdnsReady = true;
    Serial.print("mDNS started: ");
    Serial.print(deviceName);
    Serial.println(".local");
  } else {
    Serial.println("mDNS start failed");
  }
}

void startSetupAccessPoint() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP("ESP32-CAM-SETUP");
  Serial.println("Setup AP started: ESP32-CAM-SETUP");
  Serial.print("AP IP address: ");
  Serial.println(WiFi.softAPIP());
}

void sendHtml(WebServer& webServer, const String& body) {
  webServer.sendHeader("Access-Control-Allow-Origin", "*");
  webServer.send(200, "text/html", body);
}

void handleRoot() {
  String body;
  body.reserve(1200);
  body += "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'>";
  body += "<style>body{font-family:Arial,sans-serif;margin:20px;background:#0b1220;color:#e5eefc}input,button{padding:10px;border-radius:8px;border:1px solid #334155;width:100%;box-sizing:border-box}form{max-width:420px}button{margin-top:10px;background:#0891b2;color:white;border:none}</style></head><body>";
  body += "<h2>ESP32-CAM Control</h2>";
  body += "<p>IP: " + WiFi.localIP().toString() + "</p>";
  body += "<p>Hostname: <code>" + deviceName + ".local</code></p>";
  body += "<p>Camera: <strong>" + String(cameraReady ? "ready" : "not ready") + "</strong></p>";
  if (!cameraReady) {
    body += "<p>Camera error: <code>" + cameraError + "</code></p>";
  }
  body += "<p>Stream: <a href='" + getBaseUrl() + "/stream' target='_blank'>" + getBaseUrl() + "/stream</a></p>";
  body += "<p>Stream (hostname): <a href='" + getHostBaseUrl() + "/stream' target='_blank'>" + getHostBaseUrl() + "/stream</a></p>";
  body += "<p>Flash endpoint: POST <code>" + getBaseUrl() + "/flash</code></p>";
  body += "<form method='POST' action='/config'>";
  body += "<label>WiFi SSID</label><input name='ssid' value='" + htmlEscape(wifiSsid) + "' />";
  body += "<label style='display:block;margin-top:10px'>WiFi Password</label><input name='password' type='password' value='" + htmlEscape(wifiPassword) + "' />";
  body += "<button type='submit'>Save WiFi Credentials</button></form>";
  body += "<p style='margin-top:16px'>After saving, the device reconnects automatically.</p>";
  body += "</body></html>";
  sendHtml(server, body);
}

void handleStatus() {
  String payload = "{";
  payload += "\"ok\":true,";
  payload += "\"connected\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
  payload += "\"camera_ready\":" + String(cameraReady ? "true" : "false") + ",";
  payload += "\"camera_error\":\"" + cameraError + "\",";
  payload += "\"camera_profile\":\"" + cameraProfile + "\",";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"hostname\":\"" + deviceName + ".local\",";
  payload += "\"stream\":\"" + getBaseUrl() + "/stream\",";
  payload += "\"flash\":\"" + getBaseUrl() + "/flash\"";
  payload += "}";

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", payload);
}

void handleConfig() {
  if (!server.hasArg("ssid")) {
    server.send(400, "text/plain", "Missing ssid");
    return;
  }

  wifiSsid = server.arg("ssid");
  wifiPassword = server.arg("password");
  saveWifiCredentials(wifiSsid, wifiPassword);

  server.send(200, "text/plain", "Saved. Reconnecting...");
  delay(500);
  WiFi.disconnect(true);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
}

void flashTask(void* parameter) {
  int durationMs = *(int*)parameter;
  free(parameter);
  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(durationMs);
  digitalWrite(FLASH_LED_PIN, LOW);
  vTaskDelete(NULL);
}

void handleFlash() {
  int durationMs = 2000;
  if (server.hasArg("duration")) {
    int requestedSeconds = server.arg("duration").toInt();
    if (requestedSeconds > 0) {
      durationMs = requestedSeconds * 1000;
    }
  }

  int* payload = (int*)malloc(sizeof(int));
  if (!payload) {
    server.send(500, "application/json", "{\"ok\":false,\"error\":\"out_of_memory\"}");
    return;
  }

  *payload = durationMs;
  xTaskCreatePinnedToCore(flashTask, "flashTask", 2048, payload, 1, NULL, 1);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", "{\"ok\":true}");
}

void handleSnapshot() {
  if (!cameraReady) {
    server.send(503, "text/plain", "Camera not initialized");
    return;
  }

  camera_fb_t* frame = esp_camera_fb_get();
  if (!frame) {
    server.send(500, "text/plain", "Failed to capture frame");
    return;
  }

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.setContentLength(frame->len);
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  client.write(frame->buf, frame->len);
  esp_camera_fb_return(frame);
}

void handleStream() {
  if (!cameraReady) {
    server.send(503, "text/plain", "Camera not initialized");
    return;
  }

  WiFiClient client = server.client();
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-cache");
  server.send(200, STREAM_CONTENT_TYPE, "");

  while (client.connected()) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      break;
    }

    client.print(STREAM_BOUNDARY);
    client.printf(STREAM_PART, fb->len);
    client.write(fb->buf, fb->len);
    client.print("\r\n");
    esp_camera_fb_return(fb);
    delay(1);
  }
}

esp_err_t initCameraWithConfig(const CameraPins& pins, framesize_t frameSize, int jpegQuality, int frameBufferCount, int xclkFreq) {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = pins.pin_d0;
  config.pin_d1 = pins.pin_d1;
  config.pin_d2 = pins.pin_d2;
  config.pin_d3 = pins.pin_d3;
  config.pin_d4 = pins.pin_d4;
  config.pin_d5 = pins.pin_d5;
  config.pin_d6 = pins.pin_d6;
  config.pin_d7 = pins.pin_d7;
  config.pin_xclk = pins.pin_xclk;
  config.pin_pclk = pins.pin_pclk;
  config.pin_vsync = pins.pin_vsync;
  config.pin_href = pins.pin_href;
  config.pin_sccb_sda = pins.pin_sccb_sda;
  config.pin_sccb_scl = pins.pin_sccb_scl;
  config.pin_pwdn = pins.pin_pwdn;
  config.pin_reset = pins.pin_reset;
  config.xclk_freq_hz = xclkFreq;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = frameSize;
  config.jpeg_quality = jpegQuality;
  config.fb_count = frameBufferCount;

  return esp_camera_init(&config);
}

esp_err_t initCamera() {
  esp_err_t err;

  // Profile 1: AI Thinker style boards (most ESP32-CAM modules).
  if (psramFound()) {
    err = initCameraWithConfig(PINS_AI_THINKER, FRAMESIZE_VGA, 12, 2, 20000000);
  } else {
    err = initCameraWithConfig(PINS_AI_THINKER, FRAMESIZE_VGA, 15, 1, 20000000);
  }

  if (err == ESP_OK) {
    cameraProfile = "ai_thinker";
    return ESP_OK;
  }

  Serial.print("Camera init attempt 1 (ai_thinker) failed: ");
  Serial.println((int)err);
  delay(300);

  // Profile 2: OV3660 alternate pin map with conservative timing.
  err = initCameraWithConfig(PINS_OV3660_ALT, FRAMESIZE_QVGA, 18, 1, 10000000);
  if (err == ESP_OK) {
    cameraProfile = "ov3660_alt";
    Serial.println("Camera init recovered using OV3660 alternate profile.");
    return ESP_OK;
  }

  Serial.print("Camera init attempt 2 (ov3660_alt) failed: ");
  Serial.println((int)err);
  cameraProfile = "none";

  return err;
}

void connectWifi() {
  if (wifiSsid.isEmpty()) {
    Serial.println("No saved WiFi credentials found.");
    Serial.println("Connect to ESP32-CAM-SETUP and open http://192.168.4.1/ to configure WiFi.");
    return;
  }

  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
  Serial.print("Connecting to WiFi");

  unsigned long startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 20000) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    startMdnsIfPossible();
    return;
  }

  Serial.println("WiFi connect failed, starting AP fallback");
  WiFi.disconnect(true);
  startSetupAccessPoint();
}

void setup() {
  Serial.begin(115200);
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  loadWifiCredentials();

  WiFi.setHostname(deviceName.c_str());
  startSetupAccessPoint();

  server.on("/", HTTP_GET, handleRoot);
  server.on("/config", HTTP_POST, handleConfig);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/stream", HTTP_GET, handleStream);
  server.on("/snapshot", HTTP_GET, handleSnapshot);
  server.on("/flash", HTTP_POST, handleFlash);
  server.begin();

  esp_err_t cameraInitResult = initCamera();
  if (cameraInitResult == ESP_OK) {
    cameraReady = true;
    cameraError = "none";
  } else {
    cameraReady = false;
    cameraError = "esp_camera_init_failed_" + String((int)cameraInitResult);
    Serial.print("Camera init failed with code: ");
    Serial.println((int)cameraInitResult);
  }

  connectWifi();

  Serial.println("Server started");
}

void loop() {
  server.handleClient();
  if (WiFi.status() == WL_CONNECTED && !mdnsReady && millis() - lastMdnsAttempt >= 5000) {
    startMdnsIfPossible();
  }
  delay(2);
}