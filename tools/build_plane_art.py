#!/usr/bin/env python3
"""
Turn the grayscale 3D plane renders in _Planes/ into e-paper-ready
1bpp bitmaps sized to the card's plane box, and emit them as a C header the
firmware blits directly.

Unlike tools/build_silhouettes.py (which fakes windows/outline onto a SOLID-black
silhouette), these source images are already detailed light-gray renders on a
white background. So we just: clean the background to pure white, push the
midtones darker (a light fuselage on a white panel would otherwise vanish),
crop to the plane, fit it into the box, and Floyd-Steinberg dither to 1bpp so
the gray shading reads as texture on the black/white (GxEPD2_BW) panel.

Output:
  firmware/src/generated/gen_plane_art.h   PLANE_ART[] indexed by AcBase id (1..14)

Run from the repo root:
    python3 tools/build_plane_art.py
    python3 tools/build_plane_art.py --box-w 456 --box-h 224 --gamma 2.0
"""
import argparse, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "_Planes")
PREVIEW_DIR = os.path.join(IMG_DIR, "preview")
OUT_H = os.path.join(ROOT, "firmware", "src", "generated", "gen_plane_art.h")

# AcBase id (see firmware/src/generated/gen_aircraft_types.h) -> source render.
BASE_ART = {
    1:  ("Classic narrow-body",     "ClassicNarrowBody.png"),
    2:  ("Small narrow-body",       "SmallerNarrowBody.png"),
    3:  ("Regional jet",            "RegionalJet.png"),
    4:  ("Turboprop",               "TurboProp.png"),
    5:  ("Twin-aisle wide-body",    "TwinAsile.png"),
    6:  ("Four-engine wide-body",   "4enginewidebody.png"),
    7:  ("Tri-jet",                 "TriJet.png"),
    8:  ("Jumbo (hump)",            "Jumbo.png"),
    9:  ("Double-deck",             "DoubleDecker.png"),
    10: ("Business jet",            "BussniessJet.png"),
    11: ("Cargo / freighter",       "Cargo.png"),
    12: ("Piston / light",          "Piston.png"),
    13: ("Seaplane / floatplane",   "Seaplane.png"),
    14: ("Prop airliner / vintage", "PropVintage.png"),
    15: ("Helicopter",              "Helicopter.png"),
}
N_BASES = 16   # index 0 (unknown) .. 15

BG_THRESH = 244        # L >= this in the source is treated as background (white)


def process(path, box_w, box_h, gamma):
    """Source render -> (w, h, ink bool array) fitted inside the box."""
    g = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    bg = g >= BG_THRESH

    # Crop to the plane (everything that isn't background).
    ys, xs = np.where(~bg)
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
    ap.add_argument("--box-h", type=int, default=232, help="max art height px")
    ap.add_argument("--gamma", type=float, default=2.0,
                    help="midtone darkening (>1 darkens the light fuselage)")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    os.makedirs(PREVIEW_DIR, exist_ok=True)

    # De-dupe: several base ids can share one render (reuse the same C array).
    emitted = {}   # filename -> (arr_name, w, h)
    entries = {}   # base_id -> (arr_name, w, h)
    total = 0
    for bid, (name, fname) in sorted(BASE_ART.items()):
        if fname not in emitted:
            w, h, ink = process(os.path.join(IMG_DIR, fname), args.box_w,
                                 args.box_h, args.gamma)
            arr_name = "art_" + os.path.splitext(fname)[0].lower()
            emitted[fname] = (arr_name, w, h, pack_1bpp(ink))
            total += len(emitted[fname][3])
            if not args.no_preview:
                Image.fromarray((~ink * 255).astype(np.uint8)).save(
                    os.path.join(PREVIEW_DIR, f"base_{bid:02d}_{arr_name}.png"))
        arr_name, w, h, _ = emitted[fname]
        entries[bid] = (arr_name, w, h)
        print(f"  base {bid:2d}  {w:3d}x{h:<3d}  {name}  <- {fname}")

    out = ["// AUTO-GENERATED by tools/build_plane_art.py -- do not edit.",
           "// 1bpp dithered plane art from _Planes/, by AcBase id.",
           "#pragma once", "#include <stdint.h>", "#include <pgmspace.h>", "",
           "struct PlaneArt { uint16_t w, h; const uint8_t* bits; };  // 1=black",
           f"static const uint8_t N_PLANE_ART = {N_BASES};", ""]
    for fname, (arr_name, w, h, data) in emitted.items():
        out.append(f"// {fname}  ({w}x{h})")
        out.append(carr(arr_name, data))
        out.append("")

    out.append(f"static const PlaneArt PLANE_ART[{N_BASES}] = {{")
    for bid in range(N_BASES):
        e = entries.get(bid)
        if e is None:
            out.append("  { 0, 0, nullptr },")
        else:
            arr_name, w, h = e
            out.append(f"  {{ {w}, {h}, {arr_name} }},  // {BASE_ART[bid][0]}")
    out.append("};")
    out.append("")
    out.append(f"static const char* const PLANE_ART_NAME[{N_BASES}] = {{")
    for bid in range(N_BASES):
        name = BASE_ART[bid][0] if bid in BASE_ART else "Unknown"
        out.append(f'  "{name}",')
    out.append("};")
    out.append("")
    with open(OUT_H, "w") as f:
        f.write("\n".join(out))
    print(f"\nwrote {OUT_H}  ({total/1024:.1f} KB of bitmap data)")
    if not args.no_preview:
        print(f"previews -> {PREVIEW_DIR}/")


if __name__ == "__main__":
    main()
