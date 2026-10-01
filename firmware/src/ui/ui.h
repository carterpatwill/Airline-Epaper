// All e-paper rendering: the DETAILS card, the MAP screen, the plane-art
// gallery, and full-screen status messages. Everything draws to the shared
// `display` object and reads the current g_plane / g_weather / g_screen state.
#pragma once
#include "types.h"

// A full-screen status message (WiFi fail / no aircraft / API error).
void drawStatus(const String& title, const String& detail);

// The DETAILS dashboard card (800x480): logo, route, plane art, stats, weather.
void drawCard(const Plane& p);

// The MAP screen: the plane placed at its true position over the area map.
void drawMapScreen(const Plane& p);

// Draw whichever screen (DETAILS/MAP) is currently selected in g_screen.
void drawCurrentScreen();

// Gallery preview of one plane-art image (base id 1..N_PLANE_ART-1).
void drawGallery(uint8_t idx);
