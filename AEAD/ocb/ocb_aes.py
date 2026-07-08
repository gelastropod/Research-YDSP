from Crypto.Cipher import AES
from binascii import unhexlify


KEY = unhexlify('000102030405060708090A0B0C0D0E0F')
# Use a 12-byte nonce (PyCryptodome OCB requires nonce length <= 15)
NONCE = unhexlify('000102030405060708090A0B0C')
PLAINTEXT = b"This is a secret message"
HEADER = b'john.doe@example.com'

# Appendix test vectors
# H = header, M = plaintext, C = expected ciphertext, T = expected tag.
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


def to_bytes(hex_text):
    return unhexlify(hex_text) if hex_text else b""


def run_vector_tests():
    print('\n=== AES-OCB Vector Checks (via PyCryptodome) ===')
    for i, vec in enumerate(VECTORS, start=1):
        h = to_bytes(vec['H'])
        m = to_bytes(vec['M'])
        # Initialize cipher for encrypt; encrypt and then decrypt to verify
        cipher = AES.new(KEY, AES.MODE_OCB, nonce=NONCE)
        if h:
            cipher.update(h)
        c, t = cipher.encrypt_and_digest(m)

        # decrypt and verify using same nonce and header
        cipher2 = AES.new(KEY, AES.MODE_OCB, nonce=NONCE)
        if h:
            cipher2.update(h)
        try:
            m2 = cipher2.decrypt_and_verify(c, t)
        except ValueError:
            assert False, f'{i:02d} decryption/auth failed'
        assert m2 == m, f'{i:02d} plaintext mismatch'

        print(f'Vector {i:02d}: PASS')

    print(f'All {len(VECTORS)} vectors passed.')


def smoke_test():
    cipher = AES.new(KEY, AES.MODE_OCB, nonce=NONCE)
    cipher.update(HEADER)
    c, t = cipher.encrypt_and_digest(PLAINTEXT)
    print('TAG:        ', t.hex())
    print('CIPHERTEXT: ', c.hex())

    # verify
    cipher2 = AES.new(KEY, AES.MODE_OCB, nonce=NONCE)
    cipher2.update(HEADER)
    try:
        pt = cipher2.decrypt_and_verify(c, t)
        print('IS AUTHENTIC:', True)
        print('PLAINTEXT:  ', pt.decode())
    except ValueError:
        print('IS AUTHENTIC:', False)


if __name__ == '__main__':
    smoke_test()
    run_vector_tests()
