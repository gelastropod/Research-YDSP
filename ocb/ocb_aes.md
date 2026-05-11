# AES-OCB Quick Guide (PyCryptodome)

```bash
pip install pycryptodome
```

This document shows usage of AES in OCB mode via PyCryptodome (`Crypto.Cipher.AES`).

## Import and Setup

```python
from Crypto.Cipher import AES

# 128-bit AES key (example)
key = bytes.fromhex('000102030405060708090A0B0C0D0E0F')

# 12- or 15-byte nonces are commonly used; follow your protocol's requirements
nonce = bytes.fromhex('000102030405060708090A0B0C0D0E0F')
cipher = AES.new(key, AES.MODE_OCB, nonce=nonce)
```

## Encrypt and Decrypt

```python
header = b"Recipient: john.doe@example.com"
plaintext = b"The Magic Words are Squeamish Ossifrage"

cipher.update(header)                      # set associated data (AAD)
ciphertext, tag = cipher.encrypt_and_digest(plaintext)

# To decrypt, create a fresh cipher with same key and nonce and call:
dec = AES.new(key, AES.MODE_OCB, nonce=nonce)
dec.update(header)
try:
	recovered = dec.decrypt_and_verify(ciphertext, tag)
	print(recovered.decode())
except ValueError:
	print("Decryption failed or authentication failed")
```

## Notes

- OCB provides authenticity and confidentiality in one pass.
- Always use a unique nonce per key in real systems.
- PyCryptodome's `encrypt_and_digest` returns `(ciphertext, tag)` and `decrypt_and_verify` raises ``ValueError`` on failure.



