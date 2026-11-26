#!/usr/bin/env python3
"""Scale a PNG up by an integer multiplier using nearest-neighbour
sampling, so every source pixel becomes a solid NxN square.

Usage: expand_image.py in.png out.png -m 4
"""
import argparse
import sys

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("-m", "--multiplier", type=int, default=4,
                        help="integer scale factor (default 4)")
    args = parser.parse_args()
    if args.multiplier < 1:
        sys.exit("-m must be a positive integer")

    image = Image.open(args.source)
    size = (image.width * args.multiplier, image.height * args.multiplier)
    image.resize(size, Image.Resampling.NEAREST).save(args.output)
    print(f"{args.source} -> {args.output}: {image.width}x{image.height} "
          f"-> {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
