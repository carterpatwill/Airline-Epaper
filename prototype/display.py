#!/usr/bin/env python3
"""
Plane "card" renderer for a monochrome e-paper display (e.g. reTerminal E1001,
800x480, 1-bit). Composites three layers:

    1. a SILHOUETTE chosen by aircraft type family  (~12 base images)
    2. an AIRLINE LOGO chosen by callsign prefix     (swap per airline)
    3. a TEXT block (callsign, type, route, telemetry)

This runs on your Mac to *design and preview* the card. The mapping functions
(`type_family`, `airline_code`) are plain lookups you can port straight to the
ESP32; on-device you'd load the silhouette/logo bitmaps from the SD card
instead of drawing them procedurally.

Usage:
    python3 display.py                 # renders a demo card -> card_preview.png
    from display import render_card     # or call it with a plane dict

Requires: Pillow  (pip install pillow)
"""

from PIL import Image, ImageDraw, ImageFont

# Target panel (reTerminal E1001): 7.5" mono e-paper, 800x480, 1-bit.
W, H = 800, 480
BLACK, WHITE = 0, 1  # mode "1": 0 = black ink, 1 = white paper


# ---------------------------------------------------------------------------
# LAYER 1 mapping: ICAO type code  ->  silhouette family
# ---------------------------------------------------------------------------
# Prefix-matched, longest prefix wins. Add codes as you meet new ones; the
# `other` family is the catch-all fallback so nothing ever renders blank.
_TYPE_PREFIXES = [
    # (prefix, family)
    ("A38", "jumbo"), ("A388", "jumbo"), ("B74", "jumbo"),
    ("B77", "widebody"), ("B78", "widebody"), ("A33", "widebody"),
    ("A34", "widebody"), ("A35", "widebody"), ("B76", "widebody"),
    ("B73", "narrowbody"), ("B38", "narrowbody"), ("A31", "narrowbody"),
    ("A32", "narrowbody"), ("A20", "narrowbody"), ("A21", "narrowbody"),
    ("A19", "narrowbody"), ("B75", "narrowbody"),
    ("CRJ", "regional_jet"), ("E7", "regional_jet"), ("E1", "regional_jet"),
    ("ERJ", "regional_jet"), ("E9", "regional_jet"),
    ("C25", "bizjet"), ("LJ", "bizjet"), ("GLF", "bizjet"), ("CL", "bizjet"),
    ("E55", "bizjet"), ("FA", "bizjet"), ("H25", "bizjet"),
    ("DH8", "turboprop"), ("AT", "turboprop"), ("BE20", "turboprop"),
    ("SF3", "turboprop"), ("C208", "turboprop"), ("DHC", "turboprop"),
    ("EC", "helicopter"), ("AS", "helicopter"), ("B407", "helicopter"),
    ("R44", "helicopter"), ("R22", "helicopter"), ("H60", "helicopter"),
    ("S76", "helicopter"), ("A139", "helicopter"),
    ("BE", "prop_single"), ("C1", "prop_single"), ("C2", "prop_single"),
    ("P28", "prop_single"), ("SR2", "prop_single"), ("DA4", "prop_single"),
    ("PA", "prop_single"), ("M20", "prop_single"),
]


def type_family(type_code):
    """Map an ICAO type code (e.g. 'B38M', 'BE35') to a silhouette family."""
    t = (type_code or "").strip().upper()
    if not t:
        return "other"
    best = ("", "other")
    for prefix, fam in _TYPE_PREFIXES:
        if t.startswith(prefix) and len(prefix) > len(best[0]):
            best = (prefix, fam)
    return best[1]


# ---------------------------------------------------------------------------
# LAYER 2 mapping: callsign prefix -> airline (ICAO code + display name)
# ---------------------------------------------------------------------------
# The first 3 letters of an airline callsign are its ICAO code. Tail numbers
# (N-numbers etc.) have no airline -> returns ("", "").
_AIRLINES = {
    "AAL": "American", "DAL": "Delta", "UAL": "United", "SWA": "Southwest",
    "JBU": "JetBlue", "ASA": "Alaska", "FFT": "Frontier", "NKS": "Spirit",
    "ACA": "Air Canada", "SKW": "SkyWest", "RPA": "Republic", "EDV": "Endeavor",
    "AAY": "Allegiant", "HAL": "Hawaiian", "AMX": "Aeromexico", "VOI": "Volaris",
    "BAW": "British Airways", "DLH": "Lufthansa", "AFR": "Air France",
    "UAE": "Emirates", "QTR": "Qatar", "KLM": "KLM", "FDX": "FedEx",
    "UPS": "UPS", "GJS": "GoJet", "JZA": "Jazz",
}


def airline_code(callsign):
    """Return (icao_code, name) for an airline callsign, or ('','') for tails."""
    cs = (callsign or "").strip().upper()
    if len(cs) < 3 or not cs[:3].isalpha():
        return ("", "")
    code = cs[:3]
    # A real airline callsign is 3 letters then digits (AAL1933), not N31444.
    if not cs[3:4].isdigit():
        return ("", "")
    return (code, _AIRLINES.get(code, code))


# ---------------------------------------------------------------------------
# LAYER 1 art: procedural top-down silhouettes (placeholders for SD-card art)
# ---------------------------------------------------------------------------
def _draw_jet(d, cx, cy, span, length, sweep, engines=2):
    """Top-down jet planform, nose pointing up, filled black."""
    hw = length / 2
    # fuselage
    d.rounded_rectangle([cx - length * 0.05, cy - hw, cx + length * 0.05, cy + hw],
                        radius=length * 0.05, fill=BLACK)
    # nose
    d.polygon([(cx, cy - hw - length * 0.10),
               (cx - length * 0.05, cy - hw + 2),
               (cx + length * 0.05, cy - hw + 2)], fill=BLACK)
    # main wings (swept)
    d.polygon([(cx, cy - length * 0.05),
               (cx - span / 2, cy + sweep),
               (cx - span / 2 + length * 0.06, cy + sweep + length * 0.05),
               (cx, cy + length * 0.10)], fill=BLACK)
    d.polygon([(cx, cy - length * 0.05),
               (cx + span / 2, cy + sweep),
               (cx + span / 2 - length * 0.06, cy + sweep + length * 0.05),
               (cx, cy + length * 0.10)], fill=BLACK)
    # tailplane
    ty = cy + hw * 0.75
    d.polygon([(cx, ty - length * 0.05), (cx - span * 0.18, ty + length * 0.05),
               (cx, ty + length * 0.08)], fill=BLACK)
    d.polygon([(cx, ty - length * 0.05), (cx + span * 0.18, ty + length * 0.05),
               (cx, ty + length * 0.08)], fill=BLACK)
    # engines
    if engines:
        for sgn in (-1, 1):
            ex = cx + sgn * span * 0.20
            d.ellipse([ex - length * 0.03, cy + sweep * 0.3,
                       ex + length * 0.03, cy + sweep * 0.3 + length * 0.12],
                      fill=BLACK)


def _draw_prop(d, cx, cy, span, length):
    _draw_jet(d, cx, cy, span, length, sweep=0, engines=0)
    # nose prop disc (thin ellipse across the nose)
    d.ellipse([cx - span * 0.12, cy - length / 2 - 14,
               cx + span * 0.12, cy - length / 2 - 2], outline=BLACK, width=4)


def _draw_heli(d, cx, cy, span, length):
    # slim body
    d.rounded_rectangle([cx - length * 0.10, cy - length * 0.4,
                         cx + length * 0.10, cy + length * 0.5],
                        radius=length * 0.10, fill=BLACK)
    # tail boom
    d.rectangle([cx - length * 0.03, cy + length * 0.4,
                 cx + length * 0.03, cy + length * 0.9], fill=BLACK)
    # main rotor (crossed lines)
    d.line([cx - span / 2, cy - length * 0.1, cx + span / 2, cy - length * 0.1],
           fill=BLACK, width=5)
    d.line([cx, cy - length * 0.1 - span * 0.28, cx, cy - length * 0.1 + span * 0.28],
           fill=BLACK, width=5)


# family -> (drawing fn, span, length) tuned so sizes read differently
_FAMILY_ART = {
    "jumbo":        (_draw_jet, 300, 300),
    "widebody":     (_draw_jet, 260, 260),
    "narrowbody":   (_draw_jet, 200, 200),
    "regional_jet": (_draw_jet, 150, 160),
    "bizjet":       (_draw_jet, 120, 150),
    "turboprop":    (_draw_prop, 170, 150),
    "prop_single":  (_draw_prop, 110, 110),
    "helicopter":   (_draw_heli, 150, 130),
    "other":        (_draw_jet, 160, 170),
}


def draw_silhouette(d, family, cx, cy):
    fn, span, length = _FAMILY_ART.get(family, _FAMILY_ART["other"])
    if fn is _draw_jet:
        eng = 4 if family in ("jumbo",) else 2
        fn(d, cx, cy, span, length, sweep=length * 0.28, engines=eng)
    else:
        fn(d, cx, cy, span, length)


# ---------------------------------------------------------------------------
# Compose the full card
# ---------------------------------------------------------------------------
def _font(size):
    try:
        return ImageFont.load_default(size=size)  # Pillow 10+: scalable default
    except TypeError:
        return ImageFont.load_default()


def render_card(plane, path="card_preview.png"):
    """plane = dict with callsign, type, route, alt, spd, track, ground, dist."""
    img = Image.new("1", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    fam = type_family(plane.get("type"))
    code, name = airline_code(plane.get("callsign"))

    # --- Layer 2: airline logo slot (top-left). Real logo bitmap goes here. ---
    d.rectangle([20, 20, 180, 90], outline=BLACK, width=3)
    if code:
        f = _font(48)
        d.text((100, 55), code, font=f, fill=BLACK, anchor="mm")
        d.text((200, 40), name, font=_font(38), fill=BLACK, anchor="lm")
    else:
        d.text((100, 55), "PVT", font=_font(40), fill=BLACK, anchor="mm")
        d.text((200, 40), "Private / GA", font=_font(38), fill=BLACK, anchor="lm")

    # --- Layer 1: silhouette (center) ---
    draw_silhouette(d, fam, cx=W // 2, cy=210)

    # --- Layer 3: text block (bottom) ---
    d.line([20, 330, W - 20, 330], fill=BLACK, width=2)
    cs = plane.get("callsign", "?")
    typ = plane.get("type") or "?"
    d.text((30, 345), cs, font=_font(64), fill=BLACK, anchor="lm")
    d.text((W - 30, 345), f"{typ}  ({fam})", font=_font(34), fill=BLACK, anchor="rm")

    route = plane.get("route") or ""
    if "->" in route:
        orig, dest = (s.strip() for s in route.split("->", 1))
        f = _font(44)
        d.text((30, 405), orig, font=f, fill=BLACK, anchor="lm")
        ox = 30 + d.textlength(orig, font=f) + 25          # gap after origin
        d.polygon([(ox, 395), (ox, 415), (ox + 28, 405)], fill=BLACK)  # arrow
        d.text((ox + 45, 405), dest, font=f, fill=BLACK, anchor="lm")
    else:
        d.text((30, 405), "route unknown", font=_font(44), fill=BLACK, anchor="lm")

    if plane.get("ground"):
        tele = "ON GROUND"
    else:
        tele = f"{plane.get('alt',0):,} ft   {plane.get('spd',0)} kt   hdg {plane.get('track',0)}deg"
    d.text((30, 455), tele, font=_font(34), fill=BLACK, anchor="lm")
    d.text((W - 30, 455), f"{plane.get('dist','?')} km away",
           font=_font(34), fill=BLACK, anchor="rm")

    img.save(path)
    # Also emit a 1-bit BMP suitable for the SD card / e-paper buffer.
    img.save(path.replace(".png", ".bmp"))
    return img


if __name__ == "__main__":
    demo = {
        "callsign": "AAL1933", "type": "B38M", "route": "MIA->ORD",
        "alt": 12000, "spd": 450, "track": 315, "ground": False, "dist": 6.1,
    }
    render_card(demo, "card_preview.png")
    print("Wrote card_preview.png and card_preview.bmp")
    print(f"  type B38M -> family {type_family('B38M')}")
    print(f"  callsign AAL1933 -> airline {airline_code('AAL1933')}")
