// Closest Plane Overhead — reTerminal E1001 firmware
// ALL logic on-device: WiFi -> OpenSky (telemetry) -> nearest airborne plane
// -> flash DB / adsbdb (route + type) -> draw the dashboard -> deep sleep.
//
// This file is just the lifecycle (setup/loop) and the one fetch+draw cycle.
// The work lives in the modules:
//   board.h       pin map + feature flags
//   types.h       Plane / Weather / Screen / Airport structs
//   state.*       shared app state (g_plane / g_weather / g_screen)
//   display.*     the e-paper object + init
//   geo.*         distance / bearing / elevation / arrival inference
//   net.*         WiFi + HTTPS-JSON + OpenSky OAuth + fetch diagnostics
//   flightdata.*  flash DB + lookups + OpenSky fetch + adsbdb + weather
//   ui.*          all e-paper drawing (details card / map / gallery / status)
//
// Panel/pin config: see ../HARDWARE.md. User settings: see config.h.

#include <Arduino.h>
#include <WiFi.h>
#include <esp_sleep.h>

#include "board.h"
#include "config.h"
#include "state.h"
#include "display.h"
#include "net.h"
#include "geo.h"
#include "flightdata.h"
#include "ui.h"
#include "gen_plane_art.h"   // PLANE_ART[] / N_PLANE_ART (gallery mode)

// ---- Sleep ------------------------------------------------------------------
static void deepSleepMinutes(uint32_t minutes) {
  display.hibernate();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  esp_sleep_enable_timer_wakeup((uint64_t)minutes * 60ULL * 1000000ULL);
  Serial.printf("[sleep] deep sleep %u min\n", minutes);
  esp_deep_sleep_start();
}

// ---- One full cycle: WiFi -> fetch -> draw ---------------------------------
static void runCycle() {
  g_httpCode = 0; g_numStates = -1; g_parseErr = "";

  g_battPct = batteryPercent();   // works regardless of WiFi; shown on the card

  if (!wifiConnect()) {
    Serial.println("[wifi] failed");
    g_wifiRssi = 0;               // 0 = disconnected -> empty signal glyph
    g_plane.valid = false;
    drawStatus("No WiFi", "check SSID/password in config.h (2.4GHz only)");
    return;
  }
  g_wifiRssi = WiFi.RSSI();       // dBm, for the signal-bar glyph
  Serial.printf("[wifi] connected: %s\n", WiFi.localIP().toString().c_str());

  // NTP for the header clock (non-fatal if it doesn't sync in time).
  configTzTime(TZ_POSIX, "pool.ntp.org", "time.nist.gov");

  Plane p = fetchNearest();
  if (!p.valid) {
    // Distinguish a real empty result from a fetch/parse failure, on-screen,
    // since Serial isn't exposed on this board's USB port.
    char detail[80];
    if (g_httpCode != 200)
      snprintf(detail, sizeof(detail), "OpenSky HTTP %d", g_httpCode);
    else if (g_parseErr.length())
      snprintf(detail, sizeof(detail), "parse error: %s", g_parseErr.c_str());
    else
      snprintf(detail, sizeof(detail), "0 airborne of %d states", g_numStates);
    Serial.printf("[opensky] no plane: %s\n", detail);
    g_plane.valid = false;
    drawStatus("No plane", detail);
    return;
  }
  Serial.printf("[opensky] nearest %s at %.1f km\n", p.callsign.c_str(), p.distKm);

  lookupLocal(p);              // offline: type, model, airline, registration
  lookupRoute(p);              // adsbdb: origin/destination (network)
  if (!p.typeCode.length())    // adsbdb fallback only if the flash DB missed
    lookupType(p);
  // Resolve friendly model + silhouette from whatever typeCode we ended with.
  // (The adsbdb fallback sets typeCode AFTER lookupLocal, so resolve here too.)
  if (p.typeCode.length() && !p.model.length()) {
    const AcType* t = typeInfo(p.typeCode.c_str());
    if (t) { p.model = t->name; p.baseModel = t->base; }
  }

  // Infer the destination for arrivals: a low, descending (or very low) plane
  // near an airport is landing there — more reliable than adsbdb's route data.
  if (p.altFt < 10000 && p.climb <= 0) {
    const Airport* ap = arrivalAirport(p.lat, p.lon, p.headingDeg, 18.0);
    if (ap) {
      p.dest = ap->code; p.destCity = ap->city; p.destInferred = true;
      Serial.printf("[infer] landing at %s\n", ap->code);
    }
  }

  fetchWeather();              // open-meteo: current temp + condition (footer)

  g_plane = p;                 // keep for redraw when switching screens
  drawCurrentScreen();
  Serial.println("[E1001] drew screen");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n[E1001] wake");

  pinMode(BTN_REFRESH, INPUT_PULLUP);
  pinMode(BTN_LEFT,  INPUT_PULLUP);      // top white nav: DETAILS screen
  pinMode(BTN_RIGHT, INPUT_PULLUP);      // top white nav: MAP screen
  pinMode(LED_GREEN, OUTPUT);
  digitalWrite(LED_GREEN, HIGH);        // off (active-low)

  acdbInit();                           // mount the on-flash aircraft DB
  displayInit();                        // bring up HSPI + the panel

#if GALLERY_MODE
  drawGallery(1);            // show the first image; loop() advances on button
  return;
#endif

  runCycle();

#if !DEBUG_STAY_AWAKE
  deepSleepMinutes(REFRESH_MINUTES);   // production: sleep for battery
#endif
}

void loop() {
#if GALLERY_MODE
  static uint8_t idx = 1;

  // Step to the next non-empty art slot in direction `dir` (+1 next, -1 prev),
  // wrapping around 1..N_PLANE_ART-1.
  auto step = [](uint8_t from, int dir) -> uint8_t {
    int i = from;
    for (int n = 0; n < N_PLANE_ART; n++) {
      i += dir;
      if (i < 1) i = N_PLANE_ART - 1;
      else if (i > N_PLANE_ART - 1) i = 1;
      if (PLANE_ART[i].bits) return (uint8_t)i;
    }
    return from;                              // no other non-empty slot
  };

  bool green = (digitalRead(BTN_REFRESH) == LOW);   // green center -> next
  bool prev  = (digitalRead(BTN_LEFT)  == LOW);     // left white   -> previous
  bool next  = (digitalRead(BTN_RIGHT) == LOW);     // right white  -> next
  digitalWrite(LED_GREEN, (green || prev || next) ? LOW : HIGH);

  if (green || next || prev) {
    delay(30);                                       // debounce
    idx = step(idx, prev ? -1 : +1);
    Serial.printf("[gallery] show %u\n", idx);
    drawGallery(idx);
    // Wait for all nav buttons to release so one press = one flip.
    while (digitalRead(BTN_REFRESH) == LOW ||
           digitalRead(BTN_LEFT)  == LOW ||
           digitalRead(BTN_RIGHT) == LOW) delay(10);
  }
  delay(20);
#elif DEBUG_STAY_AWAKE
  static uint32_t lastRefresh = millis();
  const uint32_t AUTO_MS = 60000;      // also auto-refresh every 60s

  // Instant feedback: LED on whenever the button reads pressed. If this lights
  // when you press, GPIO3 is being read fine and any lag is just the e-paper.
  bool pressed = (digitalRead(BTN_REFRESH) == LOW);
  digitalWrite(LED_GREEN, pressed ? LOW : HIGH);

  // Green button pressed -> refresh now (debounced).
  if (pressed) {
    delay(30);
    if (digitalRead(BTN_REFRESH) == LOW) {
      Serial.println("[btn] manual refresh");
      runCycle();
      lastRefresh = millis();
      while (digitalRead(BTN_REFRESH) == LOW) delay(10);   // wait for release
    }
  }

  // Top white nav buttons switch screens (redraw only, no re-fetch). Left =
  // DETAILS, right = MAP. Only meaningful once we have a plane to show.
  bool navL = (digitalRead(BTN_LEFT)  == LOW);
  bool navR = (digitalRead(BTN_RIGHT) == LOW);
  if ((navL || navR) && g_plane.valid) {
    delay(30);
    Screen want = navR ? SCREEN_MAP : SCREEN_DETAILS;
    if (want != g_screen) {
      g_screen = want;
      Serial.printf("[btn] switch to %s screen\n", navR ? "MAP" : "DETAILS");
      drawCurrentScreen();
    }
    while (digitalRead(BTN_LEFT) == LOW || digitalRead(BTN_RIGHT) == LOW)
      delay(10);                                           // wait for release
  }

  if (millis() - lastRefresh >= AUTO_MS) {
    runCycle();
    lastRefresh = millis();
  }
  delay(20);
#endif
}
