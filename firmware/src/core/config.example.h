// ---- Your settings — EDIT THESE -------------------------------------------
// TEMPLATE. Copy this file to `config.h` (same folder) and fill in your own
// values. config.h is gitignored because it holds your WiFi password + API
// secret — never commit it.
//
//   cp config.example.h config.h
//
#pragma once

// WiFi (2.4GHz only — the E1001 does not support 5GHz).
#define WIFI_SSID   "your-wifi-ssid"
#define WIFI_PASS   "your-wifi-password"

// OpenSky OAuth2 client credentials (Account page -> API Client).
// These are exchanged for a 30-min bearer token; see getOpenSkyToken().
// Leave both empty ("") to fall back to anonymous access (lower rate limit).
#define OPENSKY_CLIENT_ID      "your-opensky-client-id"
#define OPENSKY_CLIENT_SECRET  "your-opensky-client-secret"

// Your location (the "overhead" reference point).
#define HOME_LAT    37.534868
#define HOME_LON    -122.247887
#define RADIUS_KM   80.0

// How often to wake, refresh, and re-check (minutes). E-paper + battery: keep
// this modest. 5 min is a good starting point.
#define REFRESH_MINUTES  5

// Commercial airlines only. When 1, ignore private/GA/military traffic and only
// ever show scheduled airliners. Detection: the callsign must carry a known
// 3-letter airline ICAO prefix (UAL, SWA, ...). GA planes broadcast their tail
// number (N12345) as the callsign, which has no airline prefix, so they're
// skipped. Set to 0 to show the single closest plane of any kind.
#define COMMERCIAL_ONLY  1

// POSIX timezone string for the header clock (fetched from NTP).
// Default = US Pacific. Examples: US Eastern "EST5EDT,M3.2.0,M11.1.0".
#define TZ_POSIX    "PST8PDT,M3.2.0,M11.1.0"
