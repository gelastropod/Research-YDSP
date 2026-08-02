"""
ratchet_fde.py

A research prototype for studying ciphertext-dependent ratcheting in a
full-disk-encryption-like setting.

Core construction, per 128-bit block:
    C_i = AES_{K_i}(P_i xor T_i) xor T_i
    T_{i+1} = F_{K_F}(C_i) = AES_{K_F}(C_i)
    K_{i+1} = G_{K_G}(K_i xor C_i) = AES_{K_G}(K_i xor C_i)

The important modelling choice is key separation:
    - K_i is the evolving data-encryption key state.
    - K_F is the fixed secret key for the tweak-ratchet permutation F.
    - K_G is the fixed secret key for the key-ratchet permutation G.
K_i is never reused as the key of F or G.

2 scopes are implemented:
    1. Sector scope: each sector starts from a deterministic initial state.
       Random access at sector granularity is preserved.
    2. Global scope: state carries across sectors.
       Stronger propagation, but random access is lost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
import os, time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


BLOCK_SIZE = 16


class RatchetError(ValueError):
    """Raised when inputs violate the toy model's block or sector constraints."""


def xor_bytes(a: bytes, b: bytes) -> bytes:
    """Length-checked XOR on two equal-sized buffers. Returns a new bytes object."""
    if len(a) != len(b):
        raise RatchetError("xor inputs must have equal length")
    return bytes(x ^ y for x, y in zip(a, b))


def aes_block_encrypt(key: bytes, block: bytes) -> bytes:
    """AES-ECB on one 128-bit block. Used only as a block-cipher primitive."""
    if len(block) != BLOCK_SIZE:
        raise RatchetError("AES block must be exactly 16 bytes")
    if len(key) not in (16, 24, 32):
        raise RatchetError("AES key must be 16, 24, or 32 bytes")
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    enc = cipher.encryptor()
    return enc.update(block) + enc.finalize()


def aes_block_decrypt(key: bytes, block: bytes) -> bytes:
    if len(block) != BLOCK_SIZE:
        raise RatchetError("AES block must be exactly 16 bytes")
    if len(key) not in (16, 24, 32):
        raise RatchetError("AES key must be 16, 24, or 32 bytes")
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    dec = cipher.decryptor()
    return dec.update(block) + dec.finalize()


def expand_master_key(master_key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Expand a volume master key into three independent 128-bit subkeys:
        K0: initial data-encryption key state
        KF: fixed secret key for tweak-ratchet permutation F
        KG: fixed secret key for key-ratchet permutation G
    """
    if len(master_key) < 16:
        raise RatchetError("master_key should contain at least 128 bits")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=48,
        salt=None,
        info=b"ratcheted-fde-demo:v1:key-separation",
    )
    material = hkdf.derive(master_key)
    return material[:16], material[16:32], material[32:48]


def encode_lba(lba: int) -> bytes:
    """Public 128-bit initial tweak from a logical block address."""
    if lba < 0:
        raise RatchetError("LBA must be non-negative")
    return lba.to_bytes(16, "big")


def xex_encrypt_block(data_key: bytes, tweak_state: bytes, plaintext_block: bytes) -> bytes:
    """
    Toy XEX-like block encryption:
        C = AES_K(P xor T) xor T
    """
    if len(plaintext_block) != BLOCK_SIZE:
        raise RatchetError("plaintext block must be 16 bytes")
    masked = xor_bytes(plaintext_block, tweak_state)
    core = aes_block_encrypt(data_key, masked)
    return xor_bytes(core, tweak_state)


def xex_decrypt_block(data_key: bytes, tweak_state: bytes, ciphertext_block: bytes) -> bytes:
    """
    Toy XEX-like block decryption:
        P = AES_K^{-1}(C xor T) xor T
    """
    if len(ciphertext_block) != BLOCK_SIZE:
        raise RatchetError("ciphertext block must be 16 bytes")
    masked = xor_bytes(ciphertext_block, tweak_state)
    core = aes_block_decrypt(data_key, masked)
    return xor_bytes(core, tweak_state)


def update_state(data_key: bytes, tweak_state: bytes, ciphertext_block: bytes,
                 k_f: bytes, k_g: bytes) -> Tuple[bytes, bytes]:
    """
    Ciphertext-dependent ratchet step.

    T_{i+1} = AES_{K_F}(C_i)
    K_{i+1} = AES_{K_G}(K_i xor C_i)

    K_F and K_G are independent fixed subkeys. K_i is block input to G, not
    the key of G.
    """
    next_tweak = aes_block_encrypt(k_f, ciphertext_block)
    next_key = aes_block_encrypt(k_g, xor_bytes(data_key, ciphertext_block))
    return next_key, next_tweak


@dataclass(frozen=True)
class ChainState:
    data_key: bytes
    tweak_state: bytes


class RatchetedFDE:
    """
    Sector- or global-scoped ratcheted encryption model.

    scope="sector":
        Each sector starts at (K0, T0=LBA). Decrypting sector i requires
        only sector i's ciphertext and the master key, so sector-random-access
        is preserved. Tamper propagation is limited to later blocks in the
        same sector.

    scope="global":
        State carries from sector to sector. A change in an early sector affects
        all following sectors during decryption, but random access is lost.
    """

    def __init__(self, master_key: bytes, blocks_per_sector: int = 4, scope: str = "sector"):
        if blocks_per_sector <= 0:
            raise RatchetError("blocks_per_sector must be positive")
        if scope not in {"sector", "global"}:
            raise RatchetError("scope must be 'sector' or 'global'")
        self.master_key = master_key
        self.k0, self.k_f, self.k_g = expand_master_key(master_key)
        self.blocks_per_sector = blocks_per_sector
        self.sector_size = blocks_per_sector * BLOCK_SIZE
        self.scope = scope

    def initial_state(self, lba: int) -> ChainState:
        return ChainState(data_key=self.k0, tweak_state=encode_lba(lba))

    def encrypt_sector(self, lba: int, sector_plaintext: bytes,
                       state: Optional[ChainState] = None) -> Tuple[bytes, ChainState]:
        """Encrypt a single sector, returning the ciphertext and the final state."""
        if len(sector_plaintext) != self.sector_size:
            raise RatchetError(f"sector must be exactly {self.sector_size} bytes")
        st = state if state is not None else self.initial_state(lba)
        out = bytearray()
        data_key, tweak_state = st.data_key, st.tweak_state

        for off in range(0, len(sector_plaintext), BLOCK_SIZE):
            p = sector_plaintext[off:off + BLOCK_SIZE]
            c = xex_encrypt_block(data_key, tweak_state, p)
            out.extend(c)
            data_key, tweak_state = update_state(data_key, tweak_state, c, self.k_f, self.k_g)

        return bytes(out), ChainState(data_key, tweak_state)

    def decrypt_sector(self, lba: int, sector_ciphertext: bytes,
                       state: Optional[ChainState] = None) -> Tuple[bytes, ChainState]:
        """Decrypt a single sector, returning the plaintext and the final state."""
        if len(sector_ciphertext) != self.sector_size:
            raise RatchetError(f"sector must be exactly {self.sector_size} bytes")
        st = state if state is not None else self.initial_state(lba)
        out = bytearray()
        data_key, tweak_state = st.data_key, st.tweak_state

        for off in range(0, len(sector_ciphertext), BLOCK_SIZE):
            c = sector_ciphertext[off:off + BLOCK_SIZE]
            p = xex_decrypt_block(data_key, tweak_state, c)
            out.extend(p)
            data_key, tweak_state = update_state(data_key, tweak_state, c, self.k_f, self.k_g)

        return bytes(out), ChainState(data_key, tweak_state)

    def encrypt_volume(self, plaintext: bytes) -> bytes:
        """define volume: a sequence of sectors, each of sector_size bytes
        encrypts a volume, returning the ciphertext. The volume length must be a multiple of the sector size."""
        if len(plaintext) % self.sector_size != 0:
            raise RatchetError("volume length must be a multiple of the sector size")
        out = bytearray()
        global_state: Optional[ChainState] = None

        for lba, off in enumerate(range(0, len(plaintext), self.sector_size)):
            sector = plaintext[off:off + self.sector_size]
            if self.scope == "sector":
                c, _ = self.encrypt_sector(lba, sector, state=None)
            else:
                if lba == 0:
                    global_state = self.initial_state(0)
                c, global_state = self.encrypt_sector(lba, sector, state=global_state)
            out.extend(c)
        return bytes(out)

    def decrypt_volume(self, ciphertext: bytes) -> bytes:
        """decrypts a volume, returning the plaintext. The volume length must be a multiple of the sector size."""
        if len(ciphertext) % self.sector_size != 0:
            raise RatchetError("volume length must be a multiple of the sector size")
        out = bytearray()
        global_state: Optional[ChainState] = None

        for lba, off in enumerate(range(0, len(ciphertext), self.sector_size)):
            sector = ciphertext[off:off + self.sector_size]
            if self.scope == "sector":
                p, _ = self.decrypt_sector(lba, sector, state=None)
            else:
                if lba == 0:
                    global_state = self.initial_state(0)
                p, global_state = self.decrypt_sector(lba, sector, state=global_state)
            out.extend(p)
        return bytes(out)


def count_corrupted_blocks(reference: bytes, candidate: bytes) -> int:
    """Count the number of 16-byte blocks that differ between two equal-length buffers."""
    if len(reference) != len(candidate):
        raise RatchetError("buffers must have equal length")
    return sum(
        reference[i:i + BLOCK_SIZE] != candidate[i:i + BLOCK_SIZE]
        for i in range(0, len(reference), BLOCK_SIZE)
    )


def flip_bit(buf: bytes, byte_index: int, bit_mask: int = 0x01) -> bytes:
    """Return a new bytes object with one bit flipped in the input buffer."""
    if not (0 <= bit_mask < 256):
        raise RatchetError("bit_mask must be a byte value (0-255)")
    if byte_index < 0 or byte_index >= len(buf):
        raise RatchetError("byte_index out of range")
    b = bytearray(buf)
    b[byte_index] ^= bit_mask
    return bytes(b)
