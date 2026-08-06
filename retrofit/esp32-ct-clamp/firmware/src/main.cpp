// OMP esp32-ct-clamp firmware v0.1.0
//
// STATUS: DRAFT - implements the behavior documented in
// docs/docs/guides/retrofit-installation.md. NOT COMPILED, NOT RUN, NOT
// TESTED ON HARDWARE by its author (no ESP32 toolchain was available).
// The ADC calibration path (BURDEN_* constants and rms_amps()) needs bench
// verification against a reference meter before any deployment. Treat every
// number it produces as unvalidated until then.
//
// Behavior:
//  - First boot (or held BOOT button): provisioning AP "omp-setup-XXXX",
//    form at 192.168.4.1 -> WiFi, gateway broker, machine_id, CT rating,
//    mains voltage/phases, load threshold. Stored in NVS.
//  - Runtime: RMS current sampling -> watts -> Wh accumulation; emits node
//    JSON over MQTT to omp-node/{node_id}: "hello" on connect, "energy"
//    intervals (integral Wh), "start"/"stop" on load-threshold crossings.
//  - Buffers up to RING_CAPACITY unsent messages (~10 min at the default
//    interval) and replays on reconnect; drops oldest and counts drops.
//
// The gateway's retrofit-esp32 adapter (adapters/retrofit-esp32/) consumes
// these node messages and wraps them into OMP envelopes - the node itself
// never builds envelopes, assigns seq, or signs.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <WiFi.h>

static const char *FIRMWARE_VERSION = "0.1.0";

// ---- hardware constants (bench-verify before trusting) -------------------
static const int CT_ADC_PIN = 34;          // ADC1_CH6, input-only
static const float ADC_VREF = 3.3f;
static const int ADC_MAX = 4095;
static const float BURDEN_MIDPOINT = ADC_MAX / 2.0f;  // bias divider at Vcc/2
static const int RMS_SAMPLES = 1480;       // ~2 mains cycles at 50 Hz
static const uint32_t SAMPLE_PERIOD_MS = 1000;
static const uint32_t ENERGY_INTERVAL_S = 60;
static const size_t RING_CAPACITY = 64;    // ~10 min of messages

// ---- configuration (NVS) --------------------------------------------------
struct Config {
  String wifi_ssid, wifi_pass, broker_host, machine_id;
  int broker_port = 1883;
  float ct_rating_a = 30.0f;   // SCT-013 xxA/1V
  float mains_v = 230.0f;
  int phases = 1;
  float load_threshold_w = 50.0f;
  bool provisioned = false;
};

Preferences prefs;
Config cfg;
String node_id;

void loadConfig() {
  prefs.begin("omp", true);
  cfg.provisioned = prefs.getBool("prov", false);
  cfg.wifi_ssid = prefs.getString("ssid", "");
  cfg.wifi_pass = prefs.getString("pass", "");
  cfg.broker_host = prefs.getString("broker", "");
  cfg.broker_port = prefs.getInt("bport", 1883);
  cfg.machine_id = prefs.getString("mid", "");
  cfg.ct_rating_a = prefs.getFloat("ct_a", 30.0f);
  cfg.mains_v = prefs.getFloat("mv", 230.0f);
  cfg.phases = prefs.getInt("ph", 1);
  cfg.load_threshold_w = prefs.getFloat("thr", 50.0f);
  prefs.end();
}

void saveConfig() {
  prefs.begin("omp", false);
  prefs.putBool("prov", true);
  prefs.putString("ssid", cfg.wifi_ssid);
  prefs.putString("pass", cfg.wifi_pass);
  prefs.putString("broker", cfg.broker_host);
  prefs.putInt("bport", cfg.broker_port);
  prefs.putString("mid", cfg.machine_id);
  prefs.putFloat("ct_a", cfg.ct_rating_a);
  prefs.putFloat("mv", cfg.mains_v);
  prefs.putInt("ph", cfg.phases);
  prefs.putFloat("thr", cfg.load_threshold_w);
  prefs.end();
}

// ---- provisioning portal ---------------------------------------------------
WebServer portal(80);

static const char FORM[] PROGMEM = R"html(
<!doctype html><title>OMP node setup</title>
<h2>OMP retrofit node</h2>
<form method=post action=/save>
WiFi SSID (2.4GHz): <input name=ssid><br>
WiFi password: <input name=pass type=password><br>
Gateway broker IP: <input name=broker><br>
machine_id: <input name=mid placeholder=f1-line1-m03><br>
CT rating (A): <input name=ct_a value=30><br>
Mains voltage: <input name=mv value=230><br>
Phases: <input name=ph value=1><br>
Load threshold (W): <input name=thr value=50><br>
<button>Save & reboot</button></form>
)html";

void runProvisioningPortal() {
  String ap = "omp-setup-" + node_id.substring(node_id.length() - 4);
  WiFi.softAP(ap.c_str());
  portal.on("/", []() { portal.send(200, "text/html", FORM); });
  portal.on("/save", HTTP_POST, []() {
    cfg.wifi_ssid = portal.arg("ssid");
    cfg.wifi_pass = portal.arg("pass");
    cfg.broker_host = portal.arg("broker");
    cfg.machine_id = portal.arg("mid");
    cfg.ct_rating_a = portal.arg("ct_a").toFloat();
    cfg.mains_v = portal.arg("mv").toFloat();
    cfg.phases = portal.arg("ph").toInt();
    cfg.load_threshold_w = portal.arg("thr").toFloat();
    saveConfig();
    portal.send(200, "text/html",
                "<h2>Saved. Node id: " + node_id + "</h2>Rebooting.");
    delay(1500);
    ESP.restart();
  });
  portal.begin();
  Serial.printf("provisioning AP %s, browse http://192.168.4.1\n", ap.c_str());
  for (;;) portal.handleClient();
}

// ---- sensing ---------------------------------------------------------------
float rms_amps() {
  // BENCH-VERIFY: assumes 1V-output SCT-013 into a Vcc/2-biased divider.
  double sum_sq = 0;
  for (int i = 0; i < RMS_SAMPLES; i++) {
    float centered = analogRead(CT_ADC_PIN) - BURDEN_MIDPOINT;
    sum_sq += centered * centered;
    delayMicroseconds(25);
  }
  float rms_counts = sqrt(sum_sq / RMS_SAMPLES);
  float rms_volts = rms_counts / ADC_MAX * ADC_VREF;
  return rms_volts * cfg.ct_rating_a;  // xxA per 1V CT
}

// ---- node message ring buffer ---------------------------------------------
String ring[RING_CAPACITY];
size_t ring_head = 0, ring_count = 0;
uint32_t dropped = 0;

void ringPush(const String &msg) {
  if (ring_count == RING_CAPACITY) {
    ring_head = (ring_head + 1) % RING_CAPACITY;  // drop oldest
    ring_count--;
    dropped++;
  }
  ring[(ring_head + ring_count) % RING_CAPACITY] = msg;
  ring_count++;
}

// ---- MQTT ------------------------------------------------------------------
WiFiClient wifi_client;
PubSubClient mqtt(wifi_client);
String topic;

bool mqttEnsure() {
  if (mqtt.connected()) return true;
  if (WiFi.status() != WL_CONNECTED) return false;
  if (!mqtt.connect(node_id.c_str())) return false;
  // hello announcement, then drain the buffer oldest-first
  JsonDocument doc;
  doc["type"] = "hello";
  doc["node_id"] = node_id;
  doc["machine_id"] = cfg.machine_id;
  doc["kit"] = "ct_clamp";
  doc["fw"] = FIRMWARE_VERSION;
  doc["dropped_while_offline"] = dropped;
  String out;
  serializeJson(doc, out);
  mqtt.publish(topic.c_str(), out.c_str());
  while (ring_count && mqtt.connected()) {
    if (!mqtt.publish(topic.c_str(), ring[ring_head].c_str())) break;
    ring_head = (ring_head + 1) % RING_CAPACITY;
    ring_count--;
  }
  return mqtt.connected();
}

void emitOrBuffer(JsonDocument &doc) {
  String out;
  serializeJson(doc, out);
  if (!(mqttEnsure() && mqtt.publish(topic.c_str(), out.c_str()))) {
    ringPush(out);
  }
}

// ---- main ------------------------------------------------------------------
double interval_wh_accum = 0;
uint32_t interval_start_ms = 0;
bool running = false;

void setup() {
  Serial.begin(115200);
  uint64_t mac = ESP.getEfuseMac();
  char idbuf[20];
  snprintf(idbuf, sizeof(idbuf), "omp-node-%04x", (uint16_t)(mac & 0xFFFF));
  node_id = idbuf;
  loadConfig();
  pinMode(0, INPUT_PULLUP);  // BOOT held at power-up -> reprovision
  if (!cfg.provisioned || digitalRead(0) == LOW) runProvisioningPortal();
  WiFi.mode(WIFI_STA);
  WiFi.begin(cfg.wifi_ssid.c_str(), cfg.wifi_pass.c_str());
  mqtt.setServer(cfg.broker_host.c_str(), cfg.broker_port);
  topic = "omp-node/" + node_id;
  analogReadResolution(12);
  interval_start_ms = millis();
}

void loop() {
  float amps = rms_amps();
  float watts = amps * cfg.mains_v * cfg.phases;
  interval_wh_accum += watts * SAMPLE_PERIOD_MS / 3600000.0;

  bool now_running = watts >= cfg.load_threshold_w;
  if (now_running != running) {
    running = now_running;
    JsonDocument doc;
    doc["type"] = "event";
    doc["node_id"] = node_id;
    doc["machine_id"] = cfg.machine_id;
    doc["event"] = running ? "start" : "stop";
    doc["uptime_ms"] = millis();
    emitOrBuffer(doc);
  }

  if (millis() - interval_start_ms >= ENERGY_INTERVAL_S * 1000) {
    JsonDocument doc;
    doc["type"] = "energy";
    doc["node_id"] = node_id;
    doc["machine_id"] = cfg.machine_id;
    doc["wh"] = (long)lround(interval_wh_accum);  // integral Wh by design
    doc["interval_s"] = (millis() - interval_start_ms) / 1000;
    doc["uptime_ms"] = millis();
    emitOrBuffer(doc);
    interval_wh_accum = 0;
    interval_start_ms = millis();
  }

  mqtt.loop();
  delay(SAMPLE_PERIOD_MS);
}
