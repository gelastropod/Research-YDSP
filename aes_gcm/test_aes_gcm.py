from aes_gcm import AES_GCM
from Crypto.Random.random import getrandbits

#128-bit key
master_key = 0x00000000000000000000000000000000
#96-bit random generated nonce
init_value = getrandbits(96)
auth_data  = b'hiya123c'
plaintext  = b'ello cookie time!'

my_gcm = AES_GCM(master_key)
ciphertext, auth_tag = my_gcm.encrypt(init_value, plaintext, auth_data)
decrypted = my_gcm.decrypt(init_value, ciphertext, auth_tag, auth_data)

print("Plaintext: ", plaintext)
print("Ciphertext: ", ciphertext.hex())
print("Auth Tag: ", hex(auth_tag))
print("Decrypted: ", decrypted)

#tag tampering test
print("\nTamper Test!!")
try:
    my_gcm2 = AES_GCM(master_key)
    init_value2 = getrandbits(96)
    ct, tag = my_gcm2.encrypt(init_value2, plaintext, auth_data)
    my_gcm2.decrypt(init_value2, ct, tag + 1, auth_data)  #tampered tag, tag + 1
except Exception as e:
    print("Tamper detected:", e)

#Note: changing key/nonce changes both ciphertext and auth tag, changing only auth_data changes only the auth tag