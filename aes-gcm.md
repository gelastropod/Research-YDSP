# AES-GCM
Note: aes_gcm used init_value (IV) instead of nonce within code implementation


To import the library, use:
```python
from aes_gcm import AES_GCM
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
plaintext = my_gcm.decrypt(init_value, ciphertext, auth_tag, auth_data)
```

Note: plaintext and auth_data are Python byte strings. The master key, nonce, and auth tag are large integers. If the auth tag is invalid, an `InvalidTagException` will be raised. The nonce must not be reused with the same key (nonce reuse).

Sample usage code (`test_aes_gcm.py`):
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