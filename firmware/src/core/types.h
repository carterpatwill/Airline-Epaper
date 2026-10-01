// Core data structures shared across the firmware modules.
#pragma once
#include <Arduino.h>

// ---- The plane we display ---------------------------------------------------
struct Plane {
  bool   valid = false;
  String icao24, callsign;
  double lat = 0, lon = 0;
  long   altFt = 0;
  int    spdKt = 0, headingDeg = 0;
  int    climb = 0;          // +1 up, 0 level, -1 down
  float  distKm = 0;
  String orig, dest;         // IATA codes
  String origCity, destCity;
  String typeCode;           // e.g. B738 (from flash DB, else adsbdb)
  String model;              // e.g. Boeing 737-800 (from typecode table)
  String airline;            // e.g. United Airlines (from callsign prefix)
  String registration;       // e.g. N12345 (from flash DB)
  uint8_t baseModel = 0;     // silhouette id (AcBase enum), 0 = unknown
  bool   destInferred = false; // dest came from geometry (landing), not adsbdb
  int    bearingToDeg = 0;   // compass bearing FROM home TO the plane (0..360)
};

// Which screen is showing. The top white nav buttons switch between them; the
// last fetched plane is kept so a switch just redraws (no re-fetch).
enum Screen { SCREEN_DETAILS = 0, SCREEN_MAP = 1 };

// ---- Current weather (open-meteo, free/keyless) ----------------------------
struct Weather {
  bool  valid = false;
  int   tempF = 0;
  int   code  = 0;       // WMO weather code
  bool  isDay = true;
  int   windMph = 0;
  int   windDir = 0;     // degrees the wind blows FROM
};

// ---- Nearby airport, for inferring arrivals --------------------------------
struct Airport { const char* code; const char* city; double lat, lon; };
