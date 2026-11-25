#!/usr/bin/env python3
"""Decorate the penguin PNG: close the left eye and draw a small heart
on the belly. Positions are constants below, tuned for the 64x64 testp.png.

Usage: decorate_penguin.py in.png out.png
"""
import sys

from PIL import Image, ImageDraw

EYE = (24, 15)          # left eye centre (x, y)
EYE_RX, EYE_RY = 5, 6   # eye oval half-extents
HEART = (32, 41)        # heart centre
HEART_R = 3             # heart lobe radius
HEART_COLOR = (220, 40, 70, 255)


def main():
    source, output = sys.argv[1], sys.argv[2]
    image = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Closed eye: fill the eye oval with head black, then a light lid curve.
    x, y = EYE
    draw.ellipse((x - EYE_RX, y - EYE_RY, x + EYE_RX, y + EYE_RY),
                 fill=(8, 8, 8, 255))
    draw.arc((x - 3, y - 1, x + 3, y + 5), start=0, end=180,
             fill=(190, 190, 190, 255), width=1)

    # Heart: two lobes plus a downward triangle.
    hx, hy, r = HEART + (HEART_R,)
    draw.ellipse((hx - r - 1, hy - r, hx, hy + r), fill=HEART_COLOR)
    draw.ellipse((hx, hy - r, hx + r + 1, hy + r), fill=HEART_COLOR)
    draw.polygon(((hx - r - 1, hy + r // 2 + 1),
                  (hx + r + 1, hy + r // 2 + 1),
                  (hx, hy + 2 * r + 2)), fill=HEART_COLOR)

    image.save(output)
    print(f"{source} -> {output}: closed eye at {EYE}, heart at {HEART}")


if __name__ == "__main__":
    main()
