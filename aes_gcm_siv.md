# AES-GCM-SIV Quick Guide

```bash
pip install cryptography
```

**AES-GCM-SIV** is an AEAD combining Galois/Counter Mode (GCM) and Synthetic Initialization Vector (SIV), and is designed to be safer than standard GCM when nonces are accidentally reused.

## Import and Setup

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV

# Generate a secure 128-bit or 256-bit key
key = AESGCMSIV.generate_key(bit_length=256)
aesgcmsiv = AESGCMSIV(key)

# Generate a 12-byte (96-bit) nonce
nonce = os.urandom(12)
```

## Encrypt and Decrypt

```python
data = b"CRITICALLY IMPORTANT!"
associated = b"joe@mama.com"

ciphertext = aesgcmsiv.encrypt(nonce, data, associated)
print(f"Ciphertext: {ciphertext.hex()}")

try:
    recovered = aesgcmsiv.decrypt(nonce, ciphertext, associated)
    print(f"Decrypted: {recovered.decode()}")
except Exception:
    print("Decryption failed or data was tampered with.")
```

## Nonce Rule

While AES-GCM-SIV is nonce-misuse resistant compared to AES-GCM, best practice is to use a nonce "only once".

## Lifting up the Hood :)

Let $K$ be the master key, $N$ the nonce, $A$ the associated data (AAD), and $M$ the plaintext.

![Figure 1: AES-GCM-SIV engineering](https://vos.line-scdn.net/landpress-content-v2_1761/1668501715059.png)

Figure 1 credit: https://engineering.linecorp.com/en/blog/AES-GCM-SIV-optimization

1. AES-GCM-SIV derives internal subkeys from $K$ and $N$: $(K_{hash}, K_{enc}) = \mathrm{KDF}(K, N)$

    - This way, cross-leaking between hashing and encryption is limited.

2. POLYVAL hashes associated data and plaintext via polynomial $x^{128} + x^{127} + x^{126} + x^{121} + 1$ in finite field $GF(2^{128})$ such that $S = \mathrm{POLYVAL}(K_{hash}, A, M) \oplus N$

3. SIV encrypts that fingerprint with AES under $K_{enc}$ to create tag $T = E_{K_{enc}}(S)$

4. Ciphertext blocks are produced with CTR mode using $T$ as the counter base, such that for every $i$, $C_i = M_i \oplus E_{K_{enc}}(T + i)$.
