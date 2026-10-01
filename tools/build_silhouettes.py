#!/usr/bin/env python3
"""
Turn the solid-black plane silhouettes in plane-images/ into e-paper-ready
artwork: a black OUTLINE + light-gray body FILL + a window STRIPE + a cockpit
tick, sized for the 800x480 panel. The airline tail logo and the registration
text are NOT baked in -- the firmware blits those at runtime into the per-model
`tail` / `text` boxes this script records.

Outputs:
  firmware/src/generated/gen_silhouettes.h   arrays + Silhouette[] indexed by AcBase id
  plane-images/preview/*.png       upscaled previews (fill/lines/boxes) to tune

Two bitmaps per model live in the header:
  .bits  1bpp, Adafruit_GFX drawBitmap format (1 = black ink). Works with the
         current GxEPD2_BW firmware TODAY; the gray body is ordered-dithered.
  .gray  2bpp packed, 0=black 1=darkgray 2=lightgray 3=white. For when the
         firmware switches to Seeed's 4-gray (Gray4) display class. Omit with
         --no-gray4 to shrink the header.

Boxes (.tail/.text) are pixel offsets WITHIN the silhouette bitmap, so the
firmware adds the silhouette's on-screen origin.

Everything visual is tuned in SPEC below -- run, eyeball plane-images/preview/,
adjust the fractions, re-run. Fractions are relative to the silhouette bbox.

Run from the repo root:
    python3 tools/build_silhouettes.py
    python3 tools/build_silhouettes.py --height 130 --stroke 2
"""
import argparse, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "plane-images")
PREVIEW_DIR = os.path.join(IMG_DIR, "preview")
OUT_H = os.path.join(ROOT, "firmware", "src", "generated", "gen_silhouettes.h")

sys.path.insert(0, ROOT)
from base_models import BASE_IMAGE  # base name -> filename  # noqa: E402

# base id 1..14 in the SAME order the firmware enum uses (index+1).
BASE_ORDER = list(BASE_IMAGE.keys())
BASE_ID = {name: i + 1 for i, name in enumerate(BASE_ORDER)}

# 4-gray levels (index -> friendly). 0 darkest.
BLACK, DARKGRAY, LIGHTGRAY, WHITE = 0, 1, 2, 3
GRAY_TO_8BIT = {BLACK: 0, DARKGRAY: 96, LIGHTGRAY: 192, WHITE: 255}

# ---------------------------------------------------------------------------
# Per-model tuning. Window/cockpit/text hug the detected FUSELAGE tube, so their
# numbers don't have to fight the tall tail fin. Tune against plane-images/preview/.
#   flip    : mirror horizontally (normalize so it reads consistently)
#   nose    : 'auto' | 'L' | 'R' -- fin is auto-detected; override if it guesses wrong
#   fill    : 'light' (gray body) | 'none' (hollow outline only)
#   window  : (x0, x1, drop, thick) as fractions -- x span of the bbox, then the
#             stripe's drop below the local fuselage-top and its thickness as
#             fractions of FUSELAGE height. None = no cabin windows.
#   cockpit : draw the windshield mark just aft of the nose
#   tail    : (x,y,w,h) bbox fractions for the logo box, or None = auto onto the fin
#   text    : (x,y,w,h) bbox fractions for the reg box, or None = auto onto the tube
# ---------------------------------------------------------------------------
DEF_WINDOW = (0.16, 0.72, 0.16, 0.20)
SPEC = {
    "Classic narrow-body":     dict(window=DEF_WINDOW),
    "Small narrow-body":       dict(window=(0.18, 0.70, 0.16, 0.20)),
    "Regional jet":            dict(window=(0.20, 0.68, 0.16, 0.20)),
    "Turboprop":               dict(window=(0.22, 0.66, 0.16, 0.20)),
    "Twin-aisle wide-body":    dict(window=(0.14, 0.74, 0.15, 0.22)),
    "Four-engine wide-body":   dict(window=(0.14, 0.74, 0.15, 0.22)),
    "Tri-jet":                 dict(window=(0.16, 0.70, 0.16, 0.20)),
    "Jumbo (hump)":            dict(window=(0.14, 0.74, 0.15, 0.20)),
    "Double-deck":             dict(window=(0.14, 0.76, 0.14, 0.30)),
    "Business jet":            dict(window=(0.34, 0.62, 0.18, 0.16), cockpit=False),
    "Cargo / freighter":       dict(window=None),   # freighters: no cabin windows
    "Piston / light":          dict(window=None, cockpit=False),   # art already has windows
    "Seaplane / floatplane":   dict(window=None, cockpit=False),   # art already has windows
    "Prop airliner / vintage": dict(window=(0.18, 0.70, 0.16, 0.22)),
}
# Every source image faces nose-LEFT / tail-RIGHT, so pin it (auto-detect trips
# on the tall propeller disc of the prop types). Flip here if you swap art.
SPEC_DEFAULTS = dict(flip=False, nose='L', fill='light',
                     window=DEF_WINDOW, cockpit=True, tail=None, text=None)

# 4x4 Bayer matrix (0..15) for ordered dithering of the gray body in 1bpp mode.
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0
LIGHT_DENSITY = 0.34   # fraction of body pixels inked when faking light gray in BW


def load_mask(path, max_w, max_h):
    """Solid black-on-white PNG -> cropped mask fit inside (max_w, max_h)."""
    g = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    mask = g < 128
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError(f"{path}: no dark pixels found")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = mask[y0:y1, x0:x1]
    ch, cw = crop.shape
    s = min(max_w / cw, max_h / ch)
    w, h = max(1, round(cw * s)), max(1, round(ch * s))
    # Resize via a float image + LANCZOS, then re-threshold to a clean edge.
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    return np.asarray(im, dtype=np.uint8) >= 128


def detect_nose(mask):
    """Tail fin is the tall bit at one extreme end; the nose is the other end."""
    w = mask.shape[1]
    band = max(1, w // 7)
    left = mask[:, :band].sum(axis=0).max()
    right = mask[:, -band:].sum(axis=0).max()
    return 'L' if right >= left else 'R'   # taller end = tail -> nose opposite


def fuselage_band(mask):
    """Median top/bottom of the tube across the central x -- excludes the fin."""
    h, w = mask.shape
    tops, bots = [], []
    for x in range(int(0.35 * w), int(0.65 * w)):
        col = np.where(mask[:, x])[0]
        if len(col):
            tops.append(col[0]); bots.append(col[-1])
    if not tops:
        return 0, h - 1
    return int(np.median(tops)), int(np.median(bots))


def frac_box(spec_box, w, h):
    x, y, bw, bh = spec_box
    return (round(x * w), round(y * h), round(bw * w), round(bh * h))


def build(mask, spec, stroke):
    """Return (gray image 0..3, tail_box px, text_box px)."""
    h, w = mask.shape
    eroded = ndimage.binary_erosion(mask, iterations=stroke)
    outline = mask & ~eroded
    top, bot = fuselage_band(mask)
    fh = max(1, bot - top)
    nose = spec['nose'] if spec['nose'] != 'auto' else detect_nose(mask)

    gray = np.full((h, w), WHITE, dtype=np.uint8)
    if spec['fill'] == 'light':
        gray[eroded] = LIGHTGRAY

    def stripe(x0f, x1f, dropf, thf, taller=0.0):
        """Dark band that follows each column's own fuselage-top edge."""
        band = np.zeros((h, w), dtype=bool)
        drop = round(dropf * fh)
        th = max(1, round((thf + taller) * fh))
        for x in range(round(x0f * w), round(x1f * w)):
            col = np.where(mask[:, x])[0]
            if not len(col):
                continue
            ya = col[0] + drop
            band[max(0, ya):ya + th, x] = True
        gray[band & eroded] = BLACK

    # Cabin window stripe.
    if spec['window'] is not None:
        stripe(*spec['window'])

    # Cockpit windshield: a slightly taller mark just aft of the nose.
    if spec['cockpit']:
        cols = np.where(mask.any(axis=0))[0]
        if len(cols):
            if nose == 'R':
                x0f, x1f = (cols.max() - 0.09 * w) / w, (cols.max() - 0.03 * w) / w
            else:
                x0f, x1f = (cols.min() + 0.03 * w) / w, (cols.min() + 0.09 * w) / w
            stripe(x0f, x1f, 0.06, 0.30)

    gray[outline] = BLACK   # outline always on top

    # Auto boxes (fractions in SPEC override). Tail -> fin end; text -> tube.
    tail_right = (nose == 'L')
    if spec['tail'] is not None:
        tail = frac_box(spec['tail'], w, h)
    else:
        tw = round(0.22 * w)
        tail = (w - tw if tail_right else 0, 0, tw, top + round(0.15 * fh))
    if spec['text'] is not None:
        text = frac_box(spec['text'], w, h)
    else:
        tx = round(0.34 * w)
        text = (tx, top + round(0.34 * fh), round(0.34 * w), round(0.5 * fh))
    return gray, tail, text


def to_bits_1bpp(gray, density=LIGHT_DENSITY):
    """Flatten gray (0..3) to 1bpp ink mask: lines solid, light body dithered."""
    h, w = gray.shape
    ink = gray == BLACK
    body = gray == LIGHTGRAY
    if body.any():
        yy, xx = np.mgrid[0:h, 0:w]
        thresh = BAYER4[yy % 4, xx % 4]
        ink = ink | (body & (thresh < density))
    dark = gray == DARKGRAY
    if dark.any():
        yy, xx = np.mgrid[0:h, 0:w]
        thresh = BAYER4[yy % 4, xx % 4]
        ink = ink | (dark & (thresh < 0.6))
    return ink


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
    return bytes(out), rb


def pack_2bpp(gray):
    """2 bits/px, 4 px/byte, MSB first, rows byte-padded. value 0..3."""
    h, w = gray.shape
    rb = (w + 3) // 4
    out = bytearray(rb * h)
    for y in range(h):
        for x in range(w):
            shift = 6 - 2 * (x & 3)
            out[y * rb + (x >> 2)] |= (int(gray[y, x]) & 3) << shift
    return bytes(out), rb


def carr(name, data):
    lines = [f"static const uint8_t {name}[] = {{"]
    for i in range(0, len(data), 12):
        lines.append("  " + "".join(f"0x{b:02X}," for b in data[i:i + 12]))
    lines.append("};")
    return "\n".join(lines)


def save_preview(gray, tail, text, scale, path):
    h, w = gray.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for lvl, v in GRAY_TO_8BIT.items():
        rgb[gray == lvl] = v
    im = Image.fromarray(rgb).resize((w * scale, h * scale), Image.NEAREST).convert("RGB")
    px = im.load()

    def rect(box, color):
        x, y, bw, bh = box
        for xx in range(x, min(x + bw, w)):
            for yy in (y, min(y + bh, h) - 1):
                if 0 <= yy < h:
                    for sy in range(scale):
                        for sx in range(scale):
                            px[xx * scale + sx, yy * scale + sy] = color
        for yy in range(y, min(y + bh, h)):
            for xx in (x, min(x + bw, w) - 1):
                if 0 <= xx < w:
                    for sy in range(scale):
                        for sx in range(scale):
                            px[xx * scale + sx, yy * scale + sy] = color
    rect(tail, (220, 40, 40))    # red = tail-logo box
    rect(text, (40, 120, 220))   # blue = registration box
    im.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=360,
                    help="max silhouette width px (fits the card slot)")
    ap.add_argument("--max-height", type=int, default=130,
                    help="max silhouette height px (dashboard caps at 130)")
    ap.add_argument("--stroke", type=int, default=2, help="outline thickness px")
    ap.add_argument("--no-gray4", action="store_true", help="skip 2bpp gray arrays")
    ap.add_argument("--preview-scale", type=int, default=3)
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    entries = {}   # base_id -> dict of emitted names/metadata
    for name, fname in BASE_IMAGE.items():
        bid = BASE_ID[name]
        spec = dict(SPEC_DEFAULTS)
        spec.update(SPEC.get(name, {}))
        path = os.path.join(IMG_DIR, fname)
        mask = load_mask(path, args.width, args.max_height)
        if spec['flip']:
            mask = mask[:, ::-1]
        gray, tail, text = build(mask, spec, args.stroke)
        h, w = gray.shape

        ink = to_bits_1bpp(gray)
        bits, _ = pack_1bpp(ink)
        g4 = None if args.no_gray4 else pack_2bpp(gray)[0]
        entries[bid] = dict(name=name, w=w, h=h, bits=bits, g4=g4,
                            tail=tail, text=text)
        if not args.no_preview:
            slug = "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()
            save_preview(gray, tail, text, args.preview_scale,
                         os.path.join(PREVIEW_DIR, f"base_{bid:02d}_{slug}.png"))
        print(f"  base {bid:2d}  {w:3d}x{h:<3d}  {name}")

    # ---- emit header ----
    n = max(entries) + 1
    out = []
    out.append("// AUTO-GENERATED by tools/build_silhouettes.py -- do not edit.")
    out.append("// Outlined 4-gray plane silhouettes, indexed by AcBase id.")
    out.append("#pragma once")
    out.append("#include <stdint.h>")
    out.append("")
    out.append("struct SilBox { int16_t x, y, w, h; };   // offset within the silhouette")
    out.append("struct Silhouette {")
    out.append("  uint16_t w, h;")
    out.append("  const uint8_t* bits;   // 1bpp Adafruit drawBitmap (1=black). BW firmware.")
    out.append("  const uint8_t* gray;   // 2bpp 0=black..3=white, or nullptr. Gray4 firmware.")
    out.append("  SilBox tail;           // blit the airline tail logo here")
    out.append("  SilBox text;           // write the registration here")
    out.append("};")
    out.append("")
    for bid in sorted(entries):
        e = entries[bid]
        out.append(f"// base {bid}: {e['name']}  ({e['w']}x{e['h']})")
        out.append(carr(f"sil_{bid}_bits", e['bits']))
        if e['g4'] is not None:
            out.append(carr(f"sil_{bid}_gray", e['g4']))
        out.append("")

    out.append(f"static const Silhouette SILHOUETTES[{n}] = {{")
    for bid in range(n):
        e = entries.get(bid)
        if e is None:
            out.append("  { 0, 0, nullptr, nullptr, {0,0,0,0}, {0,0,0,0} },")
            continue
        g = f"sil_{bid}_gray" if e['g4'] is not None else "nullptr"
        t, x = e['tail'], e['text']
        out.append(f"  {{ {e['w']}, {e['h']}, sil_{bid}_bits, {g}, "
                   f"{{{t[0]},{t[1]},{t[2]},{t[3]}}}, "
                   f"{{{x[0]},{x[1]},{x[2]},{x[3]}}} }},  // {e['name']}")
    out.append("};")
    out.append("")
    with open(OUT_H, "w") as f:
        f.write("\n".join(out))
    print(f"\nwrote {OUT_H}")
    if not args.no_preview:
        print(f"previews -> {PREVIEW_DIR}/  (red box = tail logo, blue = registration)")


if __name__ == "__main__":
    main()
