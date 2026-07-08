import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV 

# Generate a secure 128 or 256-bit key
key = AESGCMSIV.generate_key(bit_length=256)
aesgcmsiv = AESGCMSIV(key)

# Generate a 12-byte (96-bit) nonce
NONCE = os.urandom(12)

# Encrypt data
DATA = b"CRITICALLY IMPORTANT!"
ASSOCIATED = b"joe@mama.com"
ciphertext = aesgcmsiv.encrypt(NONCE, DATA, ASSOCIATED)
print(f"Ciphertext: {ciphertext.hex()}")

# Decrypt data
try:
    recovered = aesgcmsiv.decrypt(NONCE, ciphertext, ASSOCIATED)
    print(f"Decrypted: {recovered.decode()}")
except Exception as e:
    print("Decryption failed or data was tampered with.")