# ChaCha20-Poly1305

## Usage Explanation

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

If the authentication tag is wrong, a `TagInvalidException` is raised.

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

## Details of Algorithm

ChaCha20-Poly1305 is a combination of the ChaCha20 encryption algorithm, as well as the Poly1305 authentication algorithm.

### ChaCha20:

![Figure 1](https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/ChaCha_Cipher_Quarter_Round_Function.svg/500px-ChaCha_Cipher_Quarter_Round_Function.svg.png)

Figure 1: Diagram of ChaCha20 quarter round function

- First takes the key and nonce, to generate a keystream using a pseudorandom function based on add-rotate-XOR (ARX) operations
  - ARX operations are functions which only involve the use of addition (modulo $2^{32}$ in the case of ChaCha20), rotation with constant offset, and XOR operations.
- A 128-bit constant, 256-bit key, 64-bit counter and 64-bit nonce are arranged in a 4x4 matrix of 32-bit words to serve as the initial state of the algorithm.
- The quarter round function (denoted QR) takes in the indices of the matrix corresponding to 4 32-bit words, and does the following operations on them:
```
a += b; d ^= a; d <<<= 16;
c += d; b ^= c; b <<<= 12;
a += b; d ^= a; d <<<=  8;
c += d; b ^= c; b <<<=  7;
```
Here, `+=` denotes addition, `^=` denotes XOR and `<<<=` denotes rotation.

- Next, the algorithm repeatedly applies the quarter round function. On odd rounds it applies QR on the columns, on even rounds it applies QR on the diagonals.
- 20 rounds are then performed, and the result is XORed with the plaintext to obtain the ciphertext.

### Poly1305:

- Poly1305 takes in a 16-byte secret key $r$ and $L$-byte message $m$ to return a 16-byte hash $Poly1305_r(m)$.
- Poly1305 splits $m$ up into consecutive 16-byte chunk, and appends one byte to the end of every chunk.
- It then interprets these chunks as coefficients of a polynomial, and evaluates it at $r$ modulo $2^{130}-5$.
- Returns the result modulo $2^{128}$ as a 16-byte hash.

The authentication tag produced is therefore the result of the Poly1305 hash of the ciphertext.

Sources:
- https://en.wikipedia.org/wiki/Salsa20#ChaCha_variant
- https://en.wikipedia.org/wiki/Poly1305#Definition_of_Poly1305