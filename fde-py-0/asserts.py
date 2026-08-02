from __future__ import annotations

from ratchet_fde import (
    RatchetedFDE,
    count_corrupted_blocks,
    flip_bit,
)


MASTER_KEY = b"assert test master key for ratcheted fde".ljust(32, b"\x00")
BLOCKS_PER_SECTOR = 4
NUM_SECTORS = 4


def make_structured_volume(num_sectors: int, sector_size: int) -> bytes:
    """
    Create deterministic plaintext with visible sector labels.

    This is useful for experiments because the plaintext is structured rather
    than purely random. If decryption fails or corruption propagates, block-level
    differences are easier to reason about.
    """
    sectors = []
    for lba in range(num_sectors):
        label = f"LBA={lba:04d}|".encode()
        sector = (label * ((sector_size // len(label)) + 1))[:sector_size]
        sectors.append(sector)
    return b"".join(sectors)


def test_case_13_sector_roundtrip() -> None:
    """
    Case 13: sector-mode encryption/decryption roundtrip.

    Under the hood:
    - The volume is one sector long: 4 blocks x 16 bytes = 64 bytes.
    - The sector starts from an initial state determined by the master key and LBA.
    - The ratchet evolves inside the sector.
    - Decryption recomputes the same state sequence and recovers the plaintext.

    Expected result:
        decrypt(encrypt(P)) == P
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="sector")
    plaintext = b"A" * 64
    ciphertext = model.encrypt_volume(plaintext)
    recovered = model.decrypt_volume(ciphertext)

    assert recovered == plaintext
    print("[PASS] case 13: sector-mode roundtrip")


def test_case_14_global_roundtrip() -> None:
    """
    Case 14: global-mode encryption/decryption roundtrip.

    Under the hood:
    - With only one sector, global mode still decrypts correctly.
    - The important distinction appears only across multiple sectors.
    - Global mode is correct when encryption and decryption are both sequential.

    Expected result:
        decrypt(encrypt(P)) == P
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="global")
    plaintext = b"A" * 64
    ciphertext = model.encrypt_volume(plaintext)
    recovered = model.decrypt_volume(ciphertext)

    assert recovered == plaintext
    print("[PASS] case 14: global-mode roundtrip")


def test_length_preservation() -> None:
    """
    FDE-style encryption must be length-preserving.

    Disk sectors cannot usually grow after encryption because the storage layer
    expects fixed-size blocks. This is one reason ordinary AEAD tags and stored
    nonces are awkward in traditional FDE.

    Expected result:
        len(C) == len(P)
    """
    plaintext = b"B" * 256

    for scope in ("sector", "global"):
        model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope=scope)
        ciphertext = model.encrypt_volume(plaintext)

        assert len(ciphertext) == len(plaintext)
        assert model.decrypt_volume(ciphertext) == plaintext

    print("[PASS] length preservation in sector and global modes")


def test_same_lba_same_plaintext_is_deterministic() -> None:
    """
    Same LBA, same key, same plaintext gives the same ciphertext.

    This models deterministic FDE behaviour. The scheme has no stored nonce or
    random per-write value, so encryption at the same logical position is
    repeatable.

    Expected result:
        Enc(LBA=5, P) == Enc(LBA=5, P)
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="sector")
    plaintext_sector = b"C" * model.sector_size

    c1, _ = model.encrypt_sector(5, plaintext_sector)
    c2, _ = model.encrypt_sector(5, plaintext_sector)

    assert c1 == c2
    print("[PASS] same LBA and same plaintext are deterministic")


def test_different_lba_same_plaintext_differs() -> None:
    """
    Different LBA, same key, same plaintext gives different ciphertext.

    The initial tweak state is derived from the LBA. Therefore, sector 0 and
    sector 1 should not encrypt the same plaintext sector to the same ciphertext.

    Expected result:
        Enc(LBA=0, P) != Enc(LBA=1, P)
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="sector")
    plaintext_sector = b"D" * model.sector_size

    c0, _ = model.encrypt_sector(0, plaintext_sector)
    c1, _ = model.encrypt_sector(1, plaintext_sector)

    assert c0 != c1
    print("[PASS] different LBAs produce different ciphertexts for same plaintext")


def test_sector_random_access() -> None:
    """
    Sector-scoped ratcheting preserves sector-level random access.

    Under the hood:
    - Each sector starts from K_0 and T_0 = encode(LBA).
    - The ratchet does not depend on previous sectors.
    - Therefore sector 3 can be decrypted directly.

    Expected result:
        direct decrypt of LBA 3 succeeds
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="sector")
    plaintext = make_structured_volume(NUM_SECTORS, model.sector_size)
    ciphertext = model.encrypt_volume(plaintext)

    lba = 3
    off = lba * model.sector_size
    sector_ciphertext = ciphertext[off:off + model.sector_size]
    sector_plaintext, _ = model.decrypt_sector(lba, sector_ciphertext)

    assert sector_plaintext == plaintext[off:off + model.sector_size]
    print("[PASS] sector mode supports direct random access to LBA 3")


def test_global_random_access_failure() -> None:
    """
    Global ratcheting does not preserve direct random access.

    Under the hood:
    - The initial state of sector 3 is not simply encode(LBA=3).
    - It is the state obtained after processing sectors 0, 1, and 2.
    - If we jump directly to sector 3, decryption starts from the wrong state.

    Expected result:
        direct decrypt of LBA 3 fails in global mode
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="global")
    plaintext = make_structured_volume(NUM_SECTORS, model.sector_size)
    ciphertext = model.encrypt_volume(plaintext)

    lba = 3
    off = lba * model.sector_size
    sector_ciphertext = ciphertext[off:off + model.sector_size]
    wrong_plaintext, _ = model.decrypt_sector(lba, sector_ciphertext)

    assert wrong_plaintext != plaintext[off:off + model.sector_size]
    assert model.decrypt_volume(ciphertext) == plaintext
    print("[PASS] global mode requires previous state for LBA 3")


def test_sector_tamper_propagation_count() -> None:
    """
    In sector mode, tampering propagates only within the current sector.

    Current parameters:
    - 4 sectors
    - 4 blocks per sector
    - 16 total AES-sized blocks

    If byte 0 is flipped, it is inside the first block of the first sector.
    Because the ratchet is sector-local, all 4 blocks of that sector are corrupted,
    but later sectors remain unaffected.

    Expected result:
        corrupted block count == 4
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="sector")
    plaintext = make_structured_volume(NUM_SECTORS, model.sector_size)
    ciphertext = model.encrypt_volume(plaintext)
    tampered_ciphertext = flip_bit(ciphertext, 0)
    tampered_plaintext = model.decrypt_volume(tampered_ciphertext)

    corrupted_blocks = count_corrupted_blocks(plaintext, tampered_plaintext)

    assert corrupted_blocks == 4
    print("[PASS] sector tamper propagation corrupts exactly 4 blocks")


def test_global_tamper_propagation_count() -> None:
    """
    In global mode, tampering propagates across the whole remaining chain.

    Current parameters:
    - 4 sectors
    - 4 blocks per sector
    - 16 total AES-sized blocks

    If byte 0 is flipped, the first decrypted block is corrupted. Since the
    ciphertext also feeds the next key/tweak state, every later state becomes
    wrong, so all later blocks also decrypt wrongly.

    Expected result:
        corrupted block count == 16
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="global")
    plaintext = make_structured_volume(NUM_SECTORS, model.sector_size)
    ciphertext = model.encrypt_volume(plaintext)
    tampered_ciphertext = flip_bit(ciphertext, 0)
    tampered_plaintext = model.decrypt_volume(tampered_ciphertext)

    corrupted_blocks = count_corrupted_blocks(plaintext, tampered_plaintext)

    assert corrupted_blocks == 16
    print("[PASS] global tamper propagation corrupts exactly 16 blocks")


def test_tampering_is_not_authentication() -> None:
    """
    Corruption propagation is not authentication.

    The scheme does not output a rejection symbol. Even when the ciphertext is
    modified, decryption still returns bytes. Those bytes are wrong, but the
    decryptor does not know that they are wrong.

    Expected result:
        tampered plaintext differs from original, but no exception is raised
    """
    model = RatchetedFDE(MASTER_KEY, blocks_per_sector=4, scope="sector")
    plaintext = make_structured_volume(NUM_SECTORS, model.sector_size)
    ciphertext = model.encrypt_volume(plaintext)
    tampered_ciphertext = flip_bit(ciphertext, 0)

    tampered_plaintext = model.decrypt_volume(tampered_ciphertext)

    assert tampered_plaintext != plaintext
    assert isinstance(tampered_plaintext, bytes)
    print("[PASS] tampering corrupts output but does not authenticate/reject")


def run_all_tests() -> None:
    """
    Run all assert-based experiments.

    If the script finishes and prints all PASS lines, the prototype is behaving
    as expected. If an assertion fails, Python raises AssertionError and stops.
    """
    test_case_13_sector_roundtrip()
    test_case_14_global_roundtrip()
    test_length_preservation()
    test_same_lba_same_plaintext_is_deterministic()
    test_different_lba_same_plaintext_differs()
    test_sector_random_access()
    test_global_random_access_failure()
    test_sector_tamper_propagation_count()
    test_global_tamper_propagation_count()
    test_tampering_is_not_authentication()
    print("[ALL PASS] ratcheted FDE assert cases completed successfully")


if __name__ == "__main__":
    run_all_tests()
