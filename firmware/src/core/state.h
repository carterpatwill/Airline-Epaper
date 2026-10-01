// Cross-cutting app state: the last fetched plane, current weather, and which
// screen is showing. Produced by main/flightdata, consumed by the UI.
#pragma once
#include "types.h"

extern Plane   g_plane;     // last good plane (valid=false until first fetch)
extern Weather g_weather;
extern Screen  g_screen;
