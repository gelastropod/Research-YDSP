# AES-GCM
AES-GCM (Galois/Counter Mode) is an AEAD algorithm. It combines AES-CTR for encryption and GHASH for authentication, producing both a ciphertext and an authentication tag T to provide integrity and authenticity.

Note: this forked-repo implementation uses init_value (IV) instead of nonce in the code.

# How It Works

1. A subkey H is derived by encrypting a block of zeros with AES using your master key
2. The plaintext is encrypted block by block using AES-CTR, starting at Counter value 2. (counter is 32 bit) Each block gets XORed with an AES-encrypted counter.
3. A GHASH function runs over the ciphertext (and optional associated data) in GF(2¹²⁸), producing an authentication tag.
4. The tag is finalised by XORing with AES(nonce || counter=1). Counter 1 was deliberately skipped during encryption and reserved for the tag.
5. Durign decryption, the tag is authenticated and verified first before anything is decrypted. If the tag doesn't match, an `InvalidTagException` is raised.

# Setup

Import and set key and nonce
```python
from aes_gcm import AES_GCM
#any 128-bit key
master_key  = 0x00000000000000000000000000000000
#any 96-bit nonce
init_value  = 0x000000000000000000000000
```

Create a cipher object using a 128-bit integer key:
```python
my_gcm = AES_GCM(master_key)
```

Encrypt a plaintext using the cipher, as well as a provided 96-bit integer nonce and optional associated data:
```python
ciphertext, auth_tag = my_gcm.encrypt(init_value, plaintext, auth_data)
```

Decrypt a ciphertext using the cipher, along with the nonce, auth tag, and associated data:
```python
#any size plaintext
plaintext = my_gcm.decrypt(init_value, ciphertext, auth_tag, auth_data)
```

Full Sample code, in `test_aes_gcm.py` too:
```python
from aes_gcm import AES_GCM

#128-bit key
master_key  = 0x00000000000000000000000000000000
#96-bit nonce
init_value  = 0x000000000000000000000000
auth_data   = b'hiya123c'
plaintext   = b'ello cookie time!'

my_gcm = AES_GCM(master_key)
ciphertext, auth_tag = my_gcm.encrypt(init_value, plaintext, auth_data)
decrypted = my_gcm.decrypt(init_value, ciphertext, auth_tag, auth_data)

print("Plaintext: ", plaintext)
print("Ciphertext:", ciphertext.hex())
print("Auth Tag:  ", hex(auth_tag))
print("Decrypted: ", decrypted)
```

Output:
```
Plaintext:  b'ello cookie time!'
Ciphertext: 66e4b6a140d5ccfd9841a79905db931dd6
Auth Tag:   0xe96f36717fe5e8e66992d9adfa1be974
Decrypted:  b'ello cookie time!'
```

Note: changing key/nonce changes ciphertext and authentication tag, changing associated data only changes authentication tag