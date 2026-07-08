import os
import adiantum

#get first available variant
cipher = adiantum.Adiantum()
variant = list(cipher.variants())[0]
cipher.variant = variant

#32-byte key
key = os.urandom(32)

#tweak (like a nonce, can be any size)
tweak = os.urandom(12)

#plaintext (must be at least 16 bytes!)
plaintext = b'something maybe 16 bytes'

ciphertext = cipher.encrypt(plaintext, key=key, tweak=tweak)
print("Plaintext: ", plaintext)
print("Ciphertext:", bytes(ciphertext).hex())

decrypted = cipher.decrypt(bytes(ciphertext), key=key, tweak=tweak)
print("Decrypted: ", bytes(decrypted))

#verificaiton test
assert bytes(decrypted) == plaintext
print("Verification passed!")

#tamper test
print("\nTamper Test!!")
tampered = bytearray(ciphertext)
tampered[0] ^= 0xFF  #flip bits (tampering)
decrypted_tampered = cipher.decrypt(bytes(tampered), key=key, tweak=tweak)
print("Tampered decryption (should be garbage):", bytes(decrypted_tampered))
print("Tamper detected!" if bytes(decrypted_tampered) != plaintext else "No change detected")

# actually needed/useful files:
#     adiantum.py
#     hbsh.py
#     nh.py
#     nhpoly1305.py
#     poly1305.py
#     aes.py
#     cipher.py
#     xconstruct.py
#     latindance.py
#     bachata.py
