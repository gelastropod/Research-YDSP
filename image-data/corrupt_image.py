#!/usr/bin/env python3
"""Corrupt square pixel regions of a PNG and write the result back to PNG.

Splits the image into -s sized squares and rewrites the ones selected with
-p (the square containing that pixel) or --all (every square). Modes:
random noise, black, or channel inversion.
"""
import argparse
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops


def damage(tile, mode, rng):
    if mode == "zero":
        return Image.new("RGBA", tile.size, (0, 0, 0, 255))
    if mode == "flip":
        flipped = ImageChops.invert(tile.convert("RGB"))
        flipped.putalpha(tile.getchannel("A"))
        return flipped
    noise = Image.frombytes("RGBA", tile.size, rng.randbytes(tile.width * tile.height * 4))
    noise.putalpha(tile.getchannel("A"))
    return noise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="source PNG")
    parser.add_argument("output", help="corrupted PNG")
    parser.add_argument("-p", "--pixel", action="append", default=[], metavar="X,Y",
                        help="corrupt the -s square containing this pixel (repeatable)")
    parser.add_argument("-s", "--size", type=int, default=4, metavar="N",
                        help="square side in pixels (default 4, one AES block's worth)")
    parser.add_argument("-a", "--all", action="store_true",
                        help="corrupt every -s square in the image")
    parser.add_argument("-m", "--mode", default="random",
                        choices=("random", "zero", "flip"),
                        help="how to rewrite each square (default random)")
    parser.add_argument("--seed", type=int, help="seed for repeatable 'random' edits")
    args = parser.parse_args()

    if args.size < 1:
        sys.exit("--size must be positive")
    if not args.pixel and not args.all:
        sys.exit("nothing to corrupt: pass -p X,Y or --all")

    rng = random.Random(args.seed)
    image = Image.open(args.input).convert("RGBA")
    width, height = image.size

    squares = set()
    for point in args.pixel:
        try:
            x, y = (int(v) for v in point.split(","))
        except ValueError:
            sys.exit(f"-p expects x,y integers, got {point!r}")
        if not (0 <= x < width and 0 <= y < height):
            sys.exit(f"pixel {point} outside the {width}x{height} image")
        squares.add(((x // args.size) * args.size, (y // args.size) * args.size))
    if args.all:
        squares.update((x0, y0) for y0 in range(0, height, args.size)
                       for x0 in range(0, width, args.size))

    for x0, y0 in squares:
        box = (x0, y0, min(x0 + args.size, width), min(y0 + args.size, height))
        image.paste(damage(image.crop(box), args.mode, rng), box)
        print(f"corrupted square at ({x0},{y0}), {box[2] - x0}x{box[3] - y0} pixels")

    image.save(args.output)
    print(f"{len(squares)} squares rewritten as '{args.mode}' -> {args.output}")


if __name__ == "__main__":
    main()
