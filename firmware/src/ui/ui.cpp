#include "ui.h"
#include <time.h>
#include <Fonts/FreeSansBold24pt7b.h>
#include <Fonts/FreeSansBold18pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSansBold9pt7b.h>

#include "display.h"
#include "state.h"
#include "geo.h"
#include "flightdata.h"           // callsignPrefix, logoFor
#include "gen_plane_art.h"        // PLANE_ART[] / PLANE_ART_NAME[] / N_PLANE_ART
#include "gen_map.h"              // MAP_BG : 800x480 1bpp area map (MAP screen)

// ---- Text helpers -----------------------------------------------------------
static void text(int x, int y, const GFXfont* f, const String& s) {
  display.setFont(f); display.setCursor(x, y); display.print(s);
}
static void textRight(int xRight, int y, const GFXfont* f, const String& s) {
  int16_t bx, by; uint16_t bw, bh;
  display.setFont(f);
  display.getTextBounds(s, 0, 0, &bx, &by, &bw, &bh);
  display.setCursor(xRight - bw, y); display.print(s);
}
static void textCenter(int cx, int y, const GFXfont* f, const String& s) {
  int16_t bx, by; uint16_t bw, bh;
  display.setFont(f);
  display.getTextBounds(s, 0, 0, &bx, &by, &bw, &bh);
  display.setCursor(cx - bw / 2, y); display.print(s);
}

static String clockStr() {
  time_t now = time(nullptr);
  if (now < 100000) return "--:--";       // NTP not synced
  struct tm tm; localtime_r(&now, &tm);
  char b[8]; strftime(b, sizeof(b), "%H:%M", &tm);
  return String(b);
}

// Format an integer with thousands separators, e.g. 32000 -> "32,000".
static String withCommas(long n) {
  char tmp[16]; snprintf(tmp, sizeof(tmp), "%ld", n);
  String s = tmp;
  int start = s.startsWith("-") ? 1 : 0;
  for (int i = (int)s.length() - 3; i > start; i -= 3)
    s = s.substring(0, i) + "," + s.substring(i);
  return s;
}

// ---- Weather icons (drawn with primitives; monochrome) ---------------------
static void drawSun(int cx, int cy, int r) {
  for (int i = 0; i < 8; i++) {
    float a = i * 0.7853982f;                  // 45 deg steps
    int x0 = cx + (int)((r + 3) * cosf(a)), y0 = cy + (int)((r + 3) * sinf(a));
    int x1 = cx + (int)((r + 8) * cosf(a)), y1 = cy + (int)((r + 8) * sinf(a));
    display.drawLine(x0, y0, x1, y1, GxEPD_BLACK);
    display.drawLine(x0 + 1, y0, x1 + 1, y1, GxEPD_BLACK);
  }
  display.fillCircle(cx, cy, r, GxEPD_BLACK);
}
static void drawMoon(int cx, int cy, int r) {
  display.fillCircle(cx, cy, r, GxEPD_BLACK);
  display.fillCircle(cx + (int)(r * 0.55f), cy - (int)(r * 0.35f), r, GxEPD_WHITE);
}
static void drawCloud(int cx, int cy, int s) {
  int r = s / 2;
  display.fillCircle(cx - r, cy, (int)(r * 0.75f), GxEPD_BLACK);
  display.fillCircle(cx + r, cy, (int)(r * 0.70f), GxEPD_BLACK);
  display.fillCircle(cx - r / 3, cy - r / 2, (int)(r * 0.95f), GxEPD_BLACK);
  display.fillCircle(cx + r / 2, cy - r / 3, (int)(r * 0.80f), GxEPD_BLACK);
  display.fillRect(cx - r - 2, cy, 2 * r + 6, r, GxEPD_BLACK);
}
static void drawCloudMoon(int cx, int cy, int s) {
  drawMoon(cx + s / 2 + 2, cy - s / 2 - 3, 9);   // moon peeking upper-right
  drawCloud(cx - 2, cy + 3, s);                   // cloud in front
}
// Heading compass: north-up arrow pointing along the track.
static void drawCompass(int cx, int cy, int r, int hdg) {
  // Cardinal labels around the arrow (north-up), no ring.
  textCenter(cx, cy - r - 5, &FreeSansBold9pt7b, "N");
  textCenter(cx, cy + r + 16, &FreeSansBold9pt7b, "S");
  textCenter(cx + r + 11, cy + 5, &FreeSansBold9pt7b, "E");
  textCenter(cx - r - 11, cy + 5, &FreeSansBold9pt7b, "W");

  float a = hdg * 0.0174532925f;                           // radians
  float s = sinf(a), c = cosf(a);
  int len = r - 6;
  int tipx = cx + (int)(len * s),        tipy = cy - (int)(len * c);
  int talx = cx - (int)(len * 0.7f * s), taly = cy + (int)(len * 0.7f * c);
  display.drawLine(talx,     taly, tipx,     tipy, GxEPD_BLACK);   // shaft (3px)
  display.drawLine(talx + 1, taly, tipx + 1, tipy, GxEPD_BLACK);
  display.drawLine(talx - 1, taly, tipx - 1, tipy, GxEPD_BLACK);

  // Arrowhead: two barbs rotated +/- from the reverse direction (-s, c).
  const float p = 0.45f, hl = 12.0f;
  int lx = tipx + (int)(hl * (-s * cosf(p) - c * sinf(p)));
  int ly = tipy + (int)(hl * (-s * sinf(p) + c * cosf(p)));
  int rx = tipx + (int)(hl * (-s * cosf(p) + c * sinf(p)));
  int ry = tipy + (int)(hl * ( s * sinf(p) + c * cosf(p)));
  display.fillTriangle(tipx, tipy, lx, ly, rx, ry, GxEPD_BLACK);
}
// Wind streak glyph: flowing lines with a little curl, left edge at (x), mid (y).
static void drawWind(int x, int y) {
  display.drawLine(x, y - 6, x + 15, y - 6, GxEPD_BLACK);       // top line
  display.drawLine(x, y - 5, x + 15, y - 5, GxEPD_BLACK);
  display.drawLine(x + 15, y - 5, x + 18, y - 8, GxEPD_BLACK);  // curl up
  display.drawLine(x + 18, y - 8, x + 15, y - 10, GxEPD_BLACK);
  display.drawLine(x, y, x + 21, y, GxEPD_BLACK);               // middle line
  display.drawLine(x, y + 1, x + 21, y + 1, GxEPD_BLACK);
  display.drawLine(x + 21, y + 1, x + 24, y - 2, GxEPD_BLACK);  // curl
  display.drawLine(x + 24, y - 2, x + 21, y - 4, GxEPD_BLACK);
  display.drawLine(x, y + 6, x + 12, y + 6, GxEPD_BLACK);       // bottom line
  display.drawLine(x, y + 7, x + 12, y + 7, GxEPD_BLACK);
  display.drawLine(x + 12, y + 6, x + 15, y + 4, GxEPD_BLACK);  // curl
}
// Choose the icon from the WMO code + day/night: clear->sun/moon, else clouds.
static void drawWeatherIcon(int cx, int cy) {
  bool clear = g_weather.code <= 1;   // 0 clear, 1 mainly clear
  if (clear) {
    if (g_weather.isDay) drawSun(cx, cy, 13); else drawMoon(cx, cy, 14);
  } else {
    if (g_weather.isDay) drawCloud(cx, cy, 26); else drawCloudMoon(cx, cy, 24);
  }
}

// ---- Full-screen status message --------------------------------------------
void drawStatus(const String& title, const String& detail) {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);
    textCenter(400, 220, &FreeSansBold24pt7b, title);
    textCenter(400, 270, &FreeSans9pt7b, detail);
    textCenter(400, 300, &FreeSans9pt7b, "retrying at next refresh");
  } while (display.nextPage());
}

// ---- The dashboard card (800x480) ------------------------------------------
void drawCard(const Plane& p) {
  char buf[48];
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);

    // Header: big airline logo up top, flight number below it (left); clock +
    // tail on the right; rule under. Model is omitted here (shown under plane).
    char pfx[4]; callsignPrefix(p.callsign, pfx);
    const AirlineLogo* logo = pfx[0] ? logoFor(pfx) : nullptr;
    if (logo) {
      // Logo fills the left corner (vertically centered); flight code to its
      // right, smaller.
      int ly = (78 - logo->h) / 2;
      display.drawBitmap(18, ly, logo->bits, logo->w, logo->h, GxEPD_BLACK);
      text(18 + logo->w + 16, 47, &FreeSansBold12pt7b, p.callsign);
    } else {
      // No logo for this airline: fall back to a big callsign + airline name.
      text(22, 42, &FreeSansBold24pt7b, p.callsign);
      text(24, 68, &FreeSans9pt7b, p.airline.length() ? p.airline : String("aircraft"));
    }
    textRight(778, 40, &FreeSansBold12pt7b, clockStr());
    if (p.registration.length())
      textRight(778, 66, &FreeSans9pt7b, p.registration);
    display.fillRect(0, 78, 800, 3, GxEPD_BLACK);

    // Stats column pushed to the right edge so the plane gets more room.
    const int divX = 560;
    display.fillRect(divX, 78, 3, 340, GxEPD_BLACK);

    // Route line:  ORIG  --->  DEST  (kept high under the header so the plane
    // below can be large).
    String orig = p.orig.length() ? p.orig : String("?");
    String dest = p.dest.length() ? p.dest : String("?");
    text(30, 130, &FreeSansBold24pt7b, orig);
    textRight(525, 130, &FreeSansBold24pt7b, dest);
    display.fillRect(150, 113, 220, 3, GxEPD_BLACK);
    display.fillTriangle(370, 105, 370, 123, 386, 114, GxEPD_BLACK);
    text(30, 156, &FreeSans9pt7b, p.origCity);
    textRight(525, 156, &FreeSans9pt7b,
              p.destInferred ? (p.destCity + " (landing)") : p.destCity);

    // Plane art centered in the left region (no border).
    const int bx = 5, by = 168, bw = 550, bh = 226;
    // Tier 1: a true-to-life branded livery for this airline (Alaska, Delta,
    // United, ...), keyed by callsign prefix. Tier 2: otherwise the plain
    // per-base silhouette; if the type never resolved (base 0) or its slot is
    // empty, fall back to a generic narrow-body jet rather than a blank box --
    // an unknown plane overhead is almost always an airliner.
    const BrandedArt* branded = pfx[0] ? brandedFor(pfx) : nullptr;
    if (branded && branded->bits) {
      int ax = bx + (bw - branded->w) / 2;
      int ay = by + (bh - branded->h) / 2;
      display.drawBitmap(ax, ay, branded->bits, branded->w, branded->h, GxEPD_BLACK);
    } else {
      uint8_t base = p.baseModel;
      if (base >= N_PLANE_ART || !PLANE_ART[base].bits)
        base = BASE_CLASSIC_NARROWBODY;
      const PlaneArt& art = PLANE_ART[base];
      if (art.bits) {
        int ax = bx + (bw - art.w) / 2;
        int ay = by + (bh - art.h) / 2;
        display.drawBitmap(ax, ay, art.bits, art.w, art.h, GxEPD_BLACK);
      }
    }
    textCenter(bx + bw / 2, 411, &FreeSansBold12pt7b,
               p.model.length() ? p.model
                 : (p.typeCode.length() ? p.typeCode : String("Unknown type")));

    // Right column stats (hug the right edge).
    int sx = divX + 18;
    const int sw = 778 - sx;              // rule width to the right margin
    text(sx, 120, &FreeSansBold9pt7b, "ALTITUDE");
    display.fillRect(sx, 128, sw, 1, GxEPD_BLACK);
    snprintf(buf, sizeof(buf), "%s ft %s", withCommas(p.altFt).c_str(),
             p.climb > 0 ? "^" : p.climb < 0 ? "v" : "-");
    text(sx, 165, &FreeSansBold18pt7b, buf);

    text(sx, 220, &FreeSansBold9pt7b, "GROUND SPEED");
    display.fillRect(sx, 228, sw, 1, GxEPD_BLACK);
    snprintf(buf, sizeof(buf), "%d mph", (int)lroundf(p.spdKt * 1.15078f));
    text(sx, 265, &FreeSansBold18pt7b, buf);

    text(sx, 320, &FreeSansBold9pt7b, "HEADING");
    display.fillRect(sx, 328, sw, 1, GxEPD_BLACK);
    drawCompass(sx + (sw / 2), 374, 22, p.headingDeg);

    // Footer: current weather (left) + where to look (right).
    display.fillRect(0, 418, 800, 3, GxEPD_BLACK);
    if (g_weather.valid) {
      drawWeatherIcon(44, 449);
      char wbuf[8]; snprintf(wbuf, sizeof(wbuf), "%d", g_weather.tempF);
      int tx = 78;
      text(tx, 460, &FreeSansBold18pt7b, wbuf);
      int16_t bxx, byy; uint16_t bww, bhh;
      display.setFont(&FreeSansBold18pt7b);
      display.getTextBounds(wbuf, 0, 0, &bxx, &byy, &bww, &bhh);
      int dcx = tx + bww + 8;                 // degree ring after the number
      display.drawCircle(dcx, 445, 4, GxEPD_BLACK);
      display.drawCircle(dcx, 445, 3, GxEPD_BLACK);
      // Wind streak icon + speed, e.g. "~ 8 mph".
      int wx = dcx + 16;
      drawWind(wx, 449);
      char wind[24];
      snprintf(wind, sizeof(wind), "%d mph", g_weather.windMph);
      text(wx + 32, 458, &FreeSansBold12pt7b, wind);
    }
    snprintf(buf, sizeof(buf), "%.1f mi away", p.distKm * 0.621371f);
    textRight(778, 458, &FreeSansBold12pt7b, buf);
  } while (display.nextPage());
}

// ---- MAP screen: the plane in relation to YOU, over the area map -----------
// YOU sit at the center; the plane is placed by BEARING (angle, north-up) and
// DISTANCE (radius) on concentric range rings, over the dithered area map.

// White box behind black text (keeps labels legible over the dithered map).
static void chip(int x, int yb, const GFXfont* f, const String& s) {
  int16_t bx, by; uint16_t bw, bh;
  display.setFont(f);
  display.getTextBounds(s, x, yb, &bx, &by, &bw, &bh);
  display.fillRect(bx - 3, by - 2, bw + 6, bh + 4, GxEPD_WHITE);
  display.setTextColor(GxEPD_BLACK);
  display.setCursor(x, yb); display.print(s);
}
// Black box with white text (for the YOU marker + plane callsign tag).
static void chipInv(int x, int yb, const GFXfont* f, const String& s) {
  int16_t bx, by; uint16_t bw, bh;
  display.setFont(f);
  display.getTextBounds(s, x, yb, &bx, &by, &bw, &bh);
  display.fillRect(bx - 3, by - 2, bw + 6, bh + 4, GxEPD_BLACK);
  display.setTextColor(GxEPD_WHITE);
  display.setCursor(x, yb); display.print(s);
  display.setTextColor(GxEPD_BLACK);
}
// A little aircraft marker: filled triangle pointing along `hdg` (0 = north/up),
// with a white halo so it reads over the busy map.
static void planeMarker(int px, int py, int hdg) {
  float a = hdg * 0.0174532925f, s = sinf(a), c = cosf(a);
  auto tri = [&](float L, float Wd, uint16_t col) {
    int nx  = px + s * L,        ny  = py - c * L;               // nose
    int blx = px - s * 0.6f * L - c * Wd, bly = py + c * 0.6f * L - s * Wd;
    int brx = px - s * 0.6f * L + c * Wd, bry = py + c * 0.6f * L + s * Wd;
    display.fillTriangle(nx, ny, blx, bly, brx, bry, col);
  };
  tri(14, 10, GxEPD_WHITE);   // halo
  tri(11, 7,  GxEPD_BLACK);   // body
}

// --- Map calibration for SanFranGrey.png (800x480) ---
// From tools/build_calibrator.py, RMS fit error 0.44 mi over 5 points.
// Span: 75.3 mi wide x 45.2 mi tall.
static const double MAP_LAT_TOP   = 37.873382;   // pixel y = 0
static const double MAP_LAT_BOT   = 37.219073;   // pixel y = 480
static const double MAP_LON_LEFT  = -122.969147; // pixel x = 0
static const double MAP_LON_RIGHT = -121.593976; // pixel x = 800

// Geographic lat/lon -> map pixel (north-up, axis-aligned).
static void latLonToPixel(double lat, double lon, int& px, int& py) {
  px = lroundf((lon - MAP_LON_LEFT) / (MAP_LON_RIGHT - MAP_LON_LEFT) * 800.0);
  py = lroundf((lat - MAP_LAT_TOP)  / (MAP_LAT_BOT  - MAP_LAT_TOP ) * 480.0);
}

void drawMapScreen(const Plane& p) {
  const int cx = 400;                // used only for the north indicator

  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);

    // Area map backdrop (1 = black ink; white pixels left as paper).
    display.drawBitmap(0, 0, MAP_BG, MAP_BG_W, MAP_BG_H, GxEPD_BLACK);

    // North indicator (top center).
    chip(cx - 10, 26, &FreeSansBold9pt7b, "N");
    display.fillTriangle(cx - 1, 6, cx - 7, 14, cx + 5, 14, GxEPD_BLACK);

    // The plane at its TRUE position on the map (lat/lon -> pixel). Planes that
    // fall outside the map get clamped to the nearest edge and tagged.
    float distMi = p.distKm * 0.621371f;
    int px, py;
    latLonToPixel(p.lat, p.lon, px, py);
    bool off = px < 6 || px > 794 || py < 6 || py > 474;
    px = constrain(px, 8, 792);
    py = constrain(py, 8, 472);
    planeMarker(px, py, p.headingDeg);
    // Callsign tag beside the marker, flipped to the left near the right edge.
    String tag = p.callsign.length() ? p.callsign : String("plane");
    if (off) tag += " (off map)";
    int tagx = px + 16;
    { int16_t bx, by; uint16_t bw, bh;
      display.setFont(&FreeSansBold9pt7b);
      display.getTextBounds(tag, 0, 0, &bx, &by, &bw, &bh);
      if (tagx + (int)bw > 792) tagx = px - 16 - (int)bw; }
    chipInv(tagx, py + 5, &FreeSansBold9pt7b, tag);

    // Header chips: callsign (left) + clock (right), over the map.
    chip(16, 34, &FreeSansBold12pt7b, tag);
    { int16_t bx, by; uint16_t bw, bh;
      String t = clockStr();
      display.setFont(&FreeSansBold12pt7b);
      display.getTextBounds(t, 0, 0, &bx, &by, &bw, &bh);
      chip(782 - (int)bw, 34, &FreeSansBold12pt7b, t); }

    // Bottom info strip: distance + look direction (left), altitude + elevation
    // angle (right). Mirrors the DETAILS footer.
    display.fillRect(0, 418, 800, 62, GxEPD_WHITE);
    display.fillRect(0, 418, 800, 3, GxEPD_BLACK);
    char buf[48];
    snprintf(buf, sizeof(buf), "%.1f mi", distMi);
    text(18, 456, &FreeSansBold18pt7b, buf);
    snprintf(buf, sizeof(buf), "Look %s", compass16(p.bearingToDeg));
    text(150, 454, &FreeSansBold12pt7b, buf);
    int elev = elevationDeg(p.altFt, p.distKm);
    snprintf(buf, sizeof(buf), "%s ft   %d deg up",
             withCommas(p.altFt).c_str(), elev);
    textRight(782, 454, &FreeSansBold12pt7b, buf);
  } while (display.nextPage());
}

// Draw whichever screen is currently selected, using the last fetched plane.
void drawCurrentScreen() {
  if (g_screen == SCREEN_MAP && g_plane.valid) drawMapScreen(g_plane);
  else                                         drawCard(g_plane);
}

// ---- Gallery: preview every plane-art image, one per screen ----------------
// idx is a base id 1..N_PLANE_ART-1; blank slots are skipped by the caller.
void drawGallery(uint8_t idx) {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);

    // Header: which image + counter, rule under.
    char buf[48];
    text(22, 52, &FreeSansBold24pt7b, "Plane art");
    snprintf(buf, sizeof(buf), "%u / %u", idx, (unsigned)(N_PLANE_ART - 1));
    textRight(778, 50, &FreeSansBold18pt7b, buf);
    display.fillRect(0, 78, 800, 3, GxEPD_BLACK);

    // The art, centered in a box sized to the art so the plane fills the frame.
    const int bx = 150, by = 100, bw = 500, bh = 280;
    display.drawRect(bx, by, bw, bh, GxEPD_BLACK);
    const PlaneArt& art = PLANE_ART[idx];
    if (art.bits) {
      int ax = bx + (bw - art.w) / 2;
      int ay = by + (bh - art.h) / 2;
      display.drawBitmap(ax, ay, art.bits, art.w, art.h, GxEPD_BLACK);
    }

    // Name + hint.
    textCenter(400, 425, &FreeSansBold18pt7b, PLANE_ART_NAME[idx]);
    textCenter(400, 465, &FreeSans9pt7b,
               "left button = back    right / green = next");
  } while (display.nextPage());
}
