# OCB-AES Quick Guide

**OCB mode with AES-128**, which is an authenticated encryption with a tag $T$ to provide integrity and authenticity.

As the original repo is Python 2 and has outdated syntax, this Python 3-safe fork accepts **bytes-like inputs** and normalises internally. Common safe inputs:
- `bytes`
- `bytearray`
- hex converted with `bytearray.fromhex(...)`

## Import and Setup

```python
from ocb.aes import AES
from ocb.__init__ import OCB

key = bytearray.fromhex("000102030405060708090A0B0C0D0E0F")
nonce = bytearray.fromhex("000102030405060708090A0B0C0D0E0F")

aes = AES(128)
ocb = OCB(aes)
ocb.setKey(key)
ocb.setNonce(nonce)
```

## Encrypt and Decrypt

```python
plaintext = b"This is a secret message"
header = b"john.doe@example.com"

tag, ciphertext = ocb.encrypt(plaintext, header)
ocb.setNonce(nonce)
is_authentic, recovered = ocb.decrypt(header, ciphertext, tag)

print(is_authentic)
# True when tag matches
print(recovered)
# bytearray(b"This is a secret message")
```

## Nonce Rule

Never reuse the same key + nonce pair for different messages in real systems

The class intentionally sets `self.nonce = None` after `encrypt()`. So if you encrypt then decrypt with the same object, you must call `setNonce()` again.

## Lift up the Hood :)

1. OCB treats each 16-byte block in the message as a value in $GF(2^n)$, which is often combined with XOR `^` (bitwise addition)
2. An offset is derived from nonce $N$, which is used in tandem to multiply each block by 2 via `times2()`. To prevent the field from overflowing, we conduct a XOR.
- Afterwards, for each message block we offset it before AES encryption.
- As part of the authentication tag, OCB maintains a running Checksum over the plaintext blocks. Final tag is computed from Checksum + Final Offset via AES (and XOR-ed with PMAC of header, if a header exists).

