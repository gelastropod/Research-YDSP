"""Full-block educational transforms; independent of any file or device API."""
import hashlib
import hmac
from blake3 import blake3
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from Crypto.Cipher import AES
from Crypto.Hash import CMAC, KMAC128
from Crypto.Util.strxor import strxor

MASKS = ("BLAKE3","BLAKE2s","HMAC-SHA256","CMAC","KMAC128","GHASH")
NAMES = ("ECB","XTS",*MASKS)
SECTOR0 = 37
ZERO = bytes(16)

def keys(seed):
    # Public fixture. Each role gets separately labelled bytes. Fixed across writes.
    def derive(role):
        return hmac.digest((seed + "/1198" if role=="ecb" else seed).encode(), b"penguin-demo/v1/"+role.encode(), "sha256")
    return {r:derive(r) for r in ("ecb","xts/data","xts/tweak","xex/data","xex/mask")}

def gf_mul(x, h):
    """NIST GHASH representation; x and h are big-endian block integers."""
    z, v = 0, h
    for bit in range(127,-1,-1):
        if x & (1<<bit): z ^= v
        v = (v>>1) ^ ((0xe1<<120) if v&1 else 0)
    return z

def ghash(h, context):
    # Project's drive variant: empty AAD, 48-byte context, GCM length block.
    if len(context)!=48 or len(h)!=16: raise ValueError("GHASH expects 16-byte H, 48-byte context")
    s=0
    h=int.from_bytes(h,"big")
    for block in [context[:16], context[16:32], context[32:], (384).to_bytes(16,"big")]:
        s=gf_mul(s ^ int.from_bytes(block,"big"),h)
    return s.to_bytes(16,"big")

def make_mask(name,k):
    if name=="BLAKE3": return lambda t: blake3(t,key=k).digest(length=16)
    if name=="BLAKE2s": return lambda t: hashlib.blake2s(t,key=k,digest_size=16).digest()
    if name=="HMAC-SHA256": return lambda t: hmac.digest(k,t,"sha256")[:16]
    if name=="CMAC": return lambda t: CMAC.new(k,msg=t,ciphermod=AES).digest()
    if name=="KMAC128": return lambda t: KMAC128.new(key=k,data=t,mac_len=16,custom=b"").digest()
    if name=="GHASH": return lambda t: ghash(k[:16],t)
    raise ValueError(name)

def transform(name, payload, unit, k, *, decrypt=False, first_sector=SECTOR0):
    if name not in NAMES or unit not in (512,4096) or not payload or len(payload)%unit:
        raise ValueError("use whole 512 or 4096 byte data units and a named mode")
    if name=="ECB":
        cipher=AES.new(k["ecb"],AES.MODE_ECB)
        return cipher.decrypt(payload) if decrypt else cipher.encrypt(payload)
    out=bytearray()
    if name!="XTS":
        mask=make_mask(name,k["xex/mask"])
        aes=AES.new(k["xex/data"],AES.MODE_ECB)
        f=aes.decrypt if decrypt else aes.encrypt
    for offset in range(0,len(payload),unit):
        sector=(first_sector+offset//unit).to_bytes(16,"little")
        chunk=payload[offset:offset+unit]
        if name=="XTS":
            cipher=Cipher(algorithms.AES(k["xts/data"]+k["xts/tweak"]),modes.XTS(sector))
            ctx=cipher.decryptor() if decrypt else cipher.encryptor()
            out.extend(ctx.update(chunk)+ctx.finalize())
            continue
        prev=ZERO
        for j in range(unit//16):
            block=chunk[16*j:16*j+16]
            delta=mask(sector+j.to_bytes(16,"little")+prev)
            result=strxor(f(strxor(block,delta)),delta)
            out.extend(result)
            prev=block if decrypt else result
    return bytes(out)
