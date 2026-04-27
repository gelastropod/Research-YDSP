from ocb.aes import AES
from ocb.__init__ import OCB

KEY = bytearray.fromhex('000102030405060708090A0B0C0D0E0F')
NONCE = bytearray.fromhex('000102030405060708090A0B0C0D0E0F')
PLAINTEXT = b"This is a secret message"
HEADER = b'john.doe@example.com'

# Appendix test vectors (OCB v2, AES-128)
# H = header, M = plaintext, C = expected ciphertext, T = expected tag.

# Vector Source: https://www.cs.ucdavis.edu/~rogaway/papers/draft-krovetz-ocb-00.txt
VECTORS = [
	{"H": "", "M": "", "C": "", "T": "BF3108130773AD5EC70EC69E7875A7B0"},
	{"H": "", "M": "0001020304050607", "C": "C636B3A868F429BB", "T": "A45F5FDEA5C088D1D7C8BE37CABC8C5C"},
	{"H": "", "M": "000102030405060708090A0B0C0D0E0F", "C": "52E48F5D19FE2D9869F0C4A4B3D2BE57", "T": "F7EE49AE7AA5B5E6645DB6B3966136F9"},
	{"H": "", "M": "000102030405060708090A0B0C0D0E0F1011121314151617", "C": "F75D6BC8B4DC8D66B836A2B08B32A636CC579E145D323BEB", "T": "A1A50F822819D6E0A216784AC24AC84C"},
	{"H": "", "M": "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F", "C": "F75D6BC8B4DC8D66B836A2B08B32A636CEC3C555037571709DA25E1BB0421A27", "T": "09CA6C73F0B5C6C5FD587122D75F2AA3"},
	{"H": "", "M": "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F2021222324252627", "C": "F75D6BC8B4DC8D66B836A2B08B32A6369F1CD3C5228D79FD6C267F5F6AA7B231C7DFB9D59951AE9C", "T": "9DB0CDF880F73E3E10D4EB3217766688"},
	{"H": "0001020304050607", "M": "0001020304050607", "C": "C636B3A868F429BB", "T": "8D059589EC3B6AC00CA31624BC3AF2C6"},
	{"H": "000102030405060708090A0B0C0D0E0F", "M": "000102030405060708090A0B0C0D0E0F", "C": "52E48F5D19FE2D9869F0C4A4B3D2BE57", "T": "4DA4391BCAC39D278C7A3F1FD39041E6"},
	{"H": "000102030405060708090A0B0C0D0E0F1011121314151617", "M": "000102030405060708090A0B0C0D0E0F1011121314151617", "C": "F75D6BC8B4DC8D66B836A2B08B32A636CC579E145D323BEB", "T": "24B9AC3B9574D2202678E439D150F633"},
	{"H": "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F", "M": "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F", "C": "F75D6BC8B4DC8D66B836A2B08B32A636CEC3C555037571709DA25E1BB0421A27", "T": "41A977C91D66F62C1E1FC30BC93823CA"},
	{"H": "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F2021222324252627", "M": "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F2021222324252627", "C": "F75D6BC8B4DC8D66B836A2B08B32A6369F1CD3C5228D79FD6C267F5F6AA7B231C7DFB9D59951AE9C", "T": "65A92715A028ACD4AE6AFF4BFAA0D396"},
]


def to_bytearray(hex_text):
	return bytearray.fromhex(hex_text) if hex_text else bytearray()


def run_vector_tests():
	print('\n=== OCB2-AES Vector Checks ===')
	for i, vec in enumerate(VECTORS, start=1):
		# Convert hex strings in vectors to bytearrays
		h = to_bytearray(vec['H'])
		m = to_bytearray(vec['M'])
		c = to_bytearray(vec['C'])
		t = to_bytearray(vec['T'])

		# Initialize AES and OCB instances
		aes = AES(128)
		ocb = OCB(aes)
		ocb.setKey(KEY)
		ocb.setNonce(NONCE)

		tag, ciphertext = ocb.encrypt(m, h)

		# OCB clears nonce after encrypt, so it must be set again before decrypt
		ocb.setNonce(NONCE)
		is_authentic, plaintext = ocb.decrypt(h, ciphertext, tag)

		# Assertions to verify correctness of encryption and decryption
		assert ciphertext == c, f'{i:02d} ciphertext mismatch'
		assert tag == t, f'{i:02d} tag mismatch'
		assert is_authentic, f'{i:02d} decrypt/auth failed'
		assert plaintext == m, f'{i:02d} plaintext mismatch'

		print(f'Vector {i:02d}: PASS')

	print(f'All {len(VECTORS)} vectors passed.')


aes = AES(128)
ocb = OCB(aes)
ocb.setKey(KEY)
ocb.setNonce(NONCE)

tag, ciphertext = ocb.encrypt(PLAINTEXT, HEADER)

print('TAG:         ', tag.hex())
print('CIPHERTEXT:  ', ciphertext.hex())

ocb.setNonce(NONCE)
is_authentic, plaintext2 = ocb.decrypt(HEADER, ciphertext, tag)
print('IS AUTHENTIC:', is_authentic)
print('PLAINTEXT:   ', plaintext2.decode('utf-8'))

# Tamper with the tag
tag_ = bytearray(tag)
tag_[3] ^= 0x01  
print('IS AUTHENTIC (2): ', ocb.decrypt(HEADER, ciphertext, tag_)[0])

# Tamper with the ciphertext
cipher_ = bytearray(ciphertext)
cipher_[0] ^= 0x01
print('IS AUTHENTIC (3): ', ocb.decrypt(HEADER, cipher_, tag)[0])

run_vector_tests()