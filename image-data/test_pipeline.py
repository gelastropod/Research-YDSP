from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image


ROOT = Path(__file__).resolve().parent


def run(tool, *args, error=None):
    result = subprocess.run([ROOT / tool, *args], capture_output=True, text=True)
    if error is None:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0 and error in result.stderr, result
    return result.stdout.strip()


def rgba_pixels(image):
    data = image.tobytes()
    return list(zip(data[::4], data[1::4], data[2::4], data[3::4]))


def read_png(path):
    with Image.open(path) as image:
        return image.size, rgba_pixels(image.convert("RGBA"))


def test_padding(tmp):
    source, padded, binary = (tmp / p for p in ("source.png", "padded.png", "image.bin"))
    color = (32, 120, 224, 172)
    for size in ((13, 8), (2, 4), (12, 6)):
        Image.new("RGBA", size, color).save(source)
        run("encode", source, binary, error="run pad_image first")
        assert not binary.exists()
    Image.new("RGB", (8, 8)).save(source, format="BMP")
    run("encode", source, binary, error="expected a PNG")
    white, transparent = (255, 255, 255, 255), (0, 0, 0, 0)
    flattened = tuple(255 - ((255 - c) * color[3] + 127) // 255 for c in color[:3]) + (255,)
    for size, options, canvas_size, box, border, fill in (
        ((13, 8), (), (16, 8), (1, 0, 14, 8), white, flattened),
        ((6, 32), ("--fit", "long"), (8, 32), (1, 0, 7, 32), white, flattened),
        ((9, 24), ("--fit", "long", "-s", "16"), (8, 16), (1, 0, 7, 16), white, flattened),
        ((9, 24), ("--fit", "long", "--transparent", "-s", "16"), (8, 16), (1, 0, 7, 16), transparent, color),
        ((2, 8), (), (4, 16), (0, 0, 4, 16), white, flattened),
    ):
        Image.new("RGBA", size, color).save(source)
        run("pad_image", *options, source, padded)
        actual_size, pixels = read_png(padded)
        assert actual_size == canvas_size
        expected = Image.new("RGBA", canvas_size, border)
        expected.paste(fill, box)
        for actual, wanted in zip(pixels, rgba_pixels(expected)):
            if wanted == border:
                assert actual == wanted
            else:
                assert max(abs(a - b) for a, b in zip(actual, wanted)) <= 1
        run("encode", padded, binary)
    run("pad_image", "-s", "6", source, padded, error="power of two")
    print("Padding: both fit modes, alpha flattening, centered white and transparent borders, minimum edge, and encoder validation")


def test_rgba(tmp):
    source, payload, restored = (tmp / p for p in ("rgba.png", "rgba.bin", "restored.png"))
    meta = payload.with_suffix(".bin.meta")
    for width, height in ((24, 8), (8, 24), (8, 8)):
        image = Image.new("RGBA", (width, height))
        image.putdata([(x, y, x * y % 256, (x + 11 * y) % 256)
                       for y in range(height) for x in range(width)])
        image.save(source)
        run("encode", "-q", "rgba", source, payload)
        assert meta.read_text() == f"{width} {height} rgba\n"
        run("decode", payload, meta, restored)
        assert read_png(restored) == (image.size, rgba_pixels(image))
        raw = payload.read_bytes()
        assert len(raw) == width * height * 4
        points = [tuple(raw[i:i + 2]) for i in range(0, len(raw), 4)]
        assert points == [(x, y) for y in range(height) for x in range(width)]
        for i in (0, 19, width * height - 1):
            x, y = points[i]
            assert run("modify_block", "-b", "7", "-M", meta, "-p", f"{x},{y}") == str(4 * i // 7)
    print("RGBA: exact color and alpha, row-major traversal, and byte-based pixel lookup")


def test_compressed(tmp):
    source, payload, restored, changed_payload, changed_png = (
        tmp / p for p in ("tiles.png", "tiles.bin", "tiles-restored.png", "changed.bin", "changed.png")
    )
    meta = payload.with_suffix(".bin.meta")
    for size, point in (((8, 24), (5, 14)), ((24, 8), (14, 5))):
        image = Image.new("RGBA", size)
        for y in range(size[1]):
            for x in range(size[0]):
                color = 60 + 31 * (x // 4) + 13 * (y // 4)
                alpha = (0, 112, 255)[(x // 4 + y // 4) % 3]
                image.putpixel((x, y), (color, color - 16, color + 8, alpha))
        image.save(source)
        for fmt, flags, tolerance in (("ycc", (), 2), ("bc3", ("-q", "bc3"), 8)):
            run("encode", *flags, source, payload)
            raw = payload.read_bytes()
            assert len(raw) == size[0] * size[1]
            assert meta.read_text() == f"{size[0]} {size[1]} {fmt}\n"
            run("decode", payload, meta, restored)
            dims, pixels = read_png(restored)
            assert dims == size
            for actual, original in zip(pixels, rgba_pixels(image)):
                assert actual[3] == (255 if fmt == "ycc" else original[3])
                assert max(abs(a - b) for a, b in zip(actual[:3], original[:3])) <= tolerance
            x, y = point
            location = ("-M", meta, "-p", f"{x},{y}")
            index = int(run("modify_block", *location))
            assert run("modify_block", "-m", "zero", *location, payload, changed_payload) == str(index)
            offset = index * 16
            assert changed_payload.read_bytes() == raw[:offset] + bytes(16) + raw[offset + 16:]
            run("decode", changed_payload, meta, changed_png)
            _, after = read_png(changed_png)
            assert {i for i, (a, b) in enumerate(zip(pixels, after)) if a != b} == {
                j * size[0] + i
                for j in range(y // 4 * 4, y // 4 * 4 + 4)
                for i in range(x // 4 * 4, x // 4 * 4 + 4)
            }

    fixture = Image.new("RGBA", (4, 4))
    fixture.putdata([(k, k, k, 0) for k in range(0, 160, 10)])
    fixture.save(source)
    run("encode", source, payload)
    assert payload.read_bytes() == bytes([5, 45, 85, 125, 128, 128, 128, 128,
                                          25, 65, 105, 145, 128, 128, 128, 128])
    payload.write_bytes(payload.read_bytes() + b"\0")
    run("decode", payload, meta, restored, error="expected exactly 16 bytes")
    meta.write_text("4 4 ycc extra\n")
    run("decode", payload, meta, restored, error="WIDTH HEIGHT FORMAT")
    print("YCC and BC3: 75% smaller, expected samples/alpha, and 16-byte edits confined to one 4×4 square")


def test_modify(tmp):
    payload = tmp / "blocks.bin"
    raw = bytes(range(48))
    payload.write_bytes(raw)
    run("modify_block", "-b", "4", "-m", "flip", payload, payload, "1-2,2-3")
    expected = raw[:4] + bytes(x ^ 255 for x in raw[4:16]) + raw[16:]
    assert payload.read_bytes() == expected
    run("modify_block", "-b", "4", "-m", "fill:A5", payload, payload, "0")
    expected = b"\xa5" * 4 + expected[4:]
    assert payload.read_bytes() == expected
    run("modify_block", "-b", "4", payload, payload, "12", error="extends past end of file")
    copy = tmp / "random.bin"
    run("modify_block", payload, copy, "1")
    after = copy.read_bytes()
    assert len(after) == len(expected) and after[:16] == expected[:16] and after[32:] == expected[32:]
    assert payload.read_bytes() == expected
    print("Block edits: byte counts, overlapping ranges, in-place writes, and EOF rejection")


with TemporaryDirectory() as directory:
    tmp = Path(directory)
    test_padding(tmp)
    test_rgba(tmp)
    test_compressed(tmp)
    test_modify(tmp)
