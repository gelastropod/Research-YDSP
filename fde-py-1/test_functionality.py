"""
Basic assert-based functionality checks with ANSI-coloured expected/actual output.

Run:
    python test_functionality.py

The tests verify implementation behaviour, not a proof of cryptographic security.
"""

from __future__ import annotations

from typing import Any

from ratchet_fde import (
    BLOCK_SIZE,
    BaselineXTSFDE,
    RatchetedXTSFDE,
    count_corrupted_blocks,
    derive_subkeys,
    flip_bit,
    xts_decrypt_data_unit,
    xts_encrypt_data_unit,
)


RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"

MASTER_KEY = b"functionality-test-master-key".ljust(32, b"\x00")
BLOCKS_PER_SECTOR = 4
NUM_SECTORS = 4


def report(name: str, expected: Any, actual: Any) -> None:
    """Print expected and actual values, colour the result, then assert equality."""
    passed = actual == expected
    colour = GREEN if passed else RED
    status = "PASS" if passed else "FAIL"
    print(f"{BOLD}{name}{RESET}")
    print(f"  expected: {CYAN}{expected!r}{RESET}")
    print(f"  actual:   {colour}{actual!r}{RESET}")
    print(f"  result:   {colour}{status}{RESET}\n")
    assert passed, f"{name}: expected {expected!r}, got {actual!r}"


def make_volume(model: BaselineXTSFDE | RatchetedXTSFDE) -> bytes:
    """Build structured test plaintext spanning four sectors."""
    sectors = []
    for lba in range(NUM_SECTORS):
        label = f"LBA={lba:04d}|".encode()
        sectors.append((label * 16)[:model.sector_size])
    return b"".join(sectors)


def test_raw_xts_roundtrip() -> None:
    """Check the pyca AES-XTS wrapper on one 16-byte data unit."""
    xts_key, _, _ = derive_subkeys(MASTER_KEY)
    tweak = (7).to_bytes(16, "little")
    plaintext = b"X" * BLOCK_SIZE
    ciphertext = xts_encrypt_data_unit(xts_key, tweak, plaintext)
    recovered = xts_decrypt_data_unit(xts_key, tweak, ciphertext)
    report("raw AES-XTS one-block roundtrip", plaintext, recovered)


def test_baseline_roundtrip() -> None:
    """Conventional sector-level XTS must recover the original volume."""
    model = BaselineXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR)
    plaintext = make_volume(model)
    recovered = model.decrypt_volume(model.encrypt_volume(plaintext))
    report("baseline sector-level XTS roundtrip", True, recovered == plaintext)


def test_ratcheted_roundtrips() -> None:
    """Both ratchet scopes are correct when decrypted with the matching traversal."""
    for scope in ("sector", "global"):
        model = RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, scope)
        plaintext = make_volume(model)
        recovered = model.decrypt_volume(model.encrypt_volume(plaintext))
        report(f"ratcheted {scope} roundtrip", True, recovered == plaintext)


def test_length_preservation() -> None:
    """All constructions must emit exactly one ciphertext byte per plaintext byte."""
    for label, model in (
        ("baseline", BaselineXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR)),
        ("ratcheted-sector", RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, "sector")),
        ("ratcheted-global", RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, "global")),
    ):
        plaintext = make_volume(model)
        ciphertext = model.encrypt_volume(plaintext)
        report(f"{label} length preservation", len(plaintext), len(ciphertext))


def test_position_variability_and_determinism() -> None:
    """
    Same key/LBA/plaintext is deterministic; changing the LBA changes ciphertext.
    """
    model = BaselineXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR)
    sector = b"A" * model.sector_size
    c5_first = model.encrypt_sector(5, sector)
    c5_second = model.encrypt_sector(5, sector)
    c6 = model.encrypt_sector(6, sector)
    report("same LBA and plaintext are deterministic", True, c5_first == c5_second)
    report("different LBA changes XTS ciphertext", True, c5_first != c6)


def test_random_access() -> None:
    """
    Sector scope resets the chain per LBA; global scope requires preceding state.
    """
    lba = 3

    sector_model = RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, "sector")
    plaintext = make_volume(sector_model)
    ciphertext = sector_model.encrypt_volume(plaintext)
    offset = lba * sector_model.sector_size
    direct_plaintext, _ = sector_model.decrypt_sector(
        lba,
        ciphertext[offset:offset + sector_model.sector_size],
    )
    report(
        "sector ratchet direct access to LBA 3",
        plaintext[offset:offset + sector_model.sector_size],
        direct_plaintext,
    )

    global_model = RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, "global")
    global_plaintext = make_volume(global_model)
    global_ciphertext = global_model.encrypt_volume(global_plaintext)
    wrong_plaintext, _ = global_model.decrypt_sector(
        lba,
        global_ciphertext[offset:offset + global_model.sector_size],
    )
    report(
        "global ratchet direct access without preceding state",
        False,
        wrong_plaintext == global_plaintext[offset:offset + global_model.sector_size],
    )


def test_tamper_propagation() -> None:
    """
    Flip one bit in the first ciphertext block and count changed plaintext blocks.

    Expected with 4 sectors x 4 blocks:
      baseline XTS: 1 block
      sector ratchet: 4 blocks (the first sector)
      global ratchet: 16 blocks (the entire remaining chain)
    """
    cases = (
        ("baseline", BaselineXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR), 1),
        ("ratcheted-sector", RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, "sector"), 4),
        ("ratcheted-global", RatchetedXTSFDE(MASTER_KEY, BLOCKS_PER_SECTOR, "global"), 16),
    )

    for label, model, expected_count in cases:
        plaintext = make_volume(model)
        ciphertext = model.encrypt_volume(plaintext)
        tampered_plaintext = model.decrypt_volume(flip_bit(ciphertext, 0))
        actual_count = count_corrupted_blocks(plaintext, tampered_plaintext)
        report(f"{label} corrupted block count", expected_count, actual_count)


def test_key_separation() -> None:
    """Confirm the HKDF interface returns the intended logical subkey lengths."""
    k0, k_f, k_g = derive_subkeys(MASTER_KEY)
    report("K0 length for AES-128-XTS", 32, len(k0))
    report("KF length for AES-128", 16, len(k_f))
    report("KG logical length", 32, len(k_g))
    report("XTS key halves are distinct", True, k0[:16] != k0[16:])
    report("G subkeys are distinct", True, k_g[:16] != k_g[16:])


def main() -> None:
    print(f"{YELLOW}{BOLD}Ratcheted AES-XTS functionality checks{RESET}\n")
    test_raw_xts_roundtrip()
    test_baseline_roundtrip()
    test_ratcheted_roundtrips()
    test_length_preservation()
    test_position_variability_and_determinism()
    test_random_access()
    test_tamper_propagation()
    test_key_separation()
    print(f"{GREEN}{BOLD}ALL FUNCTIONALITY TESTS PASSED{RESET}")


if __name__ == "__main__":
    main()
