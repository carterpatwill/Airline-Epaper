#!/usr/bin/env python3
"""
Turn the airline wordmark logos in _AirplaneLogos/*.png into e-paper-ready 1bpp
bitmaps for the card header, keyed by the airline's ICAO callsign prefix (the
same 3-letter prefix the firmware already derives from the live callsign, e.g.
AAL -> American). The wordmarks are dark ink on white/transparent, so a simple
luminance threshold gives clean black text (no dithering needed).

Output:
  firmware/src/generated/gen_airline_logos.h   AIRLINE_LOGOS[] sorted by ICAO prefix

Run from the repo root:
    python3 tools/build_airline_logos.py
    python3 tools/build_airline_logos.py --height 30 --max-width 170
"""
import argparse, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_DIR = os.path.join(ROOT, "_AirplaneLogos")
PREVIEW_DIR = os.path.join(LOGO_DIR, "preview")
OUT_H = os.path.join(ROOT, "firmware", "src", "generated", "gen_airline_logos.h")

# ICAO callsign prefix -> wordmark file. Prefer the horizontal wordmark (which
# already contains the airline name) over the square *Tail.png variants.
LOGOS = {
    "ACA": "AirCanada.png",
    "AFR": "AirFrance.png",
    "THT": "Air-Tahiti-Nui-Logo.png",
    "LOT": "LOT_Polish_Airlines-Logo.wine.png",
    "CAO": "AirchinaCargo.png",
    "AAY": "Alleigant.png",
    "ASA": "Alaska.png",
    "AAL": "American.png",
    "ANA": "AnaJapan.png",
    "AAR": "AsianaAirlines.png",
    "GTI": "AtlasAir.png",
    "MXY": "Breeze.png",
    "BAW": "Brittish.png",
    "CPA": "Cathy.png",
    "CAL": "ChinaAirlines.png",
    "CFG": "Condor.png",
    "DAL": "Delta.png",
    "UAE": "Emarates.png",
    "EDV": "Endavours.png",
    "ENY": "Envoy.png",
    "EVA": "EvaAir.png",
    "FDX": "FedEx.png",
    "FFT": "Fronteir.png",
    "GJS": "GoJet.png",
    "HAL": "Hawwain.png",
    "QXE": "HorizonAir.png",
    "JAL": "JapanAirlines.png",
    "JBU": "JetBlue.png",
    "KAL": "Korean Air.png",
    "ASH": "Mesa.png",
    "PAL": "PhilipinesAirlines.png",
    "RPA": "Republic.png",
    "KLM": "RoyalDutch.png",
    "SIA": "SingaporeAirlines.png",
    "SKW": "SkyWest.png",
    "SWA": "SouthWest.png",
    "SCX": "Suncounty.png",
    "THY": "TurkishAirlines.png",
    "UPS": "UPS.png",
    "UAL": "United.png",
    "VOI": "Volaris.png",
    "WJA": "WestJet.png",
    "DLH": "lufsana.png",
}

THRESH = 170     # composited luminance below this = black ink (opaque-bg logos)
ALPHA_THRESH = 128  # opacity above this = ink (transparent-bg logos)


def process(path, height, max_width):
    """Wordmark PNG -> (w, h, ink bool array) at the target header height.

    Most wordmarks sit on a transparent background, so the shape we want to ink
    is simply the opaque region -- use the alpha channel. This is essential for
    light/silver wordmarks (e.g. Mesa's "MESA") whose luminance is above THRESH
    and would otherwise vanish on the white panel. Only fall back to a luminance
    threshold for logos with a solid (opaque) background, where alpha carries no
    shape information.
    """
    im = Image.open(path).convert("RGBA")
    rgba = np.asarray(im)
    alpha = rgba[..., 3]
    if (alpha < 20).mean() > 0.1:          # has a transparent background
        ink = alpha >= ALPHA_THRESH
    else:                                  # opaque/white background -> use luminance
        rgb = rgba[..., :3].astype(np.float32)
        lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        ink = lum < THRESH

    ys, xs = np.where(ink)
    if len(xs) == 0:
        raise ValueError(f"{path}: no ink found")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = ink[y0:y1, x0:x1]

    ch, cw = crop.shape
    s = min(height / ch, max_width / cw)
    w, h = max(1, round(cw * s)), max(1, round(ch * s))
    # Downscale the ink mask with LANCZOS then re-threshold for a clean edge.
    im2 = Image.fromarray((crop * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    return w, h, np.asarray(im2, dtype=np.uint8) >= 110


def pack_1bpp(ink):
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
    ap.add_argument("--height", type=int, default=60, help="logo height px")
    ap.add_argument("--max-width", type=int, default=320, help="max logo width px")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    entries = []   # (code, arr_name, w, h)
    blobs = []     # (arr_name, data)
    total = 0
    for code in sorted(LOGOS):
        fname = LOGOS[code]
        w, h, ink = process(os.path.join(LOGO_DIR, fname), args.height, args.max_width)
        arr_name = "logo_" + code.lower()
        entries.append((code, arr_name, w, h))
        blobs.append((arr_name, pack_1bpp(ink)))
        total += len(blobs[-1][1])
        if not args.no_preview:
            Image.fromarray((~ink * 255).astype(np.uint8)).save(
                os.path.join(PREVIEW_DIR, f"logo_{code}.png"))
        print(f"  {code}  {w:3d}x{h:<3d}  {fname}")

    out = ["// AUTO-GENERATED by tools/build_airline_logos.py -- do not edit.",
           "// 1bpp airline wordmarks for the header, sorted by ICAO prefix.",
           "#pragma once", "#include <stdint.h>", "#include <pgmspace.h>", "",
           "struct AirlineLogo { const char* code; uint16_t w, h; "
           "const uint8_t* bits; };", ""]
    for arr_name, data in blobs:
        out.append(carr(arr_name, data))
    out.append("")
    out.append(f"static const AirlineLogo AIRLINE_LOGOS[{len(entries)}] = {{")
    for code, arr_name, w, h in entries:
        out.append(f'  {{ "{code}", {w}, {h}, {arr_name} }},')
    out.append("};")
    out.append(f"static const size_t AIRLINE_LOGOS_N = {len(entries)};")
    out.append("")
    with open(OUT_H, "w") as f:
        f.write("\n".join(out))
    print(f"\nwrote {OUT_H}  ({total/1024:.1f} KB, {len(entries)} logos)")


if __name__ == "__main__":
    main()
