# AES-EAX\

## Usage Explanation

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

## Details of Algorithm

AES-EAX is a mode of operation of the AES block cipher.

AES-EAX uses the CTR (counter) mode of operation of AES for encryption, as well as OMAC for authentication.

### OMAC

![Figure 1](https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/CMAC_-_Cipher-based_Message_Authentication_Code.pdf/page1-1920px-CMAC_-_Cipher-based_Message_Authentication_Code.pdf.jpg)

Figure 1: Diagram of OMAC

- First, derive subkeys from $AES(k, 0)$ for a secret key $k$.
- Then, define an initial state starting with $k$.
- Repeatedly apply $state:=AES(k,state\ \oplus\ m_i$ for the different blocks $i$ of the message $m$.
- Lastly, return $AES(k, state\ \oplus\ m_n\ \oplus\ subkeys)$.

### AES-EAX

![Figure 2](https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/EAX_block_cipher_mode_of_operation.svg/960px-EAX_block_cipher_mode_of_operation.svg.png)

Figure 2: Diagram of EAX mode.

- AES-EAX runs OMAC with a tweak $t$. $OMAC^t_K(m)=OMAC_K(t\ ||\ m)$.
- The following are performed on the input:
```
N = OMAC_0(key, nonce)
C = AES-CTR(key, N, plaintext)
H = OMAC_2(key, AAD)
T = OMAC_1(key, C) XOR N XOR H
```

- Finally $(C,T)$ is returned, the ciphertext and authentication tag.