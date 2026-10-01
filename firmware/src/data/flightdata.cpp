#include "flightdata.h"
#include <LittleFS.h>
#include "config.h"
#include "net.h"
#include "geo.h"
#include "state.h"
#include "gen_airlines.h"   // AIRLINES : callsign prefix -> airline name

// ---- Unit conversions -------------------------------------------------------
static const float M_TO_FT     = 3.28084f;
static const float MS_TO_KT    = 1.94384f;
static const float MS_TO_FTMIN = 196.850f;

bool     g_acdbOk = false;
uint32_t g_acdbN  = 0;

// ---- On-flash aircraft DB (LittleFS acdb.bin) ------------------------------
void acdbInit() {
  // NOTE: begin() defaults to a partition labelled "spiffs"; ours is "littlefs"
  // (see partitions_e1001.csv), so pass the label explicitly or it won't mount.
  if (LittleFS.begin(false, "/littlefs", 10, "littlefs")) {
    File f = LittleFS.open("/acdb.bin", "r");
    if (f) {
      uint8_t h[16];
      if (f.read(h, 16) == 16 && memcmp(h, "ACDB", 4) == 0) {
        g_acdbN  = h[8] | (h[9] << 8) | (h[10] << 16) | ((uint32_t)h[11] << 24);
        g_acdbOk = true;
        Serial.printf("[acdb] mounted, %u records\n", (unsigned)g_acdbN);
      }
      f.close();
    }
  }
  if (!g_acdbOk) Serial.println("[acdb] not available (run: pio run -t uploadfs)");
}

// Binary-search the sorted icao24 -> typecode + registration table. ~20 seeks
// over 587k records; no network, no rate limit. See tools/build_ac_db.py.
static bool acdbLookup(uint32_t icao, char* tc9, char* reg13) {
  if (!g_acdbOk) return false;
  File f = LittleFS.open("/acdb.bin", "r");
  if (!f) return false;
  const uint32_t HDR = 16, REC = 24;
  int lo = 0, hi = (int)g_acdbN - 1;
  uint8_t rec[REC];
  bool found = false;
  while (lo <= hi) {
    int mid = (lo + hi) / 2;
    f.seek(HDR + (uint32_t)mid * REC, SeekSet);
    if (f.read(rec, REC) != (int)REC) break;
    uint32_t key = rec[0] | (rec[1] << 8) | (rec[2] << 16) | ((uint32_t)rec[3] << 24);
    if (key == icao) {
      memcpy(tc9, rec + 4, 8);   tc9[8]  = 0;
      memcpy(reg13, rec + 12, 12); reg13[12] = 0;
      found = true; break;
    }
    if (key < icao) lo = mid + 1; else hi = mid - 1;
  }
  f.close();
  return found;
}

// typecode -> friendly name + silhouette id (binary search AC_TYPES, sorted).
const AcType* typeInfo(const char* code) {
  int lo = 0, hi = (int)AC_TYPES_N - 1;
  while (lo <= hi) {
    int mid = (lo + hi) / 2, c = strcmp(AC_TYPES[mid].code, code);
    if (c == 0) return &AC_TYPES[mid];
    if (c < 0) lo = mid + 1; else hi = mid - 1;
  }
  return nullptr;
}

// 3-letter callsign prefix -> airline name (binary search AIRLINES, sorted).
static const char* airlineFor(const char* pfx) {
  int lo = 0, hi = (int)AIRLINES_N - 1;
  while (lo <= hi) {
    int mid = (lo + hi) / 2, c = strcmp(AIRLINES[mid].code, pfx);
    if (c == 0) return AIRLINES[mid].name;
    if (c < 0) lo = mid + 1; else hi = mid - 1;
  }
  return nullptr;
}

const AirlineLogo* logoFor(const char* pfx) {
  int lo = 0, hi = (int)AIRLINE_LOGOS_N - 1;
  while (lo <= hi) {
    int mid = (lo + hi) / 2, c = strcmp(AIRLINE_LOGOS[mid].code, pfx);
    if (c == 0) return &AIRLINE_LOGOS[mid];
    if (c < 0) lo = mid + 1; else hi = mid - 1;
  }
  return nullptr;
}

const BrandedArt* brandedFor(const char* pfx) {
  int lo = 0, hi = (int)BRANDED_ART_N - 1;
  while (lo <= hi) {
    int mid = (lo + hi) / 2, c = strcmp(BRANDED_ART[mid].code, pfx);
    if (c == 0) return &BRANDED_ART[mid];
    if (c < 0) lo = mid + 1; else hi = mid - 1;
  }
  return nullptr;
}

void callsignPrefix(const String& callsign, char pfx[4]) {
  pfx[0] = 0;
  String cs = callsign; cs.trim();
  if (cs.length() >= 3 && isAlpha(cs[0]) && isAlpha(cs[1]) && isAlpha(cs[2])) {
    pfx[0] = toupper(cs[0]); pfx[1] = toupper(cs[1]);
    pfx[2] = toupper(cs[2]); pfx[3] = 0;
  }
}

// ---- OpenSky: fetch state vectors, return the nearest airborne plane --------
Plane fetchNearest() {
  Plane best;
  double dlat = RADIUS_KM / 111.0;
  double dlon = RADIUS_KM / (111.0 * max(cos(radians((double)HOME_LAT)), 0.01));
  char url[256];
  snprintf(url, sizeof(url),
    "https://opensky-network.org/api/states/all?lamin=%.4f&lomin=%.4f&lamax=%.4f&lomax=%.4f",
    HOME_LAT - dlat, HOME_LON - dlon, HOME_LAT + dlat, HOME_LON + dlon);

  // Keep only the "states" array to trim the parse.
  JsonDocument filter;
  filter["states"] = true;

  String token;
  bool haveToken = getOpenSkyToken(token);   // false => anonymous fallback

  JsonDocument doc(&psAlloc);
  int code = httpGetJson(url, doc, &filter, 15000, haveToken ? token.c_str() : nullptr);
  // Token expired between wakes -> refresh once and retry (per OpenSky docs).
  if (code == 401 && haveToken) {
    Serial.println("[opensky] 401 -> refresh token, retry");
    if (getOpenSkyToken(token, /*force=*/true)) {
      doc.clear();
      code = httpGetJson(url, doc, &filter, 15000, token.c_str());
    }
  }
  if (code != 200) { Serial.printf("[opensky] fetch failed (%d)\n", code); return best; }

  JsonArray states = doc["states"].as<JsonArray>();
  g_numStates = states.size();
  Serial.printf("[opensky] parsed %u states\n", (unsigned)states.size());
  double bestDist = 1e9;
  for (JsonArray s : states) {
    // OpenSky state-vector indices:
    // 0 icao24, 1 callsign, 5 lon, 6 lat, 7 baro_alt(m), 8 on_ground,
    // 9 velocity(m/s), 10 true_track, 11 vertical_rate(m/s)
    if (s[8].as<bool>()) continue;                 // skip on-ground
    if (s[5].isNull() || s[6].isNull()) continue;  // need a position
    double lon = s[5], lat = s[6];
    double d = haversineKm(HOME_LAT, HOME_LON, lat, lon);
    if (d >= bestDist) continue;
    bestDist = d;
    best.valid = true;
    best.icao24 = String((const char*)(s[0] | ""));
    String cs = String((const char*)(s[1] | ""));
    cs.trim();
    best.callsign = cs.length() ? cs : String("(no id)");
    best.lat = lat; best.lon = lon;
    best.altFt = lroundf((s[7] | 0.0f) * M_TO_FT);
    best.spdKt = lroundf((s[9] | 0.0f) * MS_TO_KT);
    best.headingDeg = lroundf(s[10] | 0.0f);
    float vr = (s[11] | 0.0f) * MS_TO_FTMIN;
    best.climb = vr > 150 ? 1 : vr < -150 ? -1 : 0;
    best.distKm = d;
    best.bearingToDeg = lroundf(bearingDeg(HOME_LAT, HOME_LON, lat, lon));
  }
  return best;
}

void lookupLocal(Plane& p) {
  String hex = p.icao24; hex.trim();
  uint32_t icao = (uint32_t)strtoul(hex.c_str(), nullptr, 16);
  char tc[9] = {0}, reg[13] = {0};
  if (icao && acdbLookup(icao, tc, reg)) {
    if (tc[0])  p.typeCode = tc;
    if (reg[0]) p.registration = reg;
  }
  if (p.typeCode.length()) {
    const AcType* t = typeInfo(p.typeCode.c_str());
    if (t) { p.model = t->name; p.baseModel = t->base; }
  }
  String cs = p.callsign; cs.trim();
  if (cs.length() >= 3 && isAlpha(cs[0]) && isAlpha(cs[1]) && isAlpha(cs[2])) {
    char pfx[4] = { (char)toupper(cs[0]), (char)toupper(cs[1]), (char)toupper(cs[2]), 0 };
    const char* a = airlineFor(pfx);
    if (a) p.airline = a;
  }
}

// ---- adsbdb: route + aircraft type -----------------------------------------
void lookupRoute(Plane& p) {
  String cs = p.callsign; cs.trim();
  bool alnum = cs.length() > 0;
  for (size_t i = 0; i < cs.length(); i++) if (!isAlphaNumeric(cs[i])) alnum = false;
  if (!alnum) return;
  JsonDocument doc;
  int code = httpGetJson("https://api.adsbdb.com/v0/callsign/" + cs, doc);
  if (code != 200) return;
  JsonObject fr = doc["response"]["flightroute"];
  if (fr.isNull()) return;
  p.orig     = String((const char*)(fr["origin"]["iata_code"] | ""));
  p.dest     = String((const char*)(fr["destination"]["iata_code"] | ""));
  p.origCity = String((const char*)(fr["origin"]["municipality"] | ""));
  p.destCity = String((const char*)(fr["destination"]["municipality"] | ""));
}

void lookupType(Plane& p) {
  String hex = p.icao24; hex.trim(); hex.toLowerCase();
  if (!hex.length()) return;
  JsonDocument doc;
  int code = httpGetJson("https://api.adsbdb.com/v0/aircraft/" + hex, doc);
  if (code != 200) return;
  JsonObject ac = doc["response"]["aircraft"];
  if (ac.isNull()) return;
  p.typeCode = String((const char*)(ac["icao_type"] | ac["type"] | ""));
}

// ---- Current weather (open-meteo: free, no key) ----------------------------
void fetchWeather() {
  char url[220];
  snprintf(url, sizeof(url),
    "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
    "&current=temperature_2m,weather_code,is_day,wind_speed_10m,wind_direction_10m"
    "&temperature_unit=fahrenheit&wind_speed_unit=mph",
    HOME_LAT, HOME_LON);
  JsonDocument doc;
  int code = httpGetJson(String(url), doc);
  if (code != 200) return;
  JsonObject cur = doc["current"];
  if (cur.isNull()) return;
  g_weather.tempF   = (int)lroundf((float)(cur["temperature_2m"] | 0.0f));
  g_weather.code    = (int)(cur["weather_code"] | 0);
  g_weather.isDay   = (int)(cur["is_day"] | 1) != 0;
  g_weather.windMph = (int)lroundf((float)(cur["wind_speed_10m"] | 0.0f));
  g_weather.windDir = (int)lroundf((float)(cur["wind_direction_10m"] | 0.0f));
  g_weather.valid   = true;
}
