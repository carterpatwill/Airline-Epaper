// Networking layer: WiFi bring-up, a buffered HTTPS-GET-to-JSON helper, and the
// OpenSky OAuth2 token (cached in RTC across deep-sleep). Also owns the fetch
// diagnostics that get shown on-screen (Serial isn't exposed on this board's USB
// port) and the PSRAM allocator for the large OpenSky JSON document.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <esp_heap_caps.h>

// ---- Fetch diagnostics (rendered on-screen when a fetch fails) -------------
extern int    g_httpCode;   // last OpenSky HTTP status
extern int    g_numStates;  // states parsed (-1 = parse never ran)
extern String g_parseErr;   // ArduinoJson error, if any
extern int    g_credits;    // OpenSky X-Rate-Limit-Remaining (-1 = unknown)

// Let ArduinoJson allocate the (large) OpenSky doc in PSRAM.
struct PsRamAllocator : ArduinoJson::Allocator {
  void* allocate(size_t n) override { return heap_caps_malloc(n, MALLOC_CAP_SPIRAM); }
  void  deallocate(void* p) override { heap_caps_free(p); }
  void* reallocate(void* p, size_t n) override {
    return heap_caps_realloc(p, n, MALLOC_CAP_SPIRAM);
  }
};
extern PsRamAllocator psAlloc;

// Connect to the configured WiFi; true on success within timeoutMs.
bool wifiConnect(uint32_t timeoutMs = 20000);

// HTTPS GET whose body is buffered into PSRAM then parsed into `doc` (optionally
// with an ArduinoJson filter). Returns the HTTP status code, or negative on a
// transport/parse error. `bearer`, if set, is sent as an Authorization header.
int httpGetJson(const String& url, JsonDocument& doc,
                JsonDocument* filter = nullptr, uint32_t timeoutMs = 15000,
                const char* bearer = nullptr);

// Fill `out` with a valid OpenSky bearer token (re-auth only when missing/near
// expiry). Returns false when no credentials are configured or auth failed --
// the caller then falls back to anonymous access.
bool getOpenSkyToken(String& out, bool force = false);
