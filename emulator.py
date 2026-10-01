#!/usr/bin/env python3
"""
reTerminal E1001 e-paper emulator.

Takes a 1-bit 800x480 card (from display.render_card) and shows it the way the
real device will look, so you can practice layouts before the hardware arrives:

  * E-PAPER LOOK  -- monochrome e-paper is not pure black/white. "White" is a
    warm gray paper; "black" is dark charcoal ink. We remap the 1-bit image to
    those tones so contrast on screen matches what you'll actually see.
  * DEVICE FRAME  -- the reTerminal E1001 is a 7.5" panel (800x480, 5:3) in a
    metal enclosure. We draw that bezel around the screen at a viewable scale.

Nothing here changes your card pipeline -- it reuses display.render_card and
just re-skins the result. The card you design is still the exact 800x480 1-bit
image that goes to the panel.

Usage:
    python3 emulator.py                 # demo card in the device frame
    python3 emulator.py --live          # nearest real plane (uses tracker.py)
    python3 emulator.py --scale 2       # bigger preview window/file

Output: e1001_preview.png  (open it to see the mock device)

Requires: Pillow  (pip install pillow)
"""

import sys

from PIL import Image, ImageDraw, ImageFont

from display import render_card, W, H  # W,H = 800,480 (the panel)

# ---- E-paper tones (measured-ish approximations of a mono 7.5" panel) -------
PAPER = (222, 221, 214)   # "white" -- warm, slightly gray paper
INK = (38, 40, 44)        # "black" -- dark charcoal, never pure #000

# ---- Enclosure tones (E1001 metal frame) -----------------------------------
METAL = (54, 56, 60)      # dark aluminium bezel
METAL_EDGE = (96, 99, 104)  # lighter chamfer highlight
SCREEN_INSET = (28, 29, 32)  # shadow gap between bezel and glass


def epaper_look(card_1bit):
    """Remap a mode-'1' card to RGB e-paper tones (paper + charcoal ink)."""
    # Point-map the single channel: 0 (ink) -> INK, 255 (paper) -> PAPER.
    src = card_1bit.convert("L")
    out = Image.new("RGB", src.size)
    px_src = src.load()
    px_out = out.load()
    for y in range(src.height):
        for x in range(src.width):
            px_out[x, y] = INK if px_src[x, y] < 128 else PAPER
    return out


def device_frame(screen_rgb, scale=1.5):
    """Wrap the screen image in a reTerminal E1001-style metal enclosure."""
    sw, sh = screen_rgb.size
    s = scale
    screen = screen_rgb.resize((int(sw * s), int(sh * s)), Image.NEAREST)
    scr_w, scr_h = screen.size

    bezel = int(46 * s)        # metal border around the glass
    gap = int(6 * s)           # dark inset gap (bezel -> glass)
    chin = int(30 * s)         # extra bezel at the bottom (branding strip)
    radius = int(28 * s)       # rounded enclosure corners

    dev_w = scr_w + 2 * (bezel + gap)
    dev_h = scr_h + 2 * (bezel + gap) + chin

    dev = Image.new("RGB", (dev_w, dev_h), METAL)
    d = ImageDraw.Draw(dev)

    # Rounded metal body with a lighter chamfer edge.
    d.rounded_rectangle([0, 0, dev_w - 1, dev_h - 1], radius=radius, fill=METAL)
    d.rounded_rectangle([int(2 * s), int(2 * s), dev_w - 1 - int(2 * s),
                         dev_h - 1 - int(2 * s)],
                        radius=radius, outline=METAL_EDGE, width=max(1, int(2 * s)))

    # Dark inset gap, then the screen.
    gx0, gy0 = bezel, bezel
    d.rectangle([gx0 - gap, gy0 - gap, gx0 + scr_w + gap, gy0 + scr_h + gap],
                fill=SCREEN_INSET)
    dev.paste(screen, (gx0, gy0))

    # Branding on the chin.
    label_y = gy0 + scr_h + gap + int(chin * 0.45)
    try:
        f = ImageFont.load_default(size=int(15 * s))
    except TypeError:
        f = ImageFont.load_default()
    d.text((dev_w // 2, label_y), "reTerminal  E1001   ·   7.5\"  800×480  mono",
           font=f, fill=METAL_EDGE, anchor="mm")

    return dev


def emulate(plane, scale=1.5, out="e1001_preview.png"):
    """Render the plane card and present it in the emulated E1001 device."""
    card = render_card(plane, "card_preview.png")   # true 800x480 1-bit
    screen = epaper_look(card)
    dev = device_frame(screen, scale=scale)
    dev.save(out)
    return out


def _nearest_live_plane():
    """Pull the closest real aircraft via tracker.collect_planes (needs net)."""
    import tracker
    planes = tracker.collect_planes(
        tracker.DEFAULT_LAT, tracker.DEFAULT_LON, tracker.DEFAULT_RADIUS_KM,
        limit=10, detail_budget=10,
    )
    return planes[0] if planes else None


if __name__ == "__main__":
    args = sys.argv[1:]
    live = "--live" in args
    scale = 1.5
    if "--scale" in args:
        scale = float(args[args.index("--scale") + 1])

    if live:
        plane = _nearest_live_plane()
        if not plane:
            print("No live aircraft found (OpenSky rate limit or empty sky).")
            sys.exit(0)
        print(f"Nearest: {plane.get('callsign')} {plane.get('type')} "
              f"{plane.get('dist')} km")
    else:
        plane = {
            "callsign": "AAL1933", "type": "B38M", "route": "MIA->ORD",
            "alt": 12000, "spd": 450, "track": 315, "ground": False, "dist": 6.1,
        }

    out = emulate(plane, scale=scale)
    print(f"Wrote {out}  (scale {scale}x) -- open it to see the mock E1001.")
