#!/usr/bin/env python3
"""
Preview any UI design or picture on the emulated reTerminal E1001.

Drop in a PNG/JPG (a mockup, a screenshot, a photo) and see exactly how it will
look on the 7.5" 800x480 mono e-paper: converted to 1-bit, dithered like the
real panel, tinted with e-paper tones, and shown inside the device frame.

Usage:
    python3 preview.py mock.png                 # fit + dither (best for photos)
    python3 preview.py mock.png --fit fill      # crop to fill the screen
    python3 preview.py mock.png --fit stretch   # ignore aspect ratio
    python3 preview.py ui.png --threshold       # hard black/white (best for UI/line art)
    python3 preview.py ui.png --threshold 160   # custom cutoff (0-255)
    python3 preview.py mock.png --scale 2        # bigger preview
    python3 preview.py mock.png --bmp out.bmp    # also save the 800x480 1-bit BMP for the SD card

Output: <name>_e1001.png   (the mock device)  + optional 1-bit .bmp

Requires: Pillow  (pip install pillow)
"""

import os
import sys

from PIL import Image

from emulator import epaper_look, device_frame
from display import W, H  # 800 x 480

PAPER_L = 255  # letterbox fill = paper white (becomes e-paper paper tone later)


def to_panel(src_path, fit="fit", threshold=None):
    """Load any image and return a 1-bit 800x480 card, as the panel would show it.

    fit:        "fit" (letterbox, keep aspect), "fill" (crop), "stretch"
    threshold:  None -> Floyd-Steinberg dither (photos);
                int  -> hard cutoff at that gray level (UI / line art);
                True -> hard cutoff at 128.
    """
    img = Image.open(src_path).convert("L")  # grayscale first

    if fit == "stretch":
        img = img.resize((W, H), Image.LANCZOS)
    elif fit == "fill":
        # scale so the image covers 800x480, then center-crop
        scale = max(W / img.width, H / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.LANCZOS)
        left = (img.width - W) // 2
        top = (img.height - H) // 2
        img = img.crop((left, top, left + W, top + H))
    else:  # "fit" -> letterbox onto a paper-white canvas
        scale = min(W / img.width, H / img.height)
        new = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.LANCZOS)
        canvas = Image.new("L", (W, H), PAPER_L)
        canvas.paste(new, ((W - new.width) // 2, (H - new.height) // 2))
        img = canvas

    if threshold is None:
        # Floyd-Steinberg dithering -- exactly how e-paper renders photos.
        card = img.convert("1")
    else:
        cut = 128 if threshold is True else int(threshold)
        card = img.point(lambda p: 255 if p >= cut else 0).convert("1")
    return card


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python3 preview.py <image> [--fit fit|fill|stretch] "
              "[--threshold [N]] [--scale S] [--bmp out.bmp]")
        sys.exit(1)

    src = args[0]
    fit = "fit"
    threshold = None
    scale = 1.5
    bmp_out = None

    if "--fit" in args:
        fit = args[args.index("--fit") + 1]
    if "--scale" in args:
        scale = float(args[args.index("--scale") + 1])
    if "--bmp" in args:
        bmp_out = args[args.index("--bmp") + 1]
    if "--threshold" in args:
        i = args.index("--threshold")
        nxt = args[i + 1] if i + 1 < len(args) else ""
        threshold = int(nxt) if nxt.isdigit() else True

    card = to_panel(src, fit=fit, threshold=threshold)

    if bmp_out:
        card.save(bmp_out)  # true 1-bit 800x480, ready for the SD card / panel
        print(f"Wrote {bmp_out}  (1-bit 800x480 for the device)")

    screen = epaper_look(card)
    dev = device_frame(screen, scale=scale)
    out = os.path.splitext(os.path.basename(src))[0] + "_e1001.png"
    dev.save(out)
    mode = "dithered" if threshold is None else "threshold"
    print(f"Wrote {out}  (fit={fit}, {mode}, scale {scale}x) -- open it to preview.")


if __name__ == "__main__":
    main()
