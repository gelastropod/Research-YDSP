# Hilbert-order image tools

Build with `make` (POSIX and a C11 compiler; the stb headers are included).

```sh
./pad_image --fit short photo.png padded.png
./encode padded.png image.bin
./decode image.bin image.bin.meta reconstructed.png
```

`pad_image [--fit short|long] [-s N] [--transparent] in.png out.png` preserves the aspect ratio, centers the image, and fills the border with opaque white by default. Use `--transparent` for a transparent border. Neither option flattens the image's existing transparency.

The default `--fit short` scales the short edge to the nearest power of two, then pads the long edge to a multiple of it. `--fit long` instead scales the long edge to the nearest power of two and pads the short edge up to a power of two. Both round ties up, use a minimum power-of-two edge of 4, and put any extra padding pixel on the right or bottom. Use `-s N` to set the selected edge to exactly `N` pixels (a power of two of at least 4). For example, `-s 512` sizes the short edge to 512 pixels by default; `--fit long -s 512` sizes the long edge instead. Neither fit crops the image.

`encode [-q ycc|bc3|rgba] padded.png out.bin` never resizes: the PNG's short side must already be a power of two of at least 4 and its long side must be a multiple of the short side.

| Format | Raw payload | Decoded result |
| --- | --- | --- |
| `ycc` (default) | 16 bytes per 4×4 square | Lossy JPEG-style YCbCr sampling, **fully opaque** (including padding) |
| `bc3` | 16 bytes per 4×4 square | Lossy BC3/DXT5 color and alpha |
| `rgba` | 4 bytes per pixel | Exact 8-bit RGBA, including padding |

YCC and BC3 binaries are 75% smaller than RGBA for the same canvas. YCC is not JPEG: each 4×4 record holds two 2×4 halves (left, then right), each storing `Y0 Y1 Y2 Y3 Cb0 Cb1 Cr0 Cr1`. Y is averaged per row of two pixels; each chroma sample is averaged over a 2×2 square. YCC ignores alpha, so even a transparent pixel's RGB contributes to the samples.

The binary is headerless. Records follow connected Hilbert tiles arranged along the long axis. The companion `out.bin.meta` is one text line, e.g. `1024 512 ycc` (width, height, format). Keep that file unchanged when modifying the binary. `decode in.bin in.bin.meta out.png` restores the full padded canvas as PNG.

## Edit a block

```sh
# Find the 16-byte block containing pixel (120,180).
./modify_block -M image.bin.meta -p 120,180

# Zero that block in a copy, then view the result.
./modify_block -m zero -M image.bin.meta -p 120,180 image.bin changed.bin
./decode changed.bin image.bin.meta changed.png

# Or select a range by index instead of by pixel.
./modify_block -b 4096 -m flip image.bin changed.bin 3,8-10
```

`-b` sets block size in **bytes**, default 16. Coordinates and block indices are zero-based, ranges are inclusive, and the same input and output path edits in place. Modes are `random` (default), `zero`, `flip`, and `fill:HH` (one hex byte). Pixel lookup uses the block containing the first byte of that pixel's encoded record. For YCC and BC3, one 16-byte block maps to one 4×4 square; an aligned 4,096-byte block maps to a 64×64 square when the Hilbert tile is at least 64 pixels wide. You can also edit the binary with your own script and decode it with the same metadata.

`make test` uses Python 3 and Pillow to check padding, each format, and block locality.
