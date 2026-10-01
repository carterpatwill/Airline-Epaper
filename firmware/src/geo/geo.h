// Geographic math: great-circle distance/bearing, compass labels, the sky
// elevation angle, and the "which airport is this arrival landing at" inference.
#pragma once
#include "types.h"

// Great-circle distance between two lat/lon points, in km.
double haversineKm(double la1, double lo1, double la2, double lo2);

// Initial bearing (deg, 0..360) from point 1 to point 2.
double bearingDeg(double la1, double lo1, double la2, double lo2);

// 16-point compass label ("N", "NNE", ...) for a bearing in degrees.
const char* compass16(int deg);

// Elevation angle (deg) to look up at a plane: atan(altitude / ground dist).
int elevationDeg(long altFt, float distKm);

// The airport a descending plane is arriving at: nearest one within maxKm that
// the plane is actually heading toward (track within tolDeg of the bearing to
// it). Returns nullptr if it isn't lined up with any -- i.e. just passing over.
const Airport* arrivalAirport(double lat, double lon, int track,
                              double maxKm, double tolDeg = 70.0);
