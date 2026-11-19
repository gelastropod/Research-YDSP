"""48-byte context -> 16-byte mask. Setup objects belong to one worker."""
import hashlib
from blake3 import blake3
from Crypto.Cipher import AES
from Crypto.Hash import KMAC128
from nacl.bindings import crypto_shorthash_siphashx24
from Crypto.Cipher._mode_gcm import _GHASH, _ghash_clmul, _ghash_portable

NAMES = ('kmac128', 'blake3', 'blake2s', 'blake2b', 'siphash128', 'lrw_poly', 'cbc_mac')

def xor(a, b):
    return (int.from_bytes(a, 'big') ^ int.from_bytes(b, 'big')).to_bytes(16, 'big')

def make_mask(name, key, aesni=True):
    """Return a reusable keyed function; each evaluation returns exactly 16 bytes."""
    if len(key) != 32:
        raise ValueError('The benchmark mask-key container must have 32 bytes')
    if name == 'kmac128':
        return lambda x: KMAC128.new(key=key, data=x, mac_len=16, custom=b'').digest()
    if name in ('blake2s', 'blake2b', 'blake3'):
        base = blake3(key=key) if name == 'blake3' else getattr(hashlib, name)(key=key, digest_size=16)
        def h(x):
            state = base.copy()
            state.update(x)
            return state.digest(length=16) if name == 'blake3' else state.digest()
        return h
    if name == 'siphash128':
        return lambda x: crypto_shorthash_siphashx24(x, key[:16])
    if name == 'lrw_poly':
        if key[:16] == bytes(16):
            raise ValueError('LRW polynomial field key must be nonzero')
        # Reverse coefficient bits to convert the document's LSB convention
        # to GHASH's MSB convention. One immutable expanded key per worker.
        reverse = bytes(int(f'{i:08b}'[::-1],2) for i in range(256))
        def rev(b):return b.translate(reverse)[::-1]
        implementation = _ghash_clmul or _ghash_portable
        base = _GHASH(rev(key[:16]), implementation)
        from Crypto.Util._raw_api import create_string_buffer, c_uint8_ptr, c_size_t, get_raw_buffer
        def h(x):
            if len(x)!=48:raise ValueError('LRW polynomial domain is 48 bytes')
            mapped = b''.join(rev(x[i:i+16]) for i in (0,16,32))
            result = create_string_buffer(16)
            status = base._ghash(result,c_uint8_ptr(mapped),c_size_t(48),result,base._exp_key.get())
            if status:raise ValueError('Native polynomial multiplication failed')
            return rev(get_raw_buffer(result))
        return h
    if name == 'cbc_mac':
        cipher = AES.new(key, AES.MODE_ECB, use_aesni=aesni)
        def h(x):
            if len(x) != 48:
                raise ValueError('CBC-MAC mask has a fixed 48-byte domain')
            state = bytes(16)
            for i in range(0, 48, 16):
                state = cipher.encrypt(xor(state, x[i:i+16]))
            return state
        return h
    raise ValueError(f'Unknown mask {name!r}; choose from {NAMES}')
