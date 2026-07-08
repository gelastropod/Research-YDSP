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