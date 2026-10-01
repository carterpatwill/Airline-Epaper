# ✈️ Airplane Tracker

Live tracking of aircraft flying within a radius of any location — callsign,
altitude, speed, heading, climb/descent, distance from you, and destination.

**No API keys. No dependencies.** Pure Python standard library.

## Data sources (both free)
- **[OpenSky Network](https://opensky-network.org/)** — live telemetry
  (position, altitude, speed, heading).
- **[adsbdb.com](https://www.adsbdb.com/)** — flight route lookup
  (origin → destination) from the callsign.

## Usage

### Terminal
```bash
python3 tracker.py                        # default location (NYC)
python3 tracker.py 51.4700 -0.4543        # lat lon (near Heathrow)
python3 tracker.py 51.4700 -0.4543 60     # + radius in km
python3 tracker.py --watch                # live, refresh every 15s
python3 tracker.py 34.0522 -118.2437 100 --watch   # LA, 100km, live
```

### Web map (front end)
```bash
python3 tracker.py --web                  # then open http://127.0.0.1:8000
python3 tracker.py 34.0522 -118.2437 100 --web     # LA, 100km
```
Opens a live [Leaflet](https://leafletjs.com/) map: planes are ✈️ icons that
rotate to their heading and refresh every 15s. Click any plane for callsign,
type, route, altitude, speed, heading, and distance. The blue circle shows your
search radius. The map calls the built-in JSON API at `/api/planes`.

To set a permanent home location, edit the `DEFAULT_LAT` / `DEFAULT_LON` /
`DEFAULT_RADIUS_KM` values near the top of `tracker.py`.

## Example output

```
CALLSIGN   ALT(ft) SPD(kt)  HDG  CLIMB DIST(km)  ROUTE
--------------------------------------------------------------------
DAL460       1,800     156   78   down      9.7  FLL->MSP
AAL2927      2,875     257   37  level      9.9  DFW->TUS
EDV4719      3,925     251  265     up     12.7  BHM->LGA
```

## Notes
- Columns: altitude (feet), speed (knots), heading (0–360°), climb state,
  distance (km), and route (IATA airport codes).
- `GND` means the aircraft is on the ground (taxiing / parked).
- Not every flight has a known route in adsbdb — that column may be blank.
- OpenSky's anonymous access is rate-limited. If you get an error, wait a
  minute and retry, or create a free OpenSky account for higher limits.

## Finding your coordinates
Search your city on [openstreetmap.org](https://www.openstreetmap.org),
right-click → "Show address" — or just Google "<your city> latitude longitude".
