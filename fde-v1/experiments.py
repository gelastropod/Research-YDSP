"""
Expected observations:
1. Sector-scope ratcheting preserves sector-level random access.
2. Global-scope ratcheting propagates corruption across sectors but loses random access.
3. Bit-flipping a ciphertext block does not create authentication; it only causes controlled/uncontrolled plaintext corruption.
"""

from __future__ import annotations

import os
import time

from ratchet_fde import RatchetedFDE, count_corrupted_blocks, flip_bit, BLOCK_SIZE


def make_volume(num_sectors: int, sector_size: int) -> bytes:
    # Structured plaintext makes corruption easier to inspect.
    sectors = []
    for i in range(num_sectors):
        label = f"SECTOR-{i:04d}|".encode()
        sectors.append((label * ((sector_size // len(label)) + 1))[:sector_size])
    return b"".join(sectors)


def benchmark(model: RatchetedFDE, plaintext: bytes, rounds: int = 1000) -> float:
    t0 = time.perf_counter()
    for _ in range(rounds):
        ct = model.encrypt_volume(plaintext)
        _ = model.decrypt_volume(ct)
    t1 = time.perf_counter()
    return t1 - t0


def main() -> None:
    master_key = b"demo master key for ratcheted fde".ljust(32, b"\x00")
    blocks_per_sector = 4
    num_sectors = 4

    sector_model = RatchetedFDE(master_key, blocks_per_sector=blocks_per_sector, scope="sector")
    global_model = RatchetedFDE(master_key, blocks_per_sector=blocks_per_sector, scope="global")

    plaintext = make_volume(num_sectors, sector_model.sector_size)

    for name, model in [("sector", sector_model), ("global", global_model)]:
        ct = model.encrypt_volume(plaintext)
        recovered = model.decrypt_volume(ct)
        assert recovered == plaintext

        tampered = flip_bit(ct, 0)
        tampered_plaintext = model.decrypt_volume(tampered)
        corrupted = count_corrupted_blocks(plaintext, tampered_plaintext)

        print(f"[{name}] ciphertext length: {len(ct)} bytes")
        print(f"[{name}] decryption correctness: {recovered == plaintext}")
        print(f"[{name}] corrupted 16-byte blocks after flipping byte 0: {corrupted}")

    # Random-access experiment:
    lba = 3
    off = lba * sector_model.sector_size
    sector_ct = sector_model.encrypt_volume(plaintext)[off:off + sector_model.sector_size]
    sector_pt, _ = sector_model.decrypt_sector(lba, sector_ct)
    print(f"[sector] direct decryption of LBA {lba}: {sector_pt == plaintext[off:off+sector_model.sector_size]}")

    global_ct = global_model.encrypt_volume(plaintext)
    wrong_pt, _ = global_model.decrypt_sector(lba, global_ct[off:off + global_model.sector_size])
    print(f"[global] direct decryption of LBA {lba} without previous state: {wrong_pt == plaintext[off:off+global_model.sector_size]}")

    # Tiny timing comparison. This is not a serious benchmark, only an experiment hook.
    print("[timing] sector scope 1000 encrypt+decrypt cycles:", round(benchmark(sector_model, plaintext), 4), "s")
    print("[timing] global scope 1000 encrypt+decrypt cycles:", round(benchmark(global_model, plaintext), 4), "s")


if __name__ == "__main__":
    main()
