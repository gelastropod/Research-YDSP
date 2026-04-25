# ChaCha20-Poly1305
To import the library, use:

```python
from chacha20poly1305.chacha20poly1305 import ChaCha20Poly1305
```

Create a cipher object using a random key (32 bytes):

```python
cipher = ChaCha20Poly1305(key)
```

Encrypt a plaintext using the cipher, as well as a provided nonce (12 bytes):

```python
ciphertext = cipher.encrypt(nonce, plaintext)
```

Decrypt a ciphertext using the cipher, as well as a provided nonce:

```python
plaintext = cipher.decrypt(nonce, ciphertext)
```

Note: all plaintexts, ciphertexts, keys and nonces are python byte strings.

Sample usage code, also present in `test_chacha20poly1305.py`:

```python
import os
from chacha20poly1305.chacha20poly1305 import ChaCha20Poly1305

key = os.urandom(32)
cipher = ChaCha20Poly1305(key)

plaintext = b"test message"
nonce = os.urandom(12)

ciphertext = cipher.encrypt(nonce, plaintext)
plaintext_decrypted = cipher.decrypt(nonce, ciphertext)

print("Plaintext: ", plaintext)
print("Ciphertext: ", ciphertext)
print("Decrypted plaintext: ", plaintext_decrypted)
```

Output:

```
Plaintext:  b'test message'
Ciphertext:  bytearray(b'w&\x1c>\x96\x12\xe0\x89\xd2\x04\xe6\xb3$+Q\x8b\xa2|\xf3\x1a\x1fx\xa7/\x00\x05s\xe1')
Decrypted plaintext:  bytearray(b'test message')
```