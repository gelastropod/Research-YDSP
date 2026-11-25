#!/usr/bin/env python3
"""Pixel-wise diff of two images: writes a visualization and prints stats.

Modes:
  abs       absolute per-channel difference (identical regions are black)
  mask      black/white: white where any channel differs
  highlight dimmed first image with differences tinted red

Prints the count, maximum channel difference, RMSE, and the bounding box of
all differing pixels (useful to check edits stayed inside a block).
"""
import argparse
import math
import sys

from PIL import Image, ImageChops, ImageEnhance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", help="reference image")
    parser.add_argument("second", help="image to compare")
    parser.add_argument("output", help="diff visualization PNG")
    parser.add_argument("-m", "--mode", default="abs",
                        choices=("abs", "mask", "highlight"))
    parser.add_argument("--gain", type=float, default=1.0,
                        help="brightness multiplier for abs mode (default 1)")
    args = parser.parse_args()

    first = Image.open(args.first).convert("RGB")
    second = Image.open(args.second).convert("RGB")
    if first.size != second.size:
        sys.exit(f"size mismatch: {first.size} vs {second.size}")
    width, height = first.size

    diff = ImageChops.difference(first, second)
    nonzero = diff.convert("L").point(lambda v: 255 if v else 0)
    histogram = diff.histogram()          # 256 bins per channel, RGBA order
    gray_hist = nonzero.histogram()       # L: bin 255 = differing pixels

    changed = gray_hist[255]
    max_diff = max(diff.getextrema(), key=lambda t: t[1])[1]
    sum_sq = sum(v * v * count
                 for channel in range(3)
                 for v, count in enumerate(histogram[channel * 256:(channel + 1) * 256]))
    rmse = math.sqrt(sum_sq / (width * height * 3))
    bbox = nonzero.getbbox()

    if args.mode == "mask":
        visual = nonzero.convert("RGB")
    elif args.mode == "highlight":
        dim = ImageEnhance.Brightness(first).enhance(0.4)
        red = Image.new("RGB", dim.size, (255, 0, 0))
        visual = Image.composite(red, dim, nonzero)
    else:
        if args.gain != 1.0:
            diff = diff.point(lambda v: min(255, int(v * args.gain)))
        visual = diff

    visual.save(args.output)
    print(f"{width}x{height}: {changed} pixels differ "
          f"({100.0 * changed / (width * height):.2f}%), "
          f"max channel diff {max_diff}, RMSE {rmse:.2f}")
    if bbox:
        x0, y0, x1, y1 = bbox
        print(f"difference bounding box: ({x0},{y0})-({x1 - 1},{y1 - 1}), "
              f"{x1 - x0}x{y1 - y0} pixels")
    else:
        print("images are identical")


if __name__ == "__main__":
    main()
