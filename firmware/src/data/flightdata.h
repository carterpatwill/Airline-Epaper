// Flight data acquisition + enrichment: the nearest airborne plane from OpenSky,
// the on-flash aircraft DB (icao24 -> type/registration), typecode/airline/logo
// lookups, adsbdb route+type fallbacks, and current weather.
#pragma once
#include "types.h"
#include "gen_aircraft_types.h"   // AcType : typecode -> name + silhouette id
#include "gen_airline_logos.h"    // AirlineLogo : ICAO prefix -> 1bpp wordmark
#include "gen_branded_art.h"      // BrandedArt : ICAO prefix -> 1bpp livery render

// LittleFS acdb.bin mount state (set by acdbInit()).
extern bool     g_acdbOk;
extern uint32_t g_acdbN;

// Mount the on-flash aircraft DB (LittleFS). Non-fatal: without it we fall back
// to adsbdb for aircraft type. Call once from setup().
void acdbInit();

// OpenSky: fetch state vectors for the home bounding box, return nearest airborne.
Plane fetchNearest();

// Fill type/model/airline/registration entirely from on-device data (no net).
void lookupLocal(Plane& p);

// adsbdb (network) fallbacks: route (origin/destination) and aircraft type.
void lookupRoute(Plane& p);
void lookupType(Plane& p);

// open-meteo (network): current temp + condition, into g_weather.
void fetchWeather();

// typecode -> friendly name + silhouette id (binary search AC_TYPES).
const AcType* typeInfo(const char* code);

// 3-letter callsign prefix -> airline wordmark logo (binary search).
const AirlineLogo* logoFor(const char* pfx);

// 3-letter callsign prefix -> branded livery render, or nullptr (binary search).
// When present, this replaces the plain per-base silhouette in the plane box.
const BrandedArt* brandedFor(const char* pfx);

// Extract the 3-letter ICAO prefix from a callsign into pfx[4], "" if none.
void callsignPrefix(const String& callsign, char pfx[4]);
