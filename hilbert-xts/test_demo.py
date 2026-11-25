import io
import struct
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


DEMO = Path("demo")
DEMO.mkdir(exist_ok=True)
KEY = bytes(range(64)).hex()


def run(tool, *args):
    return subprocess.check_output([f"./{tool}", *map(str, args)], text=True).strip()


def image(name):
    return Image.open(DEMO / name).convert("RGBA")


def check_tile_order(width, height, axis):
    sample = Image.new("RGBA", (width, height))
    sample.putdata([(x, y, 100, (x + y) * 9) for y in range(height) for x in range(width)])
    source = DEMO / "small.png"
    raw = DEMO / "small.bin"
    meta = DEMO / "small.bin.meta"
    sample.save(source)
    assert run("img2hilbert", "-s", 4, source, raw) == f"{width} {height} {width} {height} 4 3 {axis} 0 0"
    pixels = raw.read_bytes()
    coordinates = [(pixels[i], pixels[i + 1]) for i in range(0, len(pixels), 4)]
    assert sorted(coordinates) == sorted((x, y) for x in range(width) for y in range(height))
    assert all(abs(a - x) + abs(b - y) == 1 for (a, b), (x, y) in zip(coordinates, coordinates[1:]))
    run("hilbert2img", raw, meta, DEMO / "small-out.png")
    assert image("small-out.png").tobytes() == sample.tobytes()
    for i in (0, 15, 16, 31, 32, 47):
        x, y = coordinates[i]
        assert run("modify_block", "-b", 4, "-M", meta, "-p", f"{x},{y}") == str(i)


check_tile_order(12, 4, "H")
check_tile_order(4, 12, "V")
print("Horizontal and vertical traversal: every pixel once; consecutive pixels touch across tiles; alpha roundtrips")

portrait = Image.new("RGBA", (4, 9), (25, 80, 145, 110))
portrait.save(DEMO / "portrait.png")
assert run("img2hilbert", DEMO / "portrait.png", DEMO / "portrait.bin") == "4 9 4 9 4 3 V 0 1"
run("hilbert2img", DEMO / "portrait.bin", DEMO / "portrait.bin.meta", DEMO / "portrait-out.png")
portrait_canvas = Image.new("RGBA", (4, 12), (0, 0, 0, 0))
portrait_canvas.paste(portrait, (0, 1))
assert image("portrait-out.png").tobytes() == portrait_canvas.tobytes()

run("pad_image", "-s", 8, "--fit", "short", DEMO / "portrait.png", DEMO / "portrait-padded.png")
assert image("portrait-padded.png").size == (8, 24)
assert run("img2hilbert", "-s", 8, DEMO / "portrait.png", DEMO / "portrait-direct.bin") == "4 9 8 18 8 3 V 0 3"
assert run("img2hilbert", DEMO / "portrait-padded.png", DEMO / "portrait-padded.bin") == "8 24 8 24 8 3 V 0 0"
assert (DEMO / "portrait-direct.bin").read_bytes() == (DEMO / "portrait-padded.bin").read_bytes()

near_square = Image.new("RGBA", (5, 6))
near_square.putdata([(20 * x, 20 * y, 100, 255) for y in range(6) for x in range(5)])
near_square.save(DEMO / "near-square.png")
run("pad_image", "-s", 2, DEMO / "near-square.png", DEMO / "square-padded.png")
assert run("img2hilbert", "-s", 2, DEMO / "near-square.png", DEMO / "square-direct.bin") == "5 6 2 2 2 1 V 0 0"
assert run("img2hilbert", DEMO / "square-padded.png", DEMO / "square-padded.bin") == "2 2 2 2 2 1 H 0 0"
assert (DEMO / "square-direct.bin").read_bytes() != (DEMO / "square-padded.bin").read_bytes()
run("hilbert2img", DEMO / "square-direct.bin", DEMO / "square-direct.bin.meta", DEMO / "square-direct.png")
assert image("square-direct.png").tobytes() == image("square-padded.png").tobytes()

sample = Image.new("RGB", (1000, 600))
draw = ImageDraw.Draw(sample)
for y in range(sample.height):
    draw.line((0, y, 999, y), fill=(36 + y // 6, 92 + y // 5, 143 + y // 7))
draw.ellipse((704, 50, 847, 193), fill="#ffdf95")
draw.polygon([(0, 400), (185, 185), (280, 300), (409, 130), (700, 431), (1000, 295),
              (1000, 600), (0, 600)], fill="#364866")
draw.polygon([(311, 243), (409, 130), (528, 253), (467, 237), (418, 269), (382, 229)], fill="#dce7ea")
draw.polygon([(0, 415), (237, 342), (529, 461), (765, 322), (1000, 416), (1000, 600), (0, 600)], fill="#377f7d")
draw.polygon([(0, 520), (220, 473), (487, 530), (767, 443), (1000, 508), (1000, 600), (0, 600)], fill="#215260")
for x, y in [(112, 212), (158, 248), (250, 124), (557, 116), (607, 147), (902, 239)]:
    draw.arc((x - 18, y, x, y + 20), 195, 350, fill="#fcf2d6", width=3)
    draw.arc((x, y, x + 18, y + 20), 190, 345, fill="#fcf2d6", width=3)
sample.save(DEMO / "input.png")

raw = DEMO / "image.bin"
meta = DEMO / "image.bin.meta"
assert run("img2hilbert", DEMO / "input.png", raw) == "1000 600 853 512 512 2 H 85 0"
run("test_resize", DEMO / "input.png", DEMO / "reference.png", 853, 512)
run("hilbert2img", "--crop", raw, meta, DEMO / "cropped.png")
assert image("cropped.png").tobytes() == image("reference.png").tobytes()
print("Resized roundtrip: all 853×512 RGBA pixels match the direct resize byte-for-byte")

run("hilbert2img", raw, meta, DEMO / "before.png")
before = image("before.png")
canvas = Image.new("RGBA", (1024, 512), (0, 0, 0, 0))
canvas.paste(image("reference.png"), (85, 0))
assert before.size == canvas.size and before.tobytes() == canvas.tobytes()
print("Centered canvases: landscape has 85/86 px on the left/right; portrait has 1/2 px above/below")

run("pad_image", DEMO / "input.png", DEMO / "padded.png")
padded = image("padded.png")
assert padded.size == before.size and padded.tobytes() == before.tobytes()
assert run("img2hilbert", DEMO / "padded.png", DEMO / "padded.bin") == "1024 512 1024 512 512 2 H 0 0"
assert (DEMO / "padded.bin").read_bytes() == raw.read_bytes()
print("Standalone padding: PNG matches the centered canvas; re-encoding adds no resize or offset and matches direct bytes for landscape and portrait")

long_source = DEMO / "input.png"
long_raw = DEMO / "long.bin"
long_meta = DEMO / "long.bin.meta"
assert run("img2hilbert", "--fit", "long", long_source, long_raw) == "1000 600 1024 614 1024 1 H 0 205 long"
run("test_resize", long_source, DEMO / "long-reference.png", 1024, 614)
run("hilbert2img", "--crop", long_raw, long_meta, DEMO / "long-crop.png")
assert image("long-crop.png").size == (1024, 614)
assert image("long-crop.png").tobytes() == image("long-reference.png").tobytes()
run("hilbert2img", long_raw, long_meta, DEMO / "long-decoded.png")
run("pad_image", "--fit", "long", long_source, DEMO / "long-padded.png")
long_canvas = Image.new("RGBA", (1024, 1024))
long_canvas.paste(image("long-reference.png"), (0, 205))
assert image("long-decoded.png").tobytes() == image("long-padded.png").tobytes() == long_canvas.tobytes()

portrait_long = DEMO / "portrait-long.bin"
portrait_long_meta = DEMO / "portrait-long.bin.meta"
assert run("img2hilbert", "--fit", "long", "-s", 32, DEMO / "portrait.png", portrait_long) == "4 9 14 32 16 2 V 1 0 long"
run("pad_image", "-s", 32, "--fit", "long", DEMO / "portrait.png", DEMO / "portrait-long.png")
run("test_resize", DEMO / "portrait.png", DEMO / "portrait-long-reference.png", 14, 32)
expected_portrait_long = Image.new("RGBA", (16, 32))
expected_portrait_long.paste(image("portrait-long-reference.png"), (1, 0))
assert image("portrait-long.png").size == (16, 32)
assert image("portrait-long.png").tobytes() == expected_portrait_long.tobytes()
assert run("img2hilbert", DEMO / "portrait-long.png", DEMO / "portrait-long-prepared.bin") == "16 32 16 32 16 2 V 0 0"
assert (DEMO / "portrait-long-prepared.bin").read_bytes() == portrait_long.read_bytes()
assert run("modify_block", "-b", 4, "-M", portrait_long_meta, "-p", "0,16") == "256"
print("Long fit: centered transparent padding, byte-exact crop, and pixel lookup across vertical tiles")

modified = DEMO / "modified.bin"
pixel = "256,250"
index = int(run("modify_block", "-M", meta, "-p", pixel))
assert run("modify_block", "-M", meta, "-p", pixel, "-m", "zero", raw, modified) == str(index)
original = raw.read_bytes()
start = index * 16
assert modified.read_bytes() == original[:start] + bytes(16) + original[start + 16:]
run("hilbert2img", "--opaque", modified, meta, DEMO / "modified.png")
edited = image("modified.png").convert("RGB")
assert edited.getpixel((256, 250)) == (0, 0, 0)
modified_diff = ImageChops.difference(before.convert("RGB"), edited)
assert modified_diff.getbbox() == (256, 250, 258, 252)

small = DEMO / "block-fixture.bin"
fixture = bytes(range(101))
small.write_bytes(fixture)
run("modify_block", "-m", "flip", small, small, "4,1-2,2")
expected = bytes(b ^ 255 if i // 16 in {1, 2, 4} else b for i, b in enumerate(fixture))
assert small.read_bytes() == expected
run("modify_block", "-b", 8, "-m", "fill:A5", small, small, 0)
expected = bytes([0xA5]) * 8 + expected[8:]
assert small.read_bytes() == expected
bad = subprocess.run(["./modify_block", str(small), str(small), "0,6"], capture_output=True, text=True)
assert bad.returncode != 0 and "extends past end of file" in bad.stderr
assert small.read_bytes() == expected
run("modify_block", small, small, 0)
randomized = small.read_bytes()
assert randomized[:16] != expected[:16] and randomized[16:] == expected[16:]
print("Block editing: one 16-byte edit decoded as a 2×2 patch at (256,250); ranges, in-place, and EOF checked")

bc3 = DEMO / "bc3.bin"
bc3_meta = DEMO / "bc3.bin.meta"
assert run("img2hilbert", "-q", "bc3", DEMO / "input.png", bc3) == "1000 600 853 512 512 2 H 85 0 bc3"
assert bc3.stat().st_size * 4 == raw.stat().st_size
run("hilbert2img", bc3, bc3_meta, DEMO / "bc3.png")
bc3_image = image("bc3.png")
assert bc3_image.getchannel("A").tobytes() == before.getchannel("A").tobytes()
bc3_diff = ImageChops.difference(bc3_image.convert("RGB"), before.convert("RGB"))
assert max(ImageStat.Stat(bc3_diff).mean) < 5
run("hilbert2img", "--crop", bc3, bc3_meta, DEMO / "bc3-crop.png")
assert image("bc3-crop.png").tobytes() == bc3_image.crop((85, 0, 938, 512)).tobytes()
print(f"BC3 payload: {raw.stat().st_size} → {bc3.stat().st_size} bytes (75% smaller), with transparent padding")

alpha_indices = sum((i % 8) << (3 * i) for i in range(16)).to_bytes(6, "little")
color_data = struct.pack("<HH", 0x001F, 0xF800) + bytes([0xE4] * 4)
bc3_vectors = bytes([0, 250]) + alpha_indices + color_data + bytes([245, 0]) + alpha_indices + color_data
(DEMO / "bc3-vectors.bin").write_bytes(bc3_vectors)
(DEMO / "bc3-vectors.bin.meta").write_text("8 4 8 4 4 2 H 0 0 long bc3\n")
run("hilbert2img", DEMO / "bc3-vectors.bin", DEMO / "bc3-vectors.bin.meta", DEMO / "bc3-vectors.png")
dds = b"DDS " + struct.pack("<7I11I8I5I", 124, 0x81007, 4, 8, 32, 0, 0, *([0] * 11),
                           32, 4, int.from_bytes(b"DXT5", "little"), 0, 0, 0, 0, 0,
                           0x1000, 0, 0, 0, 0)
with Image.open(io.BytesIO(dds + bc3_vectors)) as reference:
    assert image("bc3-vectors.png").tobytes() == reference.convert("RGBA").tobytes()
bad_bc3 = subprocess.run(["./img2hilbert", "-q", "bc3", "-s", "2",
                          str(DEMO / "input.png"), str(DEMO / "tiny-bc3.bin")],
                         capture_output=True, text=True)
assert bad_bc3.returncode != 0 and "at least 4 pixels" in bad_bc3.stderr
print("BC3 decoder: imported blocks match Pillow DXT5 for both alpha interpolation modes")

for byte_count, edge in [(16, 4), (4096, 64)]:
    output = DEMO / f"bc3-edit-{byte_count}.png"
    changed = DEMO / f"bc3-edit-{byte_count}.bin"
    index = int(run("modify_block", "-b", byte_count, "-M", bc3_meta, "-p", pixel))
    assert run("modify_block", "-b", byte_count, "-M", bc3_meta, "-p", pixel,
               "-m", "zero", bc3, changed) == str(index)
    start = index * byte_count
    original_bc3 = bc3.read_bytes()
    assert changed.read_bytes() == original_bc3[:start] + bytes(byte_count) + original_bc3[start + byte_count:]
    run("hilbert2img", "--opaque", changed, bc3_meta, output)
    edited = image(output.name)
    assert edited.getpixel((256, 250)) == (0, 0, 0, 255)
    change = ImageChops.difference(bc3_image.convert("RGB"), edited.convert("RGB"))
    x, y = (256 // edge) * edge, (250 // edge) * edge
    assert change.getbbox() == (x, y, x + edge, y + edge)
    assert change.convert("L").histogram()[0] == edited.width * edited.height - edge * edge
print("BC3 locality: one 16-byte record → 4×4 pixels; one aligned 4096-byte range → 64×64 pixels")

bc3_comparison = Image.new("RGB", (982, 534), "#1a2231")
caption = ImageDraw.Draw(bc3_comparison)
edited_small = image("bc3-edit-16.png")
for x, y, label, panel in [(16, 8, "RGBA  |  Uncompressed", before),
                           (506, 8, "BC3  |  75% smaller raw payload", bc3_image),
                           (16, 270, "BC3  |  16 bytes zeroed (4×4 pixels, detail at right)", edited_small),
                           (506, 270, "BC3  |  4,096 bytes zeroed (64×64 pixels)", edited)]:
    panel.putalpha(bc3_image.getchannel("A"))
    caption.text((x, y), label, fill="white")
    thumbnail = panel.resize((460, 230), Image.Resampling.LANCZOS)
    bc3_comparison.paste("black", (x, y + 20, x + thumbnail.width, y + 20 + thumbnail.height))
    bc3_comparison.paste(thumbnail, (x, y + 20), thumbnail)
zoom = edited_small.crop((250, 242, 266, 258)).resize((80, 80), Image.Resampling.NEAREST)
caption.rectangle((385, 297, 466, 378), fill="white")
bc3_comparison.paste(zoom, (386, 298))
bc3_comparison.save(DEMO / "bc3-comparison.png")

ycc_fixture = Image.new("RGBA", (4, 4))
ycc_fixture.putdata([(255, 0, 0, 255), (0, 255, 0, 255), (10, 10, 10, 255), (30, 30, 30, 255),
                     (0, 0, 255, 255), (0, 0, 0, 255), (40, 40, 40, 255), (60, 60, 60, 255),
                     (80, 80, 80, 255), (100, 100, 100, 255), (255, 0, 0, 255), (255, 0, 0, 255),
                     (120, 120, 120, 255), (140, 140, 140, 255), (0, 255, 0, 255), (0, 255, 0, 255)])
ycc_fixture.save(DEMO / "ycc-fixture.png")
run("img2hilbert", "-q", "ycc", DEMO / "ycc-fixture.png", DEMO / "ycc-fixture.bin")
assert (DEMO / "ycc-fixture.bin").read_bytes() == bytes([113, 15, 90, 130, 128, 128, 128, 128,
                                                       20, 50, 76, 150, 128, 64, 128, 138])
run("hilbert2img", DEMO / "ycc-fixture.bin", DEMO / "ycc-fixture.bin.meta", DEMO / "ycc-fixture-out.png")
sampled_fixture = image("ycc-fixture-out.png")
assert sampled_fixture.getpixel((0, 0)) == sampled_fixture.getpixel((1, 0)) == (113, 113, 113, 255)
assert sampled_fixture.getpixel((2, 2)) == sampled_fixture.getpixel((3, 2)) == (90, 91, 0, 255)

Image.new("RGBA", (5, 4), (225, 80, 50, 0)).save(DEMO / "ycc-edge.png")
assert run("img2hilbert", "-q", "ycc", DEMO / "ycc-edge.png", DEMO / "ycc-edge.bin") == "5 4 5 4 4 2 H 1 0 ycc"
solid_samples = bytes([120, 120, 120, 120, 89, 89, 203, 203])
empty_samples = bytes([0, 0, 0, 0, 128, 128, 128, 128])
assert (DEMO / "ycc-edge.bin").read_bytes() == solid_samples * 3 + empty_samples
run("hilbert2img", DEMO / "ycc-edge.bin", DEMO / "ycc-edge.bin.meta", DEMO / "ycc-edge-out.png")
assert image("ycc-edge-out.png").getchannel("A").tobytes() == bytes([0, 255, 255, 255, 255, 255, 0, 0]) * 4
run("hilbert2img", "--opaque", DEMO / "ycc-edge.bin", DEMO / "ycc-edge.bin.meta", DEMO / "ycc-edge-opaque.png")
assert image("ycc-edge-opaque.png").getchannel("A").getextrema() == (255, 255)
print("YCC samples: 4 Y, 2 Cb, and 2 Cr per 2×4 half; padding excluded from averages")

ycc = DEMO / "ycc.bin"
ycc_meta = DEMO / "ycc.bin.meta"
assert run("img2hilbert", "-q", "ycc", DEMO / "input.png", ycc) == "1000 600 853 512 512 2 H 85 0 ycc"
assert ycc.stat().st_size == bc3.stat().st_size == raw.stat().st_size // 4
run("hilbert2img", ycc, ycc_meta, DEMO / "ycc.png")
ycc_image = image("ycc.png")
assert ycc_image.getchannel("A").tobytes() == before.getchannel("A").tobytes()
run("hilbert2img", "--crop", ycc, ycc_meta, DEMO / "ycc-crop.png")
assert image("ycc-crop.png").tobytes() == ycc_image.crop((85, 0, 938, 512)).tobytes()

index = run("modify_block", "-b", 16, "-M", ycc_meta, "-p", pixel)
assert index == run("modify_block", "-b", 16, "-M", bc3_meta, "-p", pixel)
ycc_edit = DEMO / "ycc-edit-16.bin"
assert run("modify_block", "-b", 16, "-M", ycc_meta, "-p", pixel, "-m", "zero", ycc, ycc_edit) == index
start = int(index) * 16
payload = ycc.read_bytes()
assert ycc_edit.read_bytes() == payload[:start] + bytes(16) + payload[start + 16:]
run("hilbert2img", ycc_edit, ycc_meta, DEMO / "ycc-edit-16.png")
ycc_edited = image("ycc-edit-16.png")
ycc_change = ImageChops.difference(ycc_edited.convert("RGB"), ycc_image.convert("RGB"))
assert ycc_change.getbbox() == (256, 248, 260, 252)
assert ycc_change.convert("L").histogram()[0] == ycc_edited.width * ycc_edited.height - 16
print(f"YCC locality: one 16-byte edit changes only a 4×4 square; payload {raw.stat().st_size} → {ycc.stat().st_size} bytes")

ycc_comparison = Image.new("RGB", (982, 534), "#1a2231")
caption = ImageDraw.Draw(ycc_comparison)
for x, y, label, panel in [(16, 8, "RGBA  |  Uncompressed", before),
                           (506, 8, "BC3  |  16 bytes per 4×4", bc3_image),
                           (16, 270, "YCC  |  16 bytes per 4×4", ycc_image),
                           (506, 270, "YCC  |  One 16-byte record zeroed (detail at right)", ycc_edited)]:
    caption.text((x, y), label, fill="white")
    thumbnail = panel.resize((460, 230), Image.Resampling.LANCZOS)
    ycc_comparison.paste("black", (x, y + 20, x + thumbnail.width, y + 20 + thumbnail.height))
    ycc_comparison.paste(thumbnail, (x, y + 20), thumbnail)
zoom = ycc_edited.crop((250, 242, 266, 258)).resize((80, 80), Image.Resampling.NEAREST)
caption.rectangle((875, 297, 956, 378), fill="white")
ycc_comparison.paste(zoom, (876, 298))
ycc_comparison.save(DEMO / "ycc-comparison.png")

sector_size = 4096
selected = {*range(39, 44), 130, *range(300, 306), 364}
encrypted = DEMO / "encrypted.bin"
run("xts_blocks", KEY, raw, encrypted, sector_size, "300-305", "39-43", 130, 364, "41-43")
plain, ciphertext = raw.read_bytes(), encrypted.read_bytes()
assert len(plain) == len(ciphertext) == 512 * sector_size
assert {
    i // sector_size for i in range(0, len(plain), sector_size)
    if plain[i:i + sector_size] != ciphertext[i:i + sector_size]
} == selected

run("hilbert2img", "--opaque", encrypted, meta, DEMO / "after.png")
after = image("after.png")
assert after.getchannel("A").getextrema() == (255, 255)
diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
changed_tiles = 0
for y in range(0, before.height, 32):
    for x in range(0, before.width, 32):
        patch = diff.crop((x, y, x + 32, y + 32))
        if patch.getbbox():
            assert patch.getbbox() == (0, 0, 32, 32)
            changed_tiles += 1
assert changed_tiles == len(selected)
print(f"XTS locality: only {len(selected)} of 512 sectors changed, appearing as {changed_tiles} full 32×32 patches")

comparison = Image.new("RGB", (968, 274), "#1a2231")
labels = ImageDraw.Draw(comparison)
labels.text((20, 5), "BEFORE  |  Centered Hilbert canvas", fill="white")
labels.text((494, 5), "AFTER  |  13 selected AES-XTS sectors", fill="white")
comparison.paste(before.resize((460, 230), Image.Resampling.LANCZOS), (20, 25))
comparison.paste(after.resize((460, 230), Image.Resampling.LANCZOS), (494, 25))
comparison.save(DEMO / "comparison.png")
