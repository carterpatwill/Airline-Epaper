#!/usr/bin/env python3
"""
Live airplane tracker — hobby edition.

Shows aircraft currently flying near a location: callsign, altitude, speed,
heading, climb/descent, distance from you, and (when known) where the flight
is going.

Data sources (both free, no API key required):
  - OpenSky Network  -> live telemetry (position, altitude, speed, heading)
  - adsbdb.com       -> route lookup (origin -> destination) from callsign

Usage:
    python3 tracker.py                 # uses default location below
    python3 tracker.py LAT LON         # center on given coordinates
    python3 tracker.py LAT LON RADIUS  # RADIUS in km (default 80)
    python3 tracker.py --watch         # live refresh every 15s (Ctrl+C to stop)

Flags and coordinates can be combined, e.g.:
    python3 tracker.py 51.4700 -0.4543 60 --watch   # near Heathrow, live
"""

import json
import math
import sys
import time
import urllib.request
import urllib.error

from base_models import base_model_for, image_for

# ---- Your location (change these, or pass on the command line) -------------
DEFAULT_LAT = 33.793916    # Orange County, CA (near Fullerton / KSNA)
DEFAULT_LON = -117.850367
DEFAULT_RADIUS_KM = 80

# ---- Unit conversions ------------------------------------------------------
M_TO_FT = 3.28084
MS_TO_KT = 1.94384
MS_TO_FTMIN = 196.850

# Cache lookups so we don't hammer adsbdb for the same aircraft
_route_cache = {}
_type_cache = {}


def http_get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "hobby-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def bounding_box(lat, lon, radius_km):
    """Rough lat/lon box around a point for the given radius."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_states(lat, lon, radius_km):
    lamin, lomin, lamax, lomax = bounding_box(lat, lon, radius_km)
    url = (
        "https://opensky-network.org/api/states/all"
        f"?lamin={lamin:.4f}&lomin={lomin:.4f}&lamax={lamax:.4f}&lomax={lomax:.4f}"
    )
    data = http_get_json(url)
    return data.get("states") or []


def lookup_route(callsign):
    """Return 'ORIG->DEST' for a callsign, or '' if unknown."""
    cs = (callsign or "").strip()
    # Real callsigns are alphanumeric (e.g. DAL460). Skip blanks / "(no id)"
    # so we never build a URL with spaces or parens.
    if not cs.isalnum():
        return ""
    if cs in _route_cache:
        return _route_cache[cs]
    result = ""
    try:
        data = http_get_json(f"https://api.adsbdb.com/v0/callsign/{cs}", timeout=4)
        fr = data.get("response", {}).get("flightroute", {})
        origin = fr.get("origin", {}).get("iata_code", "")
        dest = fr.get("destination", {}).get("iata_code", "")
        if origin or dest:
            result = f"{origin or '?'}->{dest or '?'}"
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError):
        result = ""
    _route_cache[cs] = result
    return result


def lookup_type(icao24):
    """Return a short aircraft type (e.g. 'B738') for an ICAO24 hex, or ''."""
    hexid = (icao24 or "").strip().lower()
    # ICAO24 is a 6-char hex id; reject anything else before building a URL.
    if not hexid.isalnum():
        return ""
    if hexid in _type_cache:
        return _type_cache[hexid]
    result = ""
    try:
        data = http_get_json(f"https://api.adsbdb.com/v0/aircraft/{hexid}", timeout=4)
        ac = data.get("response", {}).get("aircraft", {})
        # icao_type is the compact code (e.g. B738); type is the long name.
        result = ac.get("icao_type") or ac.get("type") or ""
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError):
        result = ""
    _type_cache[hexid] = result
    return result


def scan_once(lat, lon, radius):
    print(f"\nScanning {radius:.0f} km around ({lat:.4f}, {lon:.4f})"
          f"  [{time.strftime('%H:%M:%S')}]\n")

    try:
        states = fetch_states(lat, lon, radius)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"Could not reach OpenSky: {e}")
        print("(Anonymous access is rate-limited; wait a bit and retry.)")
        return

    planes = []
    for s in states:
        # OpenSky state vector fields (by index):
        # 0 icao24, 1 callsign, 5 lon, 6 lat, 7 baro_alt(m), 8 on_ground,
        # 9 velocity(m/s), 10 true_track(deg), 11 vertical_rate(m/s)
        icao24 = s[0]
        callsign = (s[1] or "").strip()
        s_lon, s_lat = s[5], s[6]
        if s_lat is None or s_lon is None:
            continue
        alt_ft = (s[7] or 0) * M_TO_FT
        on_ground = s[8]
        spd_kt = (s[9] or 0) * MS_TO_KT
        track = s[10] or 0
        vrate = (s[11] or 0) * MS_TO_FTMIN
        dist = haversine_km(lat, lon, s_lat, s_lon)
        planes.append({
            "icao24": icao24,
            "callsign": callsign or "(no id)",
            "alt": alt_ft, "spd": spd_kt, "track": track,
            "vrate": vrate, "dist": dist, "ground": on_ground,
        })

    planes.sort(key=lambda p: p["dist"])

    if not planes:
        print("No aircraft found right now. Try a larger radius or a busier area.")
        return

    print(f"{'CALLSIGN':<9} {'TYPE':<6} {'ALT(ft)':>8} {'SPD(kt)':>7} {'HDG':>4} "
          f"{'CLIMB':>6} {'DIST(km)':>8}  ROUTE")
    print("-" * 78)

    for p in planes[:25]:
        route = "" if p["ground"] else lookup_route(p["callsign"])
        actype = lookup_type(p["icao24"])
        climb = "level"
        if p["vrate"] > 150:
            climb = "up"
        elif p["vrate"] < -150:
            climb = "down"
        alt = "GND" if p["ground"] else f"{p['alt']:,.0f}"
        print(f"{p['callsign']:<9} {actype:<6} {alt:>8} {p['spd']:>7.0f} "
              f"{p['track']:>4.0f} {climb:>6} {p['dist']:>8.1f}  {route}")

    print(f"\n{len(planes)} aircraft in range. Routes shown where adsbdb knows them.")


def collect_planes(lat, lon, radius, limit=60, detail_budget=6):
    """Return a list of plane dicts (for the web front end / JSON API).

    Telemetry (position/alt/speed/heading) is returned immediately from one
    OpenSky call. Type/route come from adsbdb, which is slow, so we only look
    up already-cached values plus a small `detail_budget` of NEW ones per
    request. Over a few 15s refreshes the whole map fills in, and no single
    request blocks long enough for the browser to give up.
    """
    states = fetch_states(lat, lon, radius)
    planes = []
    for s in states:
        icao24 = s[0]
        callsign = (s[1] or "").strip()
        s_lon, s_lat = s[5], s[6]
        if s_lat is None or s_lon is None:
            continue
        planes.append({
            "icao24": icao24,
            "callsign": callsign or "(no id)",
            "lat": s_lat, "lon": s_lon,
            "alt": round((s[7] or 0) * M_TO_FT),
            "spd": round((s[9] or 0) * MS_TO_KT),
            "track": round(s[10] or 0),
            "vrate": round((s[11] or 0) * MS_TO_FTMIN),
            "ground": bool(s[8]),
            "dist": round(haversine_km(lat, lon, s_lat, s_lon), 1),
        })
    planes.sort(key=lambda p: p["dist"])
    planes = planes[:limit]

    for p in planes:
        hexid = (p["icao24"] or "").strip().lower()
        cs = p["callsign"]
        # Use cached details for free; spend budget on new lookups only.
        if hexid in _type_cache:
            p["type"] = _type_cache[hexid]
        elif detail_budget > 0:
            p["type"] = lookup_type(hexid); detail_budget -= 1
        else:
            p["type"] = ""

        if p["ground"]:
            p["route"] = ""
        elif cs in _route_cache:
            p["route"] = _route_cache[cs]
        elif detail_budget > 0:
            p["route"] = lookup_route(cs); detail_budget -= 1
        else:
            p["route"] = ""

        # Tag with a base silhouette model so the front end knows which base
        # to stack the airline logo on. "Unknown" until the type resolves.
        p["base"] = base_model_for(p["type"])
        # URL the browser can load to show this base model's silhouette.
        img = image_for(p["base"])
        p["base_img"] = f"/img/{img}" if img else ""
    return planes


def serve(lat, lon, radius, port=8000):
    """Run a tiny web server: '/' -> map UI, '/api/planes' -> JSON."""
    import http.server

    here = __import__("os").path.dirname(__import__("os").path.abspath(__file__))

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/api/planes"):
                try:
                    data = collect_planes(lat, lon, radius)
                    payload = {"center": [lat, lon], "radius_km": radius,
                               "planes": data}
                    self._send(200, json.dumps(payload).encode(),
                               "application/json")
                except Exception as e:  # never let a request return nothing
                    self._send(502, json.dumps({"error": str(e)}).encode(),
                               "application/json")
                return

            # Serve a base-model silhouette from plane-images/ (basename only,
            # so a request can't escape the folder with '..').
            if self.path.startswith("/img/"):
                fname = __import__("os").path.basename(self.path[len("/img/"):])
                fpath = __import__("os").path.join(here, "plane-images", fname)
                try:
                    with open(fpath, "rb") as f:
                        self._send(200, f.read(), "image/png")
                except OSError:
                    self._send(404, b"image not found", "text/plain")
                return
            # serve index.html for '/' (and anything else)
            try:
                with open(__import__("os").path.join(here, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(404, b"index.html not found", "text/plain")

    # Threaded so a slow adsbdb lookup never blocks the HTML/tiles/API.
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"\nMap UI running at  http://127.0.0.1:{port}")
    print(f"Centered on ({lat:.4f}, {lon:.4f}), radius {radius:.0f} km.")
    print("Press Ctrl+C to stop.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    args = sys.argv[1:]
    watch = "--watch" in args
    web = "--web" in args
    args = [a for a in args if a not in ("--watch", "--web")]

    lat = float(args[0]) if len(args) >= 1 else DEFAULT_LAT
    lon = float(args[1]) if len(args) >= 2 else DEFAULT_LON
    radius = float(args[2]) if len(args) >= 3 else DEFAULT_RADIUS_KM

    if web:
        serve(lat, lon, radius)
        return

    if not watch:
        scan_once(lat, lon, radius)
        return

    print("Live mode — refreshing every 15s. Press Ctrl+C to stop.")
    try:
        while True:
            scan_once(lat, lon, radius)
            time.sleep(15)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
