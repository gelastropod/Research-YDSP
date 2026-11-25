# Hilbert-order images for an AES-XTS demo

Build the C tools with `make` (POSIX and a C11 compiler). The stb image loader, resizer, PNG writer, and BC3 encoder are vendored.

```sh
./img2hilbert photo.jpg image.bin
./hilbert2img image.bin image.bin.meta before.png

# Run your own encryption script on image.bin to produce encrypted.bin.
./hilbert2img --opaque encrypted.bin image.bin.meta after.png
```

`img2hilbert` reads an stb-supported image (such as PNG, JPEG, BMP or binary PPM) as 8-bit RGBA. Both `img2hilbert` and `pad_image` offer two aspect-preserving fit modes:

- `--fit short` (default) scales the short edge to the nearest power of two and pads the long edge to a multiple of it.
- `--fit long` scales the long edge to the nearest power of two and pads the short edge up to the next power of two.

Use `-s SIZE` to set the selected edge's power-of-two size explicitly. Ties round up. Neither mode crops source content. Padding is fully transparent RGBA `(0,0,0,0)` and split evenly, with any odd pixel on the right or bottom. The decoder writes the full centered canvas by default; use `--crop` to remove padding. The roundtrip preserves the **scaled** pixels, including alpha, not the original dimensions or file encoding. Leave off `--opaque` to preserve transparency; that flag makes every pixel opaque so ciphertext shows up as noise.

The canvas is a row or column of equal Hilbert squares, with a one-pixel step between tiles. The binary contains only pixel data, with no header. `img2hilbert` automatically writes a plain-text layout file next to it (e.g., `image.bin.meta` for `image.bin`). Give `hilbert2img` this sidecar even if you modify or rename the binary. It tells the decoder how to place the pixels and, if requested, where to crop. The sidecar starts with a line that the encoder also prints:

```text
orig_width orig_height scaled_width scaled_height tile_side tile_count axis offset_x offset_y [long] [bc3|ycc]
```

The axis is `H` for a row of tiles (also used for square inputs), or `V` for a column. The offsets give the top-left position of the scaled image on the canvas. The optional final `long` field marks long-edge fit; existing sidecars without it still work. Keep the sidecar unchanged when encrypting.

For example, `265 314 256 303 256 2 V 0 104` means the original was 265×314, scaled to 256×303. Two 256×256 tiles stacked vertically make a 256×512 canvas. The scaled image starts at `(0, 104)`, with 104 pixels of padding above it and 105 below.

## Resize and pad as a separate step

```sh
./pad_image photo.jpg padded.png
# Or fit the long side to 256 pixels:
./pad_image --fit long -s 256 photo.jpg padded.png
./img2hilbert padded.png image.bin
```

`pad_image` writes a regular PNG with the same centered, transparent padding as `img2hilbert`. It does not write a sidecar. Encoding the prepared PNG with no size override needs no second resize or padding; its sidecar describes the PNG itself, so the offsets are zero and `--crop` does not remove the transparent borders. To keep the pre-padding crop information, encode the original directly.

If resizing or padding a portrait produces a square canvas, direct encoding still uses the original vertical orientation, while encoding the square PNG uses horizontal orientation. The binary order differs in that case, but each binary reconstructs the same image with its own sidecar.

## Smaller lossy binary

```sh
./img2hilbert -q bc3 photo.png compact.bin
./hilbert2img compact.bin compact.bin.meta compact.png

./img2hilbert -q ycc photo.png sampled.bin
./hilbert2img sampled.bin sampled.bin.meta sampled.png
```

`-q bc3` writes one standard BC3 (DXT5) record per **4×4 pixel square**, ordered along the Hilbert curve on the block grid. Each record is exactly **16 bytes**, so the raw binary is **75% smaller** than the default `-q rgba` for the same canvas. BC3 is lossy in both RGB and alpha; padding stays transparent unless you use `--opaque`. The sidecar is the separate `.meta` text file and marks the format with `bc3`; no image-wide palette or other color data is needed. A BC3 canvas requires Hilbert tiles at least four pixels wide. The binary is a headerless BC3 stream in Hilbert order, not a standard DDS file.

`-q ycc` uses the same **16-byte records for 4×4 squares**, but stores JPEG-style full-range BT.601 YCbCr samples. Each record contains a left and right **2×4** half, in that order. Each half stores `Y0 Y1 Y2 Y3 Cb0 Cb1 Cr0 Cr1`: one brightness sample averaged across each row pair of pixels, and one sample per chroma channel averaged over each 2×2 half-height region. Decoding repeats the nearest sample. Padding pixels do not contribute to the averages. YCC does not store source alpha: it decodes the scaled image as opaque and the padding as transparent (or all opaque with `--opaque`). It is not a JPEG file and does not use JPEG's transform or variable-rate encoding. Like BC3, it requires Hilbert tiles at least four pixels wide.

## Modify a block without encryption

```sh
# Randomize block 7 (the eighth block) in a copy; the default block size is 16 bytes.
./modify_block image.bin changed.bin 7

# Use 4096-byte blocks and flip every bit in blocks 3, 8, 9, and 10.
./modify_block -b 4096 -m flip image.bin changed.bin 3,8-10

# Print the 4096-byte block index for canvas pixel (120,180), without editing.
./modify_block -b 4096 -M image.bin.meta -p 120,180

# Or edit that block directly, fill it with 0x80, and print the index.
./modify_block -b 4096 -m fill:80 -M image.bin.meta -p 120,180 image.bin changed.bin
./hilbert2img --opaque changed.bin image.bin.meta changed.png
```

Block sizes (`-b`) are in **bytes**, not bits. Block indices and canvas coordinates are zero-based. Ranges are inclusive and overlapping selections apply once. `-p` looks up the block containing the first byte of the pixel's encoded record, using its position on the **padded** canvas (not the cropped image). Specify the same input and output path to edit in place. Modes are `random` (read from `/dev/urandom`), `zero`, `flip` (invert every bit), and `fill:HH` (repeat one hex byte). A block that extends past EOF is rejected.

In BC3 and YCC modes, `modify_block -b 16` edits exactly one 4×4 pixel square; `-b 4096` edits a 64×64 square when the Hilbert tile is at least 64 pixels wide. In RGBA mode, aligned 16- and 4,096-byte blocks map to 2×2 and 32×32 squares respectively when the tiles are large enough. Runs of blocks follow the curve and can also touch the padding.

`make test` requires Python 3, Pillow, and OpenSSL development headers (for the optional legacy `xts_blocks` demo only). It checks roundtripping, centering, compression, and that selected block edits stay local. See `demo/ycc-comparison.png` for the RGBA, BC3, and YCC comparison and a one-record YCC edit.
