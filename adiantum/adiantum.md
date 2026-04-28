# Adiantum
Adiantum is a length-preserving cipher developed by Google, designed for **low-end devices without hardware AES acceleration** (e.g. cheap Android phones). It is an instance of HBSH (Hash, Block cipher, Stream cipher, Hash) and is used primarily for **disk/storage encryption**.

Note: Adiantum is **not a traditional AEAD**, it does not have authentication tag nor associated data. It is a Super Pseudorandom Permutation (SPRP), where any change to the ciphertext results in completely garbled plaintext on decryption, which provides the integrity.

## How It Works
1. A 32-byte key is used to derive subkeys via XChaCha12, one for stream cipher, one for AES, and one for NH hashing.
2. The plaintext is split into a bulk portion and a final 16-byte block.
3. The bulk portion is hashed using **NH + Poly1305** in GF(2¹²⁸), producing a hash value.
4. The final 16-byte block is XORed with the hash, then encrypted with **AES-256** once.
5. The AES output is used as a nonce to encrypt the bulk portion with **XChaCha12**.
6. The bulk portion is hashed again and XORed back into the final block, producing the ciphertext.
7. During decryption, the process is reversed. Since there is no auth tag, if the ciphertext is tampered with, it decrypts to garbage.

## Setup
**Dependencies**
```bash
pip3 install pycryptodome
```
All other dependencies (`hbsh.py`, `nh.py`, `poly1305.py`, etc.) are included in the forked repo. Run from inside the `python/` folder.

Import and set key and tweak:
```python
import adiantum
import os

# get first available variant
cipher = adiantum.Adiantum()
variant = list(cipher.variants())[0]
cipher.variant = variant

# 32-byte key
key = os.urandom(32)
# tweak (like a nonce, can be any length)
tweak = os.urandom(12)
```

Encrypt a plaintext (must be at least 16 bytes):
```python
ciphertext = cipher.encrypt(plaintext, key=key, tweak=tweak)
```

Decrypt a ciphertext using the same key and tweak:
```python
decrypted = cipher.decrypt(ciphertext, key=key, tweak=tweak)
```

## Full Sample Code, in `sample_adiantum.py` too:
```python
import adiantum
import os

cipher = adiantum.Adiantum()
cipher.variant = list(cipher.variants())[0]

key      = os.urandom(32)
tweak    = os.urandom(12)
plaintext = b'Hello Adiantum!!'  # must be at least 16 bytes

ciphertext = cipher.encrypt(plaintext, key=key, tweak=tweak)
decrypted  = cipher.decrypt(bytes(ciphertext), key=key, tweak=tweak)

print("Plaintext: ", plaintext)
print("Ciphertext:", bytes(ciphertext).hex())
print("Decrypted: ", bytes(decrypted))

# tamper test: shows garbled output instead of exception
print("\nTamper Test!!")
tampered = bytearray(ciphertext)
tampered[0] ^= 0xFF  # flip bits in first byte
garbled = cipher.decrypt(bytes(tampered), key=key, tweak=tweak)
print("Tampered decryption (garbage):", bytes(garbled))
print("Tamper detected!" if bytes(garbled) != plaintext else "No change detected")
```

Output:
```
Plaintext:  b'adiantum adiantum adiantum'
Ciphertext: <varies with random key and tweak>
Decrypted:  b'adiantum adiantum adiantum'

Tamper Test!!
Tampered decryption (garbage): <garbled bytes>
Tamper detected!
```

Note: unlike AES-GCM, Adiantum has no authentication tag, hence tampering does not raise an exception, it produces garbage output. The tweak is equivalent to a nonce and should be unique (eg: disk sector index).