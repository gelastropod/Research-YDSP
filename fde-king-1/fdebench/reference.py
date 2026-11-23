"""AES-256 throughout. No padding, ciphertext stealing or authentication."""
from dataclasses import dataclass
from time import perf_counter_ns
import hashlib
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from .masks import make_mask, xor

DEFAULT_MASK = 'blake3'  # Change this one line to select another nominated mask.
MAX_BLOCKS = 4096
MASK128 = (1 << 128) - 1

def mul_alpha(t):
    return ((t << 1) & MASK128) ^ (0x87 if t >> 127 else 0)

def gf_xts(a, b):
    z = 0
    for _ in range(128):
        if b & 1:
            z ^= a
        a, b = mul_alpha(a), b >> 1
    return z

ALPHAS = [1]
for _ in range(MAX_BLOCKS-1):
    ALPHAS.append(mul_alpha(ALPHAS[-1]))
INDICES = tuple(i.to_bytes(16, 'big') for i in range(MAX_BLOCKS))

def sector_bytes(sector):
    if not isinstance(sector, int) or not 0 <= sector < (1 << 64):
        raise ValueError('sector must be an unsigned 64-bit integer')
    return sector.to_bytes(16, 'big')

@dataclass
class Cost:
    seed_ns: int = 0
    mask_ns: int = 0
    data_ns: int = 0
    library_ns: int = 0
    wall_ns: int = 0

class Engine:
    def __init__(self, scheme='xex', mask=None, key=None):
        if scheme not in ('xex','cbc_mac','lrw_poly','ecb_bulk','xts_manual_soft','xts_manual_ni','xts_library'):
            raise ValueError('Unknown encryption scheme')
        self.scheme = scheme
        self.mask_name = scheme if scheme in ('cbc_mac','lrw_poly') else (mask or DEFAULT_MASK)
        family = 'xts' if scheme.startswith('xts') else f'{scheme}:{self.mask_name}'
        if key is not None and (not isinstance(key, bytes) or len(key)!=64):
            raise ValueError('Volume key must be 64 bytes: K1 || K2')
        self.k1 = key[:32] if key is not None else hashlib.sha256(('mask:' + family).encode()).digest()
        self.k2 = key[32:] if key is not None else hashlib.sha256(('data:' + family).encode()).digest()
        self.aesni = scheme != 'xts_manual_soft'
        self.aes = AES.new(self.k2, AES.MODE_ECB, use_aesni=self.aesni)
        self.aux = AES.new(self.k1, AES.MODE_ECB, use_aesni=self.aesni)
        self.mask = make_mask(self.mask_name, self.k1, self.aesni) if scheme in ('xex','cbc_mac','lrw_poly') else None
        self.indices = INDICES
        self.xts_cipher = None

    @property
    def label(self):
        return f'xex_{self.mask_name}' if self.scheme == 'xex' else self.scheme

    @staticmethod
    def validate(data):
        if not data or len(data) % 16 or len(data) > MAX_BLOCKS*16:
            raise ValueError('A sector must contain 1..4096 complete AES blocks')

    def crypt(self, data, sector=0, decrypt=False, cost=None):
        self.validate(data)
        s = sector_bytes(sector)
        start = perf_counter_ns() if cost is not None else 0
        if self.scheme == 'ecb_bulk':
            out = self.aes.decrypt(data) if decrypt else self.aes.encrypt(data)
            if cost is not None:
                cost.data_ns += perf_counter_ns()-start
                cost.wall_ns += perf_counter_ns()-start
            return out
        if self.scheme == 'xts_library':
            cipher = Cipher(algorithms.AES(self.k2+self.k1), modes.XTS(s))
            op = cipher.decryptor() if decrypt else cipher.encryptor()
            out = op.update(data)+op.finalize()
            if cost is not None:
                cost.library_ns += perf_counter_ns()-start
                cost.wall_ns += perf_counter_ns()-start
            return out
        tick = perf_counter_ns() if cost is not None else 0
        t = int.from_bytes(self.aux.encrypt(s), 'little') if self.scheme.startswith('xts') else None
        a_s = self.aux.encrypt(s) if self.scheme == 'cbc_mac' else None
        if cost is not None:
            cost.seed_ns += perf_counter_ns()-tick
        previous = bytes(16)
        result = bytearray(len(data))
        aes_operation = self.aes.decrypt if decrypt else self.aes.encrypt
        for offset in range(0, len(data), 16):
            j = offset//16
            current = data[offset:offset+16]
            tick = perf_counter_ns() if cost is not None else 0
            if t is not None:
                delta = t.to_bytes(16, 'little')
                t = mul_alpha(t)
            elif a_s is not None:
                b = self.aux.encrypt(xor(self.indices[j], a_s))
                delta = self.aux.encrypt(xor(previous, b))
            else:
                delta = self.mask(s+self.indices[j]+previous)
            if cost is not None:
                cost.mask_ns += perf_counter_ns()-tick
                tick = perf_counter_ns()
            transformed = xor(aes_operation(xor(current, delta)), delta)
            result[offset:offset+16] = transformed
            if cost is not None:
                cost.data_ns += perf_counter_ns()-tick
            previous = current if decrypt else transformed
        if cost is not None:
            cost.wall_ns += perf_counter_ns()-start
        return bytes(result)

    def encrypt(self, plaintext, sector=0):
        return self.crypt(plaintext, sector)

    def decrypt(self, ciphertext, sector=0):
        return self.crypt(ciphertext, sector, True)

    def decrypt_block(self, ciphertext, sector, j):
        """Zero-based j. The library-XTS control deliberately reads the full sector."""
        self.validate(ciphertext)
        if not 0 <= j < len(ciphertext)//16:
            raise IndexError('Block index outside sector')
        if self.scheme == 'xts_library':
            return self.decrypt(ciphertext, sector)[16*j:16*(j+1)]
        c = ciphertext[16*j:16*(j+1)]
        if self.scheme == 'ecb_bulk':
            return self.aes.decrypt(c)
        s = sector_bytes(sector)
        if self.scheme.startswith('xts'):
            seed = int.from_bytes(self.aux.encrypt(s), 'little')
            delta = gf_xts(seed, ALPHAS[j]).to_bytes(16, 'little')
        else:
            previous = ciphertext[16*(j-1):16*j] if j else bytes(16)
            delta = self.mask(s+self.indices[j]+previous)
        return xor(self.aes.decrypt(xor(c, delta)), delta)

    def decrypt_range(self, ciphertext, sector, lo, hi):
        """Independent contiguous range, keeping original sector indices/feedback."""
        self.validate(ciphertext)
        if not 0 <= lo <= hi <= len(ciphertext)//16:
            raise IndexError('Invalid block range')
        if lo == hi:
            return b''
        if self.scheme == 'xts_library':
            raise ValueError('Full-sector library control has no offset-range API')
        if self.scheme == 'ecb_bulk':
            return self.aes.decrypt(ciphertext[16*lo:16*hi])
        s = sector_bytes(sector)
        t = gf_xts(int.from_bytes(self.aux.encrypt(s), 'little'), ALPHAS[lo]) if self.scheme.startswith('xts') else None
        a_s = self.aux.encrypt(s) if self.scheme == 'cbc_mac' else None
        out = bytearray()
        for j in range(lo, hi):
            c = ciphertext[16*j:16*(j+1)]
            prev = ciphertext[16*(j-1):16*j] if j else bytes(16)
            if t is not None:
                delta, t = t.to_bytes(16, 'little'), mul_alpha(t)
            elif a_s is not None:
                delta = self.aux.encrypt(xor(prev, self.aux.encrypt(xor(self.indices[j], a_s))))
            else:
                delta = self.mask(s+self.indices[j]+prev)
            out.extend(xor(self.aes.decrypt(xor(c, delta)), delta))
        return bytes(out)

def encrypt_sector(plaintext, sector, *, mask=None, key=None):
    """Simple full-encryption entry point. Reuse Engine for measured batches."""
    return Engine('xex', mask=mask, key=key).encrypt(plaintext, sector)

# Baselines and the three separately named feedback construction families.
def schemes():
    return [('ecb_bulk', None), ('xts_manual_soft', None), ('xts_manual_ni', None), ('xts_library', None)] + [
        ('xex', name) for name in ('kmac128','blake3','blake2s','blake2b','siphash128')] + [('cbc_mac',None),('lrw_poly',None)]

def build(label):
    return Engine('xex', label[4:]) if label.startswith('xex_') else Engine(label)
