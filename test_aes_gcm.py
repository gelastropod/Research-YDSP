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

#changing key/nonce changes ciphertext and authentication tag, changing associated data only changes authentication tag