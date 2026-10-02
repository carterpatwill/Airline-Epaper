#include "geo.h"
#include <math.h>

// Major commercial airports only -- airliners land here. (Small GA fields like
// San Carlos/Palo Alto are deliberately excluded: a jet on SFO approach passing
// over San Carlos is landing at SFO, not the GA strip below it.)
static const Airport AIRPORTS[] = {
  {"SFO", "San Francisco", 37.6213, -122.3790},
  {"OAK", "Oakland",       37.7126, -122.2197},
  {"SJC", "San Jose",      37.3639, -121.9289},
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
