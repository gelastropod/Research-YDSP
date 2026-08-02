"""
ratchet_fde.py

Research prototype for ciphertext-dependent ratcheting over real AES-XTS.

This module provides two constructions:

1. BaselineXTSFDE
   Conventional no-expansion AES-XTS at sector/data-unit granularity. A fixed
   AES-XTS key is used, while the 16-byte XTS tweak is derived from the LBA.

2. RatchetedXTSFDE
   A research construction that invokes AES-XTS on one 16-byte block per
   ratchet step. After block i is encrypted, its ciphertext C_i updates an
   internal XTS tweak state and the next 256-bit AES-128-XTS key:

       T_{i+1} = AES_{K_F}(C_i)

       K_{i+1,L} = AES_{K_{G,L}}(K_{i,L} xor C_i)
       K_{i+1,R} = AES_{K_{G,R}}(K_{i,R} xor C_i)
       K_{i+1}   = K_{i+1,L} || K_{i+1,R}

   K_F, K_{G,L}, and K_{G,R} are fixed secret subkeys. The evolving XTS key
   K_i is input data to G; it is never reused as the key of F or G.

The two 128-bit halves of K_i form the double-length key required by
AES-128-XTS. The public LBA seeds the initial 128-bit tweak state. Subsequent
ratcheted tweak states are secret internal state, not public TBC tweaks.

This is not a production FDE implementation and provides confidentiality only.
Ciphertext corruption may propagate, but the construction does not authenticate
or reject modified ciphertext.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


BLOCK_SIZE = 16
AES_128_XTS_KEY_SIZE = 32
MASTER_EXPANSION_SIZE = 80  # K0 (32) || KF (16) || KG (32)


class RatchetError(ValueError):
    """Raised when an input violates the prototype's cryptographic interface."""


def xor_bytes(*values: bytes) -> bytes:
    """XOR equal-length byte strings."""
    if not values:
        raise RatchetError("xor_bytes requires at least one input")
    length = len(values[0])
    if any(len(value) != length for value in values):
        raise RatchetError("all XOR inputs must have equal length")
    result = bytearray(length)
    for value in values:
        for index, byte in enumerate(value):
            result[index] ^= byte
    return bytes(result)


def encode_lba(lba: int) -> bytes:
    """
    Encode a logical block address as the 16-byte XTS data-unit tweak.

    Little-endian encoding is common in storage implementations. The crucial
    property for this prototype is that the encoding is deterministic and
    injective over the supported LBA range.
    """
    if lba < 0 or lba >= 2**128:
        raise RatchetError("LBA must be in the interval [0, 2^128)")
    return lba.to_bytes(BLOCK_SIZE, "little")


def aes_block_encrypt(key: bytes, block: bytes) -> bytes:
    """Encrypt one 128-bit block with AES-ECB as an internal PRP primitive."""
    if len(block) != BLOCK_SIZE:
        raise RatchetError("AES input must be exactly 16 bytes")
    if len(key) not in (16, 24, 32):
        raise RatchetError("AES key must be 16, 24, or 32 bytes")
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(block) + encryptor.finalize()


def derive_subkeys(master_key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Derive three logically independent subkeys from one master secret.

    Returns:
        K0: 32-byte initial AES-128-XTS key.
        KF: 16-byte AES-128 key for the tweak-ratchet permutation F.
        KG: 32-byte logical key, split into independent AES-128 keys
            K_G,L || K_G,R for the 256-bit key-ratchet permutation G.
    """
    if len(master_key) < 16:
        raise RatchetError("master_key must contain at least 128 bits")

    material = HKDF(
        algorithm=hashes.SHA256(),
        length=MASTER_EXPANSION_SIZE,
        salt=None,
        info=b"ratcheted-aes-xts-fde:v2:key-separation",
    ).derive(master_key)

    k0 = material[:32]
    k_f = material[32:48]
    k_g = material[48:80]

    # OpenSSL rejects an XTS key whose two AES subkeys are identical. HKDF makes
    # this event negligible, but fail explicitly rather than silently.
    if k0[:16] == k0[16:]:
        raise RatchetError("derived XTS subkeys unexpectedly coincide")
    return k0, k_f, k_g


def xts_encrypt_data_unit(xts_key: bytes, tweak: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt one XTS data unit using pyca/cryptography's AES-XTS implementation.

    AES-128-XTS requires a 32-byte double-length key and a 16-byte tweak. XTS
    supports ciphertext stealing and therefore does not require padding, but a
    data unit must contain at least one 16-byte AES block.
    """
    _validate_xts_inputs(xts_key, tweak, plaintext)
    encryptor = Cipher(algorithms.AES(xts_key), modes.XTS(tweak)).encryptor()
    return encryptor.update(plaintext) + encryptor.finalize()


def xts_decrypt_data_unit(xts_key: bytes, tweak: bytes, ciphertext: bytes) -> bytes:
    """Decrypt one AES-XTS data unit."""
    _validate_xts_inputs(xts_key, tweak, ciphertext)
    decryptor = Cipher(algorithms.AES(xts_key), modes.XTS(tweak)).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def _validate_xts_inputs(xts_key: bytes, tweak: bytes, data: bytes) -> None:
    if len(xts_key) not in (32, 64):
        raise RatchetError("XTS key must be 32 bytes (AES-128-XTS) or 64 bytes (AES-256-XTS)")
    if len(tweak) != BLOCK_SIZE:
        raise RatchetError("XTS tweak must be exactly 16 bytes")
    if len(data) < BLOCK_SIZE:
        raise RatchetError("an XTS data unit must contain at least 16 bytes")


def ratchet_tweak(k_f: bytes, ciphertext_block: bytes) -> bytes:
    """
    F_{K_F}(C_i) = AES_{K_F}(C_i).

    The output is an internal secret XTS tweak state. It is not claimed to be a
    public tweak in the conventional tweakable-block-cipher interface.
    """
    return aes_block_encrypt(k_f, ciphertext_block)


def ratchet_xts_key(k_g: bytes, current_xts_key: bytes, ciphertext_block: bytes) -> bytes:
    """
    Lift the write-up's 128-bit G construction to a 256-bit AES-128-XTS key.

    Let K_i = K_{i,L} || K_{i,R} and K_G = K_{G,L} || K_{G,R}. Then:

        K_{i+1,L} = AES_{K_{G,L}}(K_{i,L} xor C_i)
        K_{i+1,R} = AES_{K_{G,R}}(K_{i,R} xor C_i)

    The two fixed AES keys implement one logical 256-bit update function G.
    Key separation prevents the evolving XTS key from being reused as the key
    of the ratchet primitive.
    """
    if len(k_g) != 32:
        raise RatchetError("K_G must be 32 bytes: K_G,L || K_G,R")
    if len(current_xts_key) != AES_128_XTS_KEY_SIZE:
        raise RatchetError("the evolving AES-128-XTS key must be 32 bytes")
    if len(ciphertext_block) != BLOCK_SIZE:
        raise RatchetError("ciphertext_block must be exactly 16 bytes")

    current_left, current_right = current_xts_key[:16], current_xts_key[16:]
    k_g_left, k_g_right = k_g[:16], k_g[16:]

    next_left = aes_block_encrypt(k_g_left, xor_bytes(current_left, ciphertext_block))
    next_right = aes_block_encrypt(k_g_right, xor_bytes(current_right, ciphertext_block))
    next_key = next_left + next_right

    if next_left == next_right:
        # An equal-half XTS key is invalid. Under independent PRP keys this is a
        # negligible 2^-128 event; surface it explicitly for experimental code.
        raise RatchetError("ratchet produced an invalid equal-half XTS key")
    return next_key


@dataclass(frozen=True)
class RatchetState:
    """Secret state required to continue a ciphertext-dependent chain."""

    xts_key: bytes
    tweak: bytes


class BaselineXTSFDE:
    """
    Conventional sector-level AES-128-XTS baseline.

    Each sector is one XTS data unit. The fixed key is K0 and the public tweak is
    encode_lba(lba). Sectors are independently encryptable and decryptable.
    """

    def __init__(self, master_key: bytes, blocks_per_sector: int = 32):
        if blocks_per_sector <= 0:
            raise RatchetError("blocks_per_sector must be positive")
        self.xts_key, _, _ = derive_subkeys(master_key)
        self.blocks_per_sector = blocks_per_sector
        self.sector_size = blocks_per_sector * BLOCK_SIZE

    def encrypt_sector(self, lba: int, plaintext_sector: bytes) -> bytes:
        self._validate_sector(plaintext_sector)
        return xts_encrypt_data_unit(self.xts_key, encode_lba(lba), plaintext_sector)

    def decrypt_sector(self, lba: int, ciphertext_sector: bytes) -> bytes:
        self._validate_sector(ciphertext_sector)
        return xts_decrypt_data_unit(self.xts_key, encode_lba(lba), ciphertext_sector)

    def encrypt_volume(self, plaintext: bytes) -> bytes:
        self._validate_volume(plaintext)
        return b"".join(
            self.encrypt_sector(lba, plaintext[offset:offset + self.sector_size])
            for lba, offset in enumerate(range(0, len(plaintext), self.sector_size))
        )

    def decrypt_volume(self, ciphertext: bytes) -> bytes:
        self._validate_volume(ciphertext)
        return b"".join(
            self.decrypt_sector(lba, ciphertext[offset:offset + self.sector_size])
            for lba, offset in enumerate(range(0, len(ciphertext), self.sector_size))
        )

    def _validate_sector(self, data: bytes) -> None:
        if len(data) != self.sector_size:
            raise RatchetError(f"sector must be exactly {self.sector_size} bytes")

    def _validate_volume(self, data: bytes) -> None:
        if len(data) % self.sector_size != 0:
            raise RatchetError("volume length must be a multiple of sector_size")


class RatchetedXTSFDE:
    """
    Ciphertext-dependent AES-XTS research construction.

    scope="sector":
        The chain resets at each sector using K0 and T0=encode_lba(lba).
        Sector-level random access is preserved. Corruption propagation is
        bounded by the sector.

    scope="global":
        The final state of one sector seeds the next sector. Corruption can
        propagate across the full remaining chain, but direct random access is
        lost unless the preceding state is available.

    To follow the block-level recurrence in the write-up, each 16-byte block is
    passed to a real AES-XTS invocation as a one-block XTS data unit. This is an
    experimental composition, not the conventional IEEE 1619 usage in which a
    whole sector is one XTS data unit under a fixed XTS key.
    """

    def __init__(self, master_key: bytes, blocks_per_sector: int = 32, scope: str = "sector"):
        if blocks_per_sector <= 0:
            raise RatchetError("blocks_per_sector must be positive")
        if scope not in {"sector", "global"}:
            raise RatchetError("scope must be 'sector' or 'global'")

        self.k0, self.k_f, self.k_g = derive_subkeys(master_key)
        self.blocks_per_sector = blocks_per_sector
        self.sector_size = blocks_per_sector * BLOCK_SIZE
        self.scope = scope

    def initial_state(self, lba: int) -> RatchetState:
        return RatchetState(xts_key=self.k0, tweak=encode_lba(lba))

    def encrypt_sector(
        self,
        lba: int,
        plaintext_sector: bytes,
        state: Optional[RatchetState] = None,
    ) -> Tuple[bytes, RatchetState]:
        self._validate_sector(plaintext_sector)
        current = state if state is not None else self.initial_state(lba)
        output = bytearray()

        for offset in range(0, self.sector_size, BLOCK_SIZE):
            plaintext_block = plaintext_sector[offset:offset + BLOCK_SIZE]
            ciphertext_block = xts_encrypt_data_unit(
                current.xts_key,
                current.tweak,
                plaintext_block,
            )
            output.extend(ciphertext_block)
            current = RatchetState(
                xts_key=ratchet_xts_key(self.k_g, current.xts_key, ciphertext_block),
                tweak=ratchet_tweak(self.k_f, ciphertext_block),
            )

        return bytes(output), current

    def decrypt_sector(
        self,
        lba: int,
        ciphertext_sector: bytes,
        state: Optional[RatchetState] = None,
    ) -> Tuple[bytes, RatchetState]:
        self._validate_sector(ciphertext_sector)
        current = state if state is not None else self.initial_state(lba)
        output = bytearray()

        for offset in range(0, self.sector_size, BLOCK_SIZE):
            ciphertext_block = ciphertext_sector[offset:offset + BLOCK_SIZE]
            plaintext_block = xts_decrypt_data_unit(
                current.xts_key,
                current.tweak,
                ciphertext_block,
            )
            output.extend(plaintext_block)
            current = RatchetState(
                xts_key=ratchet_xts_key(self.k_g, current.xts_key, ciphertext_block),
                tweak=ratchet_tweak(self.k_f, ciphertext_block),
            )

        return bytes(output), current

    def encrypt_volume(self, plaintext: bytes) -> bytes:
        self._validate_volume(plaintext)
        output = bytearray()
        state: Optional[RatchetState] = None

        for lba, offset in enumerate(range(0, len(plaintext), self.sector_size)):
            sector = plaintext[offset:offset + self.sector_size]
            if self.scope == "sector":
                ciphertext_sector, _ = self.encrypt_sector(lba, sector)
            else:
                if lba == 0:
                    state = self.initial_state(0)
                ciphertext_sector, state = self.encrypt_sector(lba, sector, state)
            output.extend(ciphertext_sector)
        return bytes(output)

    def decrypt_volume(self, ciphertext: bytes) -> bytes:
        self._validate_volume(ciphertext)
        output = bytearray()
        state: Optional[RatchetState] = None

        for lba, offset in enumerate(range(0, len(ciphertext), self.sector_size)):
            sector = ciphertext[offset:offset + self.sector_size]
            if self.scope == "sector":
                plaintext_sector, _ = self.decrypt_sector(lba, sector)
            else:
                if lba == 0:
                    state = self.initial_state(0)
                plaintext_sector, state = self.decrypt_sector(lba, sector, state)
            output.extend(plaintext_sector)
        return bytes(output)

    def _validate_sector(self, data: bytes) -> None:
        if len(data) != self.sector_size:
            raise RatchetError(f"sector must be exactly {self.sector_size} bytes")

    def _validate_volume(self, data: bytes) -> None:
        if len(data) % self.sector_size != 0:
            raise RatchetError("volume length must be a multiple of sector_size")


def flip_bit(data: bytes, byte_index: int, bit_mask: int = 0x01) -> bytes:
    """Return a copy with one selected bit mask XORed into one byte."""
    if byte_index < 0 or byte_index >= len(data):
        raise RatchetError("byte_index is outside the data buffer")
    modified = bytearray(data)
    modified[byte_index] ^= bit_mask
    return bytes(modified)


def count_corrupted_blocks(reference: bytes, candidate: bytes) -> int:
    """Count 16-byte blocks that differ between two equal-length buffers."""
    if len(reference) != len(candidate):
        raise RatchetError("buffers must have equal length")
    return sum(
        reference[offset:offset + BLOCK_SIZE] != candidate[offset:offset + BLOCK_SIZE]
        for offset in range(0, len(reference), BLOCK_SIZE)
    )
