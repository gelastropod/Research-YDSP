"""Optimized scheduling of the exact document formulas; no plaintext caching."""
from .reference import *
from .reference import Engine as ReferenceEngine
from Crypto.Util.strxor import strxor

DEFAULT_MASK = 'blake3'  # Change one line for the full hash-based XEX implementation.

class Engine(ReferenceEngine):
    def __init__(self,scheme='xex',mask=None,key=None):
        if scheme=='xex' and mask not in (None,'kmac128','blake3','blake2s','blake2b','siphash128'):
            raise ValueError('XEX profile must be a nominated keyed hash')
        super().__init__(scheme,mask or DEFAULT_MASK,key)

    def crypt(self,data,sector=0,decrypt=False,cost=None):
        self.validate(data)
        s=sector_bytes(sector)
        if self.scheme in ('ecb_bulk','xts_library'):
            return super().crypt(data,sector,decrypt,cost)
        start=perf_counter_ns() if cost else 0
        aes=self.aes.decrypt if decrypt else self.aes.encrypt
        seed_start=perf_counter_ns() if cost else 0
        n=len(data)//16
        seed=self.aux.encrypt(s) if self.scheme.startswith('xts') or self.scheme=='cbc_mac' else None
        if cost:cost.seed_ns+=perf_counter_ns()-seed_start
        tick=perf_counter_ns() if cost else 0
        if self.scheme.startswith('xts'):
            t=int.from_bytes(seed,'little');masks=bytearray(len(data))
            for j in range(n):
                masks[j*16:j*16+16]=t.to_bytes(16,'little');t=mul_alpha(t)
            if cost:cost.mask_ns+=perf_counter_ns()-tick;tick=perf_counter_ns()
            out=strxor(aes(strxor(data,masks)),masks)
            if cost:cost.data_ns+=perf_counter_ns()-tick;cost.wall_ns+=perf_counter_ns()-start
            return out
        # CBC-MAC's first two stages are independent of ciphertext feedback.
        # Compute E(I_j xor E(S)) in one native batch, without retaining sectors.
        mids=None
        if self.scheme=='cbc_mac':
            mids=self.aux.encrypt(b''.join(xor(seed,self.indices[j]) for j in range(n)))
            if cost:cost.mask_ns+=perf_counter_ns()-tick
        prefix=s
        h=self.mask
        encmask=self.aux.encrypt
        if decrypt:
            tick=perf_counter_ns() if cost else 0
            prev=bytes(16)+data[:-16]
            if mids is not None:
                masks=encmask(strxor(prev,mids))
            else:
                masks=b''.join(h(prefix+self.indices[j]+prev[j*16:j*16+16]) for j in range(n))
            if cost:cost.mask_ns+=perf_counter_ns()-tick;tick=perf_counter_ns()
            out=strxor(aes(strxor(data,masks)),masks)
            if cost:cost.data_ns+=perf_counter_ns()-tick;cost.wall_ns+=perf_counter_ns()-start
            return out
        previous=bytes(16);result=bytearray(len(data))
        for j in range(n):
            offset=j*16
            tick=perf_counter_ns() if cost else 0
            delta=encmask(xor(previous,mids[offset:offset+16])) if mids is not None else h(prefix+self.indices[j]+previous)
            if cost:cost.mask_ns+=perf_counter_ns()-tick;tick=perf_counter_ns()
            previous=xor(aes(xor(data[offset:offset+16],delta)),delta)
            result[offset:offset+16]=previous
            if cost:cost.data_ns+=perf_counter_ns()-tick
        if cost:cost.wall_ns+=perf_counter_ns()-start
        return bytes(result)

    def decrypt_range(self,ciphertext,sector,lo,hi):
        self.validate(ciphertext)
        if not 0<=lo<=hi<=len(ciphertext)//16:raise IndexError('Invalid range')
        if lo==hi:return b''
        if self.scheme in ('xts_library','ecb_bulk'):
            return super().decrypt_range(ciphertext,sector,lo,hi)
        s=sector_bytes(sector)
        if self.scheme.startswith('xts'):
            t=gf_xts(int.from_bytes(self.aux.encrypt(s),'little'),ALPHAS[lo]);parts=[]
            for j in range(lo,hi):parts.append(t.to_bytes(16,'little'));t=mul_alpha(t)
            masks=b''.join(parts)
        else:
            prev=(bytes(16)+ciphertext[:16*(hi-1)]) if lo==0 else ciphertext[16*(lo-1):16*(hi-1)]
            if self.scheme=='cbc_mac':
                seed=self.aux.encrypt(s)
                mids=self.aux.encrypt(b''.join(xor(seed,self.indices[j]) for j in range(lo,hi)))
                masks=self.aux.encrypt(strxor(prev,mids))
            else:
                masks=b''.join(self.mask(s+self.indices[j]+prev[16*(j-lo):16*(j-lo+1)]) for j in range(lo,hi))
        return strxor(self.aes.decrypt(strxor(ciphertext[lo*16:hi*16],masks)),masks)

def build(label):return Engine('xex',label[4:]) if label.startswith('xex_') else Engine(label)

def encrypt_sector(plaintext,sector,*,mask=None,key=None):return Engine('xex',mask,key).encrypt(plaintext,sector)
