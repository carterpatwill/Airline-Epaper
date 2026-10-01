#include "geo.h"
#include <math.h>

// Major commercial airports only -- airliners land here. (Small GA fields like
// Fullerton/Chino are deliberately excluded: a jet on SNA approach passing over
// Fullerton is landing at SNA, not the GA strip below it.)
static const Airport AIRPORTS[] = {
  {"SNA", "Santa Ana",    33.6757, -117.8682},
  {"LAX", "Los Angeles",  33.9416, -118.4085},
  {"LGB", "Long Beach",   33.8177, -118.1516},
  {"ONT", "Ontario",      34.0560, -117.6012},
  {"BUR", "Burbank",      34.2007, -118.3587},
};

double haversineKm(double la1, double lo1, double la2, double lo2) {
  const double R = 6371.0;
  double p1 = radians(la1), p2 = radians(la2);
  double dp = radians(la2 - la1), dl = radians(lo2 - lo1);
  double a = sin(dp/2)*sin(dp/2) + cos(p1)*cos(p2)*sin(dl/2)*sin(dl/2);
  return 2 * R * asin(sqrt(a));
}

double bearingDeg(double la1, double lo1, double la2, double lo2) {
  double y = sin(radians(lo2 - lo1)) * cos(radians(la2));
  double x = cos(radians(la1)) * sin(radians(la2)) -
             sin(radians(la1)) * cos(radians(la2)) * cos(radians(lo2 - lo1));
  double b = degrees(atan2(y, x));
  return fmod(b + 360.0, 360.0);
}

const Airport* arrivalAirport(double lat, double lon, int track,
                              double maxKm, double tolDeg) {
  const Airport* best = nullptr; double bd = maxKm;
  for (const Airport& a : AIRPORTS) {
    double d = haversineKm(lat, lon, a.lat, a.lon);
    if (d >= bd) continue;
    double br = bearingDeg(lat, lon, a.lat, a.lon);
    double diff = fabs(br - track);
    if (diff > 180) diff = 360 - diff;
    if (diff > tolDeg) continue;                 // not heading toward it
    bd = d; best = &a;
  }
  return best;
}

const char* compass16(int deg) {
  static const char* C[] = {"N","NNE","NE","ENE","E","ESE","SE","SSE",
                            "S","SSW","SW","WSW","W","WNW","NW","NNW"};
  return C[(int)((deg % 360) / 22.5 + 0.5) % 16];
}

int elevationDeg(long altFt, float distKm) {
  float altKm = altFt * 0.0003048f;
  if (distKm <= 0) return 90;
  return (int)(atan2(altKm, distKm) * 180.0 / PI + 0.5);
}
