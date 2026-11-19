"""48-byte context -> 16-byte mask. Setup objects belong to one worker."""
import hashlib
from blake3 import blake3
from Crypto.Cipher import AES
from Crypto.Hash import KMAC128
from nacl.bindings import crypto_shorthash_siphashx24
from Crypto.Cipher._mode_gcm import _GHASH, _ghash_clmul, _ghash_portable
from Crypto.Util._raw_api import create_string_buffer,c_uint8_ptr,c_size_t,get_raw_buffer

NAMES = ('kmac128', 'blake3', 'blake2s', 'blake2b', 'siphash128', 'lrw_horner', 'lrw_precompute', 'cbc_mac')

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
    if name in ('lrw_poly','lrw_horner'):
        if key[:16] == bytes(16):
            raise ValueError('LRW polynomial field key must be nonzero')
        # Reverse coefficient bits to convert the document's LSB convention
        # to GHASH's MSB convention. One immutable expanded key per worker.
        reverse = REVERSE_BITS
        def rev(b):return b.translate(reverse)[::-1]
        implementation = _ghash_clmul or _ghash_portable
        base = _GHASH(rev(key[:16]), implementation)
        def h(x):
            if len(x)!=48:raise ValueError('LRW polynomial domain is 48 bytes')
            mapped = b''.join(rev(x[i:i+16]) for i in (0,16,32))
            result = create_string_buffer(16)
            status = base._ghash(result,c_uint8_ptr(mapped),c_size_t(48),result,base._exp_key.get())
            if status:raise ValueError('Native polynomial multiplication failed')
            return rev(get_raw_buffer(result))
        return h
    if name == 'lrw_precompute':
        return LRWPrecompute(key).full
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


REVERSE_BITS = bytes(int(f'{i:08b}'[::-1], 2) for i in range(256))
def reverse_field(b):return b.translate(REVERSE_BITS)[::-1]

def field_reference(a,b):
    z=0
    for _ in range(128):
        if b&1:z^=a
        a=((a<<1)&((1<<128)-1))^(0x87 if a>>127 else 0)
        b>>=1
    return z

class NativeField:
    """LSB-coefficient convention, matching the document's GF128_MUL."""
    def __init__(self,key):
        self.base=_GHASH(reverse_field(key), _ghash_clmul or _ghash_portable)
        self.operation=self.base._ghash
        self.expanded=self.base._exp_key.get()
    def __call__(self,value):
        result=create_string_buffer(16)
        status=self.operation(result,c_uint8_ptr(reverse_field(value)),c_size_t(16),result,self.expanded)
        if status:raise ValueError('Native field multiplication failed')
        return reverse_field(get_raw_buffer(result))

class LRWPrecompute:
    """delta = S*a^3 XOR I*a^2 XOR Cprev*a; no sector-result caching."""
    def __init__(self,key,blocks=256):
        a=int.from_bytes(key[:16],'big')
        if not a:raise ValueError('LRW field key must be nonzero')
        a2=field_reference(a,a);a3=field_reference(a2,a)
        self.mul_a=NativeField(a.to_bytes(16,'big'))
        self.mul_a2=NativeField(a2.to_bytes(16,'big'))
        self.mul_a3=NativeField(a3.to_bytes(16,'big'))
        self.positions=bytearray()
        self.ensure(blocks)
    def ensure(self,blocks):
        if not 0<=blocks<=4096:raise ValueError('At most 4096 table positions')
        for j in range(len(self.positions)//16,blocks):
            self.positions.extend(self.mul_a2(j.to_bytes(16,'big')))
    @property
    def table_bytes(self):return len(self.positions)
    def sector(self,s,blocks):
        self.ensure(blocks)
        return int.from_bytes(self.mul_a3(s),'big')
    def block(self,sector_term,j,previous):
        return (sector_term ^ int.from_bytes(self.positions[16*j:16*j+16],'big') ^ int.from_bytes(self.mul_a(previous),'big')).to_bytes(16,'big')
    def full(self,context):
        if len(context)!=48:raise ValueError('LRW context must be 48 bytes')
        j=int.from_bytes(context[16:32],'big')
        position=(self.positions[j*16:j*16+16] if j<len(self.positions)//16
                  else self.mul_a2(context[16:32]))
        return xor(xor(self.mul_a3(context[:16]),position),self.mul_a(context[32:]))
