// ============================================================
// FROSTGUARD — Smart Freezer Door Monitoring (ESP32 + A3144)
// Zero external libraries: WiFi/HTTPClient are in the ESP32 core.
// All timing is millis() based — no delay() in the main loop.
// ============================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <stdarg.h>

// ============================================================
// USER SETTINGS — edit this section only, then Upload
// ============================================================

// ---------- Wi-Fi ----------
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// ---------- Backend server (your PC's LAN IP, NOT localhost) ----------
// Find it with:  cmd -> ipconfig  ->  IPv4 Address, e.g. 192.168.1.15
#define SERVER_IP        "192.168.1.15"
#define SERVER_TCP_PORT  8081     // live NDJSON stream (fast path)
#define SERVER_HTTP_PORT 8000     // config pull + HTTP fallback

// ---------- Device identity ----------
#define DEVICE_ID        "esp32-freezer-01"
#define FIRMWARE_VERSION "1.0.0"

// ---------- Pins (ESP32-safe 3.3V only) ----------
// A3144 module:  + -> 3V3   - -> GND   S -> SENSOR_PIN
#define SENSOR_PIN       13
// Most A3144 modules are ACTIVE-LOW (magnet near = LOW = door CLOSED).
// Boot log prints the raw pin — set false if yours reads HIGH when near.
#define SENSOR_ACTIVE_LOW true

// Buzzer: set true and the GPIO if you wire one later (e.g. 14)
#define BUZZER_ENABLED   false
#define BUZZER_PIN       -1

// ---------- Behavior ----------
#define WARNING_THRESHOLD_S   30   // fallback until backend config is pulled (5..1800)
#define DEBOUNCE_MS           50   // sensor must be stable this long
#define STATUS_INTERVAL_MS    1000 // status line every 1s while connected
#define CONFIG_POLL_MS        10000// pull threshold from backend every 10s
#define TCP_RECONNECT_MS      5000 // retry TCP connect every 5s
#define HTTP_FALLBACK_MS      15000// use HTTP for events if TCP down this long
#define HEARTBEAT_HTTP_MS     5000 // HTTP heartbeat while TCP is down
#define SERIAL_BAUD           115200
// ============================================================

#if BUZZER_ENABLED && (BUZZER_PIN >= 0)
  #define BUZZER_ACTIVE true
#else
  #define BUZZER_ACTIVE false
#endif

// ---------------- state ----------------
bool fieldPresent = false;   // debounced: magnet near sensor
bool doorClosed = true;      // doorClosed == fieldPresent (with polarity applied)
bool rawLastRead = false;
unsigned long debounceAt = 0;
unsigned long openStartMs = 0;
bool overdue = false;
bool alarmActive = false;

unsigned long thresholdMs = (unsigned long)WARNING_THRESHOLD_S * 1000UL;
int appliedConfigVersion = 0;
bool systemEnabled = true;

// Wi-Fi / link state
unsigned long lastWifiAttempt = 0;
unsigned long lastTcpAttempt = 0;
unsigned long tcpUpSince = 0; // last moment TCP was up (or boot)
unsigned long lastHttpHeartbeat = 0;
unsigned long lastConfigPoll = 0;
unsigned long lastStatusSend = 0;
bool wifiWasConnected = false;
bool tcpWasConnected = false;

WiFiClient tcp;
HTTPClient http;

// ---------------- pending events ring (survives TCP outages) ----------------
struct PendingEvent {
  bool used;
  bool sentTcp;
  bool sentHttp;
  unsigned long createdAt;
  char eventId[64];
  char type[16];
  float openSeconds;
  bool doorIsOpen;
};
#define QUEUE_SIZE 8
PendingEvent queue[QUEUE_SIZE];
unsigned long eventCounter = 0;

// ---------------- helpers ----------------
void logf(const char* fmt, ...) {
  char buf[192];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  Serial.println(buf);
}

int jsonInt(const String& body, const char* key, int def) {
  int i = body.indexOf(key);
  if (i < 0) return def;
  i = body.indexOf(':', i);
  if (i < 0) return def;
  return body.substring(i + 1).toInt();
}

bool jsonBool(const String& body, const char* key, bool def) {
  int i = body.indexOf(key);
  if (i < 0) return def;
  i = body.indexOf(':', i);
  if (i < 0) return def;
  String v = body.substring(i + 1, i + 16);
  v.trim();
  if (v.startsWith("true")) return true;
  if (v.startsWith("false")) return false;
  return v.toInt() != 0;
}

float openSecondsNow() {
  if (!doorClosed && openStartMs > 0) return (millis() - openStartMs) / 1000.0f;
  return 0.0f;
}

// ---------------- events ----------------
void queueEvent(const char* type, float openSecs) {
  for (int i = 0; i < QUEUE_SIZE; i++) {
    if (!queue[i].used) {
      queue[i].used = true;
      queue[i].sentTcp = false;
      queue[i].sentHttp = false;
      queue[i].createdAt = millis();
      snprintf(queue[i].eventId, sizeof(queue[i].eventId), "%s-%08x",
               DEVICE_ID, (unsigned int)esp_random());
      strncpy(queue[i].type, type, sizeof(queue[i].type) - 1);
      queue[i].type[sizeof(queue[i].type) - 1] = '\0';
      queue[i].openSeconds = openSecs;
      queue[i].doorIsOpen = !doorClosed;
      eventCounter++;
      logf("[EVENT] %s (openS=%.1f) -> queued (#%lu)", type, openSecs, eventCounter);
      return;
    }
  }
  logf("[EVENT] %s -> QUEUE FULL, dropped", type);
}

String eventJson(const PendingEvent& e) {
  String s = "{\"type\":\"event\",\"event_id\":\"" + String(e.eventId) +
             "\",\"device_id\":\"" + DEVICE_ID +
             "\",\"event_type\":\"" + e.type +
             "\",\"door_state\":\"" + (e.doorIsOpen ? "OPEN" : "CLOSED") +
             "\",\"door_open_seconds\":" + String(e.openSeconds, 1) + "}";
  return s;
}

String statusJson() {
  char buf[448];
  snprintf(buf, sizeof(buf),
           "{\"type\":\"status\",\"device_id\":\"%s\",\"door_state\":\"%s\","
           "\"door_open_seconds\":%.1f,\"alarm_active\":%s,"
           "\"wifi_rssi\":%d,\"uptime_seconds\":%.1f,"
           "\"firmware_version\":\"%s\",\"config_version\":%d,"
           "\"system_enabled\":%s}",
           DEVICE_ID, doorClosed ? "CLOSED" : "OPEN",
           openSecondsNow(), alarmActive ? "true" : "false",
           (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : 0,
           millis() / 1000.0, FIRMWARE_VERSION, appliedConfigVersion,
           systemEnabled ? "true" : "false");
  return String(buf);
}

// ---------------- door state machine ----------------
void onDoorChanged(bool nowClosed, float durSecs) {
  if (nowClosed) {
    logf("[DOOR] CLOSED after %.1fs (overdue was: %s)", durSecs, overdue ? "YES" : "no");
    queueEvent("DOOR_CLOSED", durSecs);
    if (overdue) queueEvent("RECOVERY", durSecs);
    openStartMs = 0;
    overdue = false;
    alarmActive = false;   // re-arm only happens on close (documented rule)
  } else {
    openStartMs = millis();
    logf("[DOOR] OPEN (threshold %lus, system %s)", thresholdMs / 1000,
         systemEnabled ? "ON" : "OFF");
    queueEvent("DOOR_OPEN", 0.0f);
  }
}

void serviceSensor() {
  bool rawField = SENSOR_ACTIVE_LOW ? (digitalRead(SENSOR_PIN) == LOW)
                                    : (digitalRead(SENSOR_PIN) == HIGH);
  if (rawField != rawLastRead) {
    rawLastRead = rawField;
    debounceAt = millis();
    return; // wait for stability
  }
  if (rawField != fieldPresent && (millis() - debounceAt) >= DEBOUNCE_MS) {
    fieldPresent = rawField;
    bool nowClosed = fieldPresent;
    if (nowClosed != doorClosed) {
      float durSecs = doorClosed ? 0.0f : openSecondsNow(); // capture BEFORE flip
      doorClosed = nowClosed;
      onDoorChanged(nowClosed, durSecs);
    }
  }
}

void serviceAlarm() {
  if (!systemEnabled) return; // master OFF: no overdue, no buzzer
  if (!doorClosed && (millis() - openStartMs) >= thresholdMs) {
    if (!overdue) {
      overdue = true;
      alarmActive = true;
      logf("[ALARM] DOOR OPEN > %lus -> OVERDUE", thresholdMs / 1000);
      queueEvent("OVERDUE", openSecondsNow());
    }
  }
}

void serviceBuzzer() {
#if BUZZER_ACTIVE
  if (alarmActive) {
    // beeping pattern 250ms on / 750ms off — never a continuous tone
    digitalWrite(BUZZER_PIN, ((millis() % 1000) < 250) ? HIGH : LOW);
  } else {
    digitalWrite(BUZZER_PIN, LOW);
  }
#endif
}

// ---------------- network ----------------
void wifiLoop() {
  bool connected = (WiFi.status() == WL_CONNECTED);
  if (connected != wifiWasConnected) {
    wifiWasConnected = connected;
    logf("[WIFI] %s (rssi %d)", connected ? "CONNECTED" : "LOST",
         connected ? WiFi.RSSI() : 0);
  }
  if (!connected && (millis() - lastWifiAttempt >= TCP_RECONNECT_MS)) {
    lastWifiAttempt = millis();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

void tcpLoop() {
  bool connected = tcp.connected();
  if (connected != tcpWasConnected) {
    tcpWasConnected = connected;
    logf("[TCP] %s %s:%d", connected ? "CONNECTED" : "DISCONNECTED",
         SERVER_IP, SERVER_TCP_PORT);
  }
  if (!connected && WiFi.status() == WL_CONNECTED &&
      (millis() - lastTcpAttempt >= TCP_RECONNECT_MS)) {
    lastTcpAttempt = millis();
    tcp.stop();
    if (tcp.connect(SERVER_IP, SERVER_TCP_PORT)) {
      tcp.setNoDelay(true);
      tcpWasConnected = true;
      logf("[TCP] CONNECTED %s:%d", SERVER_IP, SERVER_TCP_PORT);
    } else {
      logf("[TCP] connect failed, retry in %ds", TCP_RECONNECT_MS / 1000);
    }
  }
}

void sendEvents() {
  bool tcpUp = tcp.connected();
  if (tcpUp) tcpUpSince = millis();
  bool httpOk = !tcpUp && WiFi.status() == WL_CONNECTED &&
                (millis() - tcpUpSince >= HTTP_FALLBACK_MS);
  for (int i = 0; i < QUEUE_SIZE; i++) {
    if (!queue[i].used) continue;
    bool delivered = false;
    if (tcpUp && !queue[i].sentTcp) {
      tcp.print(eventJson(queue[i]));
      tcp.print('\n');
      queue[i].sentTcp = true;
      delivered = true;
      logf("[TCP] sent %s", queue[i].type);
    }
    if (httpOk && !queue[i].sentHttp) {
      http.begin(String("http://") + SERVER_IP + ":" +
                 String(SERVER_HTTP_PORT) + "/api/device/events");
      http.addHeader("Content-Type", "application/json");
      int code = http.POST(eventJson(queue[i]));
      if (code >= 200 && code < 300) {
        queue[i].sentHttp = true;
        delivered = true;
        logf("[HTTP] sent %s (code %d)", queue[i].type, code);
      } else {
        logf("[HTTP] event POST failed (code %d)", code);
      }
      http.end();
    }
    // delivered by any path -> done (server also dedupes by event_id)
    if (delivered && (queue[i].sentTcp || queue[i].sentHttp)) queue[i].used = false;
    // undeliverable for 60s -> drop to avoid stale floods later
    if (millis() - queue[i].createdAt > 60000) {
      if (!queue[i].sentTcp && !queue[i].sentHttp)
        logf("[EVENT] %s dropped (undelivered 60s)", queue[i].type);
      queue[i].used = false;
    }
  }
}

void statusLoop() {
  if (millis() - lastStatusSend < STATUS_INTERVAL_MS) return;
  lastStatusSend = millis();
  if (tcp.connected()) {
    String s = statusJson();
    tcp.print(s);
    tcp.print('\n');
  } else if (WiFi.status() == WL_CONNECTED &&
             millis() - lastHttpHeartbeat >= HEARTBEAT_HTTP_MS) {
    lastHttpHeartbeat = millis();
    http.begin(String("http://") + SERVER_IP + ":" + String(SERVER_HTTP_PORT) +
               "/api/device/heartbeat");
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(statusJson());
    if (code >= 200 && code < 300) logf("[HTTP] heartbeat ok (%d)", code);
    else logf("[HTTP] heartbeat failed (%d)", code);
    http.end();
  }
}

void configLoop() {
  if (millis() - lastConfigPoll < CONFIG_POLL_MS) return;
  if (WiFi.status() != WL_CONNECTED) return;
  lastConfigPoll = millis();
  http.begin(String("http://") + SERVER_IP + ":" + String(SERVER_HTTP_PORT) +
             "/api/device/config");
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();
    int newThreshold = jsonInt(body, "warning_threshold_seconds", -1);
    int newVersion = jsonInt(body, "config_version", -1);
    bool newSys = jsonBool(body, "system_enabled", systemEnabled);
    if (newThreshold >= 5 && newThreshold <= 1800) {
      unsigned long ms = (unsigned long)newThreshold * 1000UL;
      if (ms != thresholdMs || newVersion > appliedConfigVersion) {
        thresholdMs = ms;
        if (newSys != systemEnabled) {
          if (systemEnabled && !newSys) {
            alarmActive = false;
            overdue = false;
            logf("[CONFIG] system OFF -> alarm cleared");
          }
          systemEnabled = newSys;
        }
        appliedConfigVersion = newVersion;
        logf("[CONFIG] applied threshold=%ds system=%s version=%d",
             newThreshold, systemEnabled ? "ON" : "OFF", newVersion);
      }
    }
  } else {
    logf("[CONFIG] pull failed (%d)", code);
  }
  http.end();
}

// ---------------- setup / loop ----------------
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  pinMode(SENSOR_PIN, INPUT);
#if BUZZER_ACTIVE
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
#endif
  Serial.println();
  Serial.println("========================================");
  Serial.println(" FROSTGUARD firmware " FIRMWARE_VERSION);
  Serial.println("========================================");
  logf("Sensor pin GPIO%d raw=%s (expect %s when magnet near)",
       SENSOR_PIN, digitalRead(SENSOR_PIN) ? "HIGH" : "LOW",
       SENSOR_ACTIVE_LOW ? "LOW" : "HIGH");

  // initial door state from first stable read
  bool rawField = SENSOR_ACTIVE_LOW ? (digitalRead(SENSOR_PIN) == LOW)
                                    : (digitalRead(SENSOR_PIN) == HIGH);
  fieldPresent = rawField;
  rawLastRead = rawField;
  debounceAt = millis();
  doorClosed = fieldPresent;
  openStartMs = doorClosed ? 0 : millis();
  logf("Initial state: %s", doorClosed ? "CLOSED" : "OPEN");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiAttempt = millis();
  logf("Wi-Fi joining '%s' ...", WIFI_SSID);
}

void loop() {
  wifiLoop();
  tcpLoop();
  serviceSensor();
  serviceAlarm();
  serviceBuzzer();
  sendEvents();
  statusLoop();
  configLoop();
}
