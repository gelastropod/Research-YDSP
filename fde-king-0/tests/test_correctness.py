import random,unittest
from Crypto.Cipher import AES
from fdebench.engine import Engine,ReferenceEngine,schemes,gf_xts,sector_bytes
from fdebench.masks import make_mask,xor

class Correctness(unittest.TestCase):
 def test_aes_vector(self):
  key=bytes(range(32));p=bytes.fromhex('00112233445566778899aabbccddeeff')
  self.assertEqual(AES.new(key,AES.MODE_ECB).encrypt(p).hex(),'8ea2b7ca516745bfeafc49904b496089')
 def test_lrw_document_field(self):
  rng=random.Random(18)
  for _ in range(100):
   key=rng.randbytes(32);x=rng.randbytes(48);a=int.from_bytes(key[:16],'big');y=0
   for i in (0,16,32):y=gf_xts(y^int.from_bytes(x[i:i+16],'big'),a)
   self.assertEqual(make_mask('lrw_poly',key)(x),y.to_bytes(16,'big'))
  with self.assertRaises(ValueError):make_mask('lrw_poly',bytes(32))
 def test_cbc_mac(self):
  rng=random.Random(19)
  for _ in range(50):
   k=rng.randbytes(32);x=rng.randbytes(48)
   self.assertEqual(make_mask('cbc_mac',k)(x),AES.new(k,AES.MODE_CBC,iv=bytes(16)).encrypt(x)[-16:])
 def test_all_schemes(self):
  rng=random.Random(20)
  for scheme,mask in schemes():
   for size in (16,32,512,4096):
    key=rng.randbytes(64);p=rng.randbytes(size);e=Engine(scheme,mask,key);ref=ReferenceEngine(scheme,mask,key)
    c=e.encrypt(p,37)
    self.assertEqual(c,ref.encrypt(p,37),(scheme,size))
    self.assertEqual(e.decrypt(c,37),p)
    self.assertEqual(ref.decrypt(c,37),p)
    for j in {0,size//32,size//16-1}:self.assertEqual(e.decrypt_block(c,37,j),p[16*j:16*(j+1)])
    if scheme!='xts_library':
     mid=size//32
     self.assertEqual(e.decrypt_range(c,37,0,mid)+e.decrypt_range(c,37,mid,size//16),p)
 def test_xts_library(self):
  k=bytes(range(64));p=bytes(range(256))*16
  expected=Engine('xts_library',key=k).encrypt(p,2**32+7)
  for mode in ('xts_manual_soft','xts_manual_ni'):self.assertEqual(Engine(mode,key=k).encrypt(p,2**32+7),expected)
 def test_local_recovery(self):
  for scheme,mask in schemes():
   e=Engine(scheme,mask);p=bytes(4096);c=bytearray(e.encrypt(p,3));c[16*31]^=1
   restored=e.decrypt(bytes(c),3)
   self.assertNotEqual(restored[16*31:16*32],p[16*31:16*32])
   self.assertEqual(restored[16*33:],p[16*33:])
 def test_hash_vectors(self):
  import hashlib
  from blake3 import blake3
  from nacl.bindings import crypto_shorthash_siphashx24
  self.assertEqual(crypto_shorthash_siphashx24(b'',bytes(range(16))).hex(),'a3817f04ba25a8e66df67214c7550293')
  key=bytes(range(32));x=bytes(range(48))
  for name in ('blake2s','blake2b'):
   self.assertEqual(make_mask(name,key)(x),getattr(hashlib,name)(x,key=key,digest_size=16).digest())
  self.assertEqual(make_mask('blake3',key)(x),blake3(x,key=key).digest(length=16))
 def test_validation(self):
  for bad in (b'',bytes(15),bytes(17)):
   with self.assertRaises(ValueError):Engine().encrypt(bad)
  with self.assertRaises(ValueError):Engine().encrypt(bytes(16),-1)
  with self.assertRaises(ValueError):Engine('xex','cbc_mac')
  with self.assertRaises(ValueError):Engine(key=bytes(63))
  with self.assertRaises(IndexError):Engine().decrypt_block(bytes(16),0,1)
if __name__=='__main__':unittest.main()
