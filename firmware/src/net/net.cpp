#include "net.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include "config.h"

// ---- Fetch diagnostics ------------------------------------------------------
int    g_httpCode  = 0;
int    g_numStates = -1;
String g_parseErr  = "";
int    g_credits   = -1;

PsRamAllocator psAlloc;

// ---- OpenSky OAuth2 token cache (survives deep-sleep, NOT power loss) --------
// The bearer token lasts ~30 min; wakes are 1-5 min apart, so one token serves
// several wakes. We cache it in RTC memory and only re-auth when it's near
// expiry (or on cold boot, when RTC is zeroed). Token is ~1466 chars.
static RTC_DATA_ATTR char     rtcToken[1600]   = {0};
static RTC_DATA_ATTR uint32_t rtcTokenExpEpoch = 0;   // unix time token expires
static const uint32_t TOKEN_REFRESH_MARGIN = 60;      // refresh this early (s)

bool wifiConnect(uint32_t timeoutMs) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) delay(200);
  return WiFi.status() == WL_CONNECTED;
}

int httpGetJson(const String& url, JsonDocument& doc, JsonDocument* filter,
                uint32_t timeoutMs, const char* bearer) {
  WiFiClientSecure client;
  client.setInsecure();               // hobby: skip cert validation
  client.setTimeout(timeoutMs / 1000);
  HTTPClient https;
  https.setTimeout(timeoutMs);
  https.useHTTP10(true);              // HTTP/1.0: no chunked encoding
  if (!https.begin(client, url)) { Serial.println("[http] begin failed"); return -1; }
  https.setUserAgent("reterminal-plane/1.0");
  https.addHeader("Accept-Encoding", "identity");   // no gzip
  if (bearer && bearer[0]) https.addHeader("Authorization", String("Bearer ") + bearer);
  // Capture the remaining-credits header (must be requested before GET).
  const char* collect[] = { "X-Rate-Limit-Remaining" };
  https.collectHeaders(collect, 1);
  int code = https.GET();
  g_httpCode = code;
  if (https.hasHeader("X-Rate-Limit-Remaining"))
    g_credits = https.header("X-Rate-Limit-Remaining").toInt();
  Serial.printf("[http] %d  len=%d  heap=%u\n",
                code, https.getSize(), (unsigned)ESP.getFreeHeap());
  if (code != 200) { https.end(); return code; }

  // Read the FULL body into a PSRAM buffer before parsing. Parsing straight
  // from the TLS stream yields IncompleteInput when the stream stalls mid-body;
  // buffering first decouples network timing from the parser.
  int contentLen = https.getSize();                 // Content-Length, or -1
  size_t cap = contentLen > 0 ? (size_t)contentLen + 1 : 16384;
  char* buf = (char*)heap_caps_malloc(cap, MALLOC_CAP_SPIRAM);
  if (!buf) { g_parseErr = "buf alloc"; https.end(); return -3; }

  WiFiClient* stream = https.getStreamPtr();
  size_t n = 0; uint32_t last = millis();
  while (https.connected() || stream->available()) {
    size_t avail = stream->available();
    if (avail) {
      if (n + avail + 1 > cap) {                    // grow (unknown-length case)
        size_t ncap = cap * 2;
        char* nb = (char*)heap_caps_realloc(buf, ncap, MALLOC_CAP_SPIRAM);
        if (!nb) { heap_caps_free(buf); g_parseErr = "buf grow"; https.end(); return -3; }
        buf = nb; cap = ncap;
      }
      n += stream->readBytes(buf + n, avail);
      last = millis();
    } else {
      if (contentLen > 0 && (int)n >= contentLen) break;
      if (millis() - last > timeoutMs) break;
      delay(2);
    }
  }
  buf[n] = 0;
  https.end();
  Serial.printf("[http] read %u bytes\n", (unsigned)n);

  DeserializationError err = filter
    ? deserializeJson(doc, buf, n, DeserializationOption::Filter(*filter))
    : deserializeJson(doc, buf, n);
  heap_caps_free(buf);
  if (err) { g_parseErr = err.c_str();
             Serial.printf("[json] parse error: %s\n", err.c_str());
             return -2; }
  return code;
}

bool getOpenSkyToken(String& out, bool force) {
  if (!OPENSKY_CLIENT_ID[0] || !OPENSKY_CLIENT_SECRET[0]) return false;  // anon mode

  uint32_t now = (uint32_t)time(nullptr);
  bool clockSynced = now > 1600000000UL;    // past ~2020 => NTP has run
  if (!force && rtcToken[0] && clockSynced &&
      now + TOKEN_REFRESH_MARGIN < rtcTokenExpEpoch) {
    out = rtcToken;
    Serial.printf("[auth] cached token, %us left\n",
                  (unsigned)(rtcTokenExpEpoch - now));
    return true;
  }

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient https;
  https.setTimeout(10000);
  if (!https.begin(client,
        "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token")) {
    Serial.println("[auth] begin failed");
    return false;
  }
  https.addHeader("Content-Type", "application/x-www-form-urlencoded");
  String body = String("grant_type=client_credentials&client_id=") +
                OPENSKY_CLIENT_ID + "&client_secret=" + OPENSKY_CLIENT_SECRET;
  int code = https.POST(body);
  if (code != 200) { Serial.printf("[auth] token HTTP %d\n", code); https.end(); return false; }

  String payload = https.getString();       // small body; handles decoding
  https.end();
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) { Serial.printf("[auth] token parse: %s\n", err.c_str()); return false; }

  const char* tok = doc["access_token"] | "";
  uint32_t expiresIn = doc["expires_in"] | 1800;
  if (!tok[0] || strlen(tok) >= sizeof(rtcToken)) {
    Serial.println("[auth] no/oversized token"); return false;
  }
  strncpy(rtcToken, tok, sizeof(rtcToken) - 1);
  rtcToken[sizeof(rtcToken) - 1] = 0;
  // If the clock isn't synced yet, base expiry at 0 so the next wake re-auths
  // (harmless: token fetches cost no credits). The 401-retry path is the real
  // safety net regardless of clock state.
  rtcTokenExpEpoch = (clockSynced ? now : 0) + expiresIn;
  out = rtcToken;
  Serial.printf("[auth] new token, expires_in=%u\n", (unsigned)expiresIn);
  return true;
}
