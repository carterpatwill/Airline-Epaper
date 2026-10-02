#!/usr/bin/env python3
"""
Turn the branded, true-to-life airline side-view renders in _Planes/*ClassicNarrow.png
into e-paper-ready 1bpp bitmaps, keyed by the airline's ICAO callsign prefix
(the same 3-letter prefix the firmware derives from the live callsign, e.g.
ASA -> Alaska). These are the "Tier 1" art: when the plane overhead is one of
these carriers, the firmware draws its actual livery instead of the plain
per-base-model silhouette (PLANE_ART), which stays the fallback for everyone else.

Same image pipeline as tools/build_plane_art.py (light-gray render on white ->
gamma-darkened -> fit box -> Floyd-Steinberg dither -> 1bpp), just keyed by
airline instead of base id.

Output:
  firmware/src/generated/gen_branded_art.h   BRANDED_ART[] sorted by ICAO prefix

Run from the repo root:
    python3 tools/build_branded_art.py
"""
import argparse, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "_Planes")
PREVIEW_DIR = os.path.join(IMG_DIR, "preview_branded")
OUT_H = os.path.join(ROOT, "firmware", "src", "generated", "gen_branded_art.h")

# ICAO callsign prefix -> branded side-view render. Keyed by the 3-letter ICAO
# prefix the firmware derives from the live callsign (e.g. ASA -> Alaska).
BRANDED = {
    # US mainline narrow-body (737/A320)
    "AAL": "AmericanNarrowBodyClassic.png", # American
    "ASA": "AlaskanClassicNarrow.png",      # Alaska
    "DAL": "DeltaClassicNarrow.png",        # Delta
    "FFT": "FreontierClassicNarrow.png",    # Frontier
    "HAL": "HawwaiinClassicNarrow.png",     # Hawaiian
    "JBU": "JetBlueClassicNarrow.png",      # JetBlue
    "SWA": "SWClassicNarrow.png",           # Southwest
    "UAL": "UnitedClassicNarrow.png",       # United
    "AAY": "AlligeantClassic.png",          # Allegiant
    "MXY": "BreezeClassic.png",             # Breeze (callsign MOXY)
    "SCX": "SunCountryClassic.png",         # Sun Country
    "VOI": "VolarisClassic.png",            # Volaris
    "SKW": "SkywestReginalJet.png",         # SkyWest (regional jet)
    # Cargo
    "FDX": "FedExClassic.png",              # FedEx
    "UPS": "UPSClassic.png",                # UPS
    # International / wide-body
    "ACA": "AirCanadaClassic.png",          # Air Canada
    "THT": "AirTahitiNuiClassic.png",       # Air Tahiti Nui
    "LOT": "LotClassic.png",                # LOT Polish Airlines
    "ANA": "AnaJapan.png",                  # All Nippon Airways (ANA)
    "AAR": "AsainaAirlines.png",            # Asiana
    "CPA": "CathayPacific.png",             # Cathay Pacific
    "CAL": "ChinaAirlines.png",             # China Airlines (callsign DYNASTY)
    "CFG": "CondorAirplane.png",            # Condor
    "UAE": "EmaritesTwinAsile.png",         # Emirates
    "EVA": "EvaAir.png",                    # EVA Air
    "JAL": "JapanAirlines.png",             # Japan Airlines
    "KAL": "KoreanAir.png",                 # Korean Air
    "PAL": "Philipines.png",                # Philippine Airlines
    "SIA": "SignaporeDoubleDeck.png",       # Singapore Airlines
}

BG_THRESH = 244        # L >= this in the source is treated as background (white)


def process(path, box_w, box_h, gamma):
    """Source render -> (w, h, ink bool array) fitted inside the box."""
    g = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    bg = g >= BG_THRESH
    ink = ~bg

    # Crop to the plane. Use a density-based bbox, not raw min/max: a single
    # stray speck far from the fuselage (e.g. a lone dark pixel near the image
    # edge) would otherwise blow up the box and shrink the plane to fit. Keep
    # only rows/cols carrying a meaningful fraction of the peak ink count.
    row_ink, col_ink = ink.sum(axis=1), ink.sum(axis=0)
    rt, ct = row_ink.max() * 0.01, col_ink.max() * 0.01
    ys = np.where(row_ink > rt)[0]
    xs = np.where(col_ink > ct)[0]
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = g[y0:y1, x0:x1].astype(np.float32)
    cbg = bg[y0:y1, x0:x1]

    # Push midtones darker so the light-gray fuselage survives dithering on a
    # white panel; keep pure black/white ends fixed. Then re-whiten the bg.
    adj = 255.0 * np.power(np.clip(crop / 255.0, 0, 1), gamma)
    adj[cbg] = 255.0

    # Fit inside the box, preserving aspect ratio.
    ch, cw = adj.shape
    s = min(box_w / cw, box_h / ch)
    w, h = max(1, round(cw * s)), max(1, round(ch * s))
    im = Image.fromarray(adj.astype(np.uint8)).resize((w, h), Image.LANCZOS)

    # Floyd-Steinberg dither to 1bpp. PIL '1': 0=black, 255=white.
    d = np.asarray(im.convert("1"), dtype=np.uint8)
    ink = d == 0          # True = black ink (Adafruit drawBitmap sets 1 = draw)
    return w, h, ink


def pack_1bpp(ink):
    """Adafruit drawBitmap layout: rows byte-padded, MSB first, 1 = draw."""
    h, w = ink.shape
    rb = (w + 7) // 8
    out = bytearray(rb * h)
    for y in range(h):
        row = ink[y]
        for x in range(w):
            if row[x]:
                out[y * rb + (x >> 3)] |= 0x80 >> (x & 7)
    return bytes(out)


def carr(name, data):
    lines = [f"static const uint8_t {name}[] PROGMEM = {{"]
    for i in range(0, len(data), 12):
        lines.append("  " + "".join(f"0x{b:02X}," for b in data[i:i + 12]))
    lines.append("};")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box-w", type=int, default=540, help="max art width px")
    ap.add_argument("--box-h", type=int, default=224, help="max art height px")
    ap.add_argument("--gamma", type=float, default=2.0,
                    help="midtone darkening (>1 darkens the light fuselage)")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    entries = []   # (code, arr_name, w, h)
    blobs = []     # (arr_name, data)
    total = 0
    for code in sorted(BRANDED):
        fname = BRANDED[code]
        w, h, ink = process(os.path.join(IMG_DIR, fname), args.box_w,
                            args.box_h, args.gamma)
        arr_name = "branded_" + code.lower()
        entries.append((code, arr_name, w, h))
        blobs.append((arr_name, pack_1bpp(ink)))
        total += len(blobs[-1][1])
        if not args.no_preview:
            Image.fromarray((~ink * 255).astype(np.uint8)).save(
                os.path.join(PREVIEW_DIR, f"branded_{code}.png"))
        print(f"  {code}  {w:3d}x{h:<3d}  {fname}")

    out = ["// AUTO-GENERATED by tools/build_branded_art.py -- do not edit.",
           "// 1bpp branded airline liveries for the plane box, by ICAO prefix.",
           "#pragma once", "#include <stdint.h>", "#include <pgmspace.h>", "",
           "struct BrandedArt { const char* code; uint16_t w, h; "
           "const uint8_t* bits; };  // 1=black", ""]
    for arr_name, data in blobs:
        out.append(carr(arr_name, data))
    out.append("")
    out.append(f"static const BrandedArt BRANDED_ART[{len(entries)}] = {{")
    for code, arr_name, w, h in entries:
        out.append(f'  {{ "{code}", {w}, {h}, {arr_name} }},')
    out.append("};")
    out.append(f"static const size_t BRANDED_ART_N = {len(entries)};")
    out.append("")
    with open(OUT_H, "w") as f:
        f.write("\n".join(out))
    print(f"\nwrote {OUT_H}  ({total/1024:.1f} KB, {len(entries)} liveries)")


if __name__ == "__main__":
    main()
