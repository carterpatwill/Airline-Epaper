#!/usr/bin/env python3
"""
Build one contact sheet showing every base-plane image as the E1001 panel
would render it (1-bit, threshold, e-paper tones). Quick way to eyeball the
whole set at once.

Usage:
    python3 contact_sheet.py                 # -> base_models_sheet.png
"""

import glob
import os

from PIL import Image, ImageDraw, ImageFont

from preview import to_panel
from emulator import epaper_look

SRC_DIR = "plane-images"
CELL_W, CELL_H = 320, 192          # each thumbnail = 800x480 scaled to 40%
PAD = 18
LABEL_H = 26
COLS = 4


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def main():
    paths = sorted(
        p for p in glob.glob(os.path.join(SRC_DIR, "*.png"))
        if "_e1001" not in os.path.basename(p)          # skip stray previews
    )
    if not paths:
        print(f"No source PNGs in {SRC_DIR}/")
        return

    rows = (len(paths) + COLS - 1) // COLS
    sheet_w = COLS * CELL_W + (COLS + 1) * PAD
    sheet_h = rows * (CELL_H + LABEL_H) + (rows + 1) * PAD
    sheet = Image.new("RGB", (sheet_w, sheet_h), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    f = _font(18)

    for i, path in enumerate(paths):
        r, c = divmod(i, COLS)
        x = PAD + c * (CELL_W + PAD)
        y = PAD + r * (CELL_H + LABEL_H + PAD)

        # threshold works best for these flat black silhouettes
        card = to_panel(path, fit="fit", threshold=True)
        thumb = epaper_look(card).resize((CELL_W, CELL_H), Image.NEAREST)
        sheet.paste(thumb, (x, y))
        d.rectangle([x, y, x + CELL_W - 1, y + CELL_H - 1],
                    outline=(120, 120, 120), width=1)

        name = os.path.splitext(os.path.basename(path))[0]
        d.text((x + CELL_W // 2, y + CELL_H + LABEL_H // 2), name,
               font=f, fill=(30, 30, 30), anchor="mm")

    out = "base_models_sheet.png"
    sheet.save(out)
    print(f"Wrote {out}  ({len(paths)} images, {COLS}x{rows} grid)")


if __name__ == "__main__":
    main()
