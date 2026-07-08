import os
from chacha20poly1305 import ChaCha20Poly1305

key = os.urandom(32)
cipher = ChaCha20Poly1305(key)

plaintext = b"test message"
nonce = os.urandom(12)

ciphertext = cipher.encrypt(nonce, plaintext)
plaintext_decrypted = cipher.decrypt(nonce, ciphertext)

print("Plaintext: ", plaintext)
print("Ciphertext: ", ciphertext)
print("Decrypted plaintext: ", plaintext_decrypted)