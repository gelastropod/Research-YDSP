"""Change DEFAULT_MASK in engine.py, or change the mask name below."""
from fdebench.engine import Engine
from secrets import token_bytes

engine = Engine('xex', key=token_bytes(64))  # Uses DEFAULT_MASK in engine.py
# Alternatives: Engine('cbc_mac', key=token_bytes(64)) or Engine('lrw_poly', key=token_bytes(64))
plaintext = bytes(4096)
ciphertext = engine.encrypt(plaintext, sector=12)
assert engine.decrypt(ciphertext, sector=12) == plaintext
assert engine.decrypt_block(ciphertext, sector=12, j=200) == plaintext[3200:3216]
print('4096-byte sector and direct block read verified')
