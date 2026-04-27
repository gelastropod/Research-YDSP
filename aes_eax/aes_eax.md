# AES-EAX
Please note that the following dependencies are needed:
- `pycryptodome`

To install these dependencies, use:

```pip install pycryptodome```

To import the library, use:

```python
from Crypto.Cipher import AES
```

Create a cipher object using a random key (16 bytes), and get its nonce:

```python
cipher = AES.new(key, AES.MODE_EAX)
nonce = cipher.nonce
```

Encrypt a plaintext using the cipher, and obtain the associated authentication tag:

```python
ciphertext, tag = cipher.encrypt_and_digest(plaintext)
```

Create a cipher object with the same nonce, for decryption purposes:

```python
cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
plaintext_decrypted = cipher.decrypt_and_verify(ciphertext, tag)
```

If the authentication tag is wrong, a `ValueError` will be raised.

Note: all plaintexts, ciphertexts, keys and nonces are python byte strings.

Sample usage code, also present in `test_aes_eax.py`:

```python
import os
from Crypto.Cipher import AES

key = os.urandom(16)
plaintext = b"test message"

cipher = AES.new(key, AES.MODE_EAX)
nonce = cipher.nonce
ciphertext, tag = cipher.encrypt_and_digest(plaintext)

cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
plaintext_decrypted = cipher.decrypt_and_verify(ciphertext, tag)

print("Plaintext: ", plaintext)
print("Ciphertext: ", ciphertext)
print("Authentication tag: ", tag)
print("Decrypted plaintext: ", plaintext_decrypted)
```

Output:

```
Plaintext:  b'test message'
Ciphertext:  b'\x07\xde;]\xac\xd1\xef\xd7\x8f\x95[\xec'
Authentication tag:  b'\xc9\xd9*\xfd\xe6\xcf\x1f\xeb|?\xe5\x86\r\xedm\x1e'
Decrypted plaintext:  b'test message'
```