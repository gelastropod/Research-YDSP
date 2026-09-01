#include <stdio.h>
#include <string.h>

#include "primitives.h"
#include "test_utils.h"

int main() {
	byte key[32];
	byte plaintext[59];
	byte ciphertext[59];
	byte re_plaintext[59];

	char key_string[65] = "e952be5248628ff1b75ddeb7a56b17edc20d645402106651d86b58391b1f4719";
	char plaintext_string[119] = "7cda46586f7b1393c0ad428ca36712f1bfdb2100bbde1725423e1b6b16a672f18e3e72fab444339b58413b5be37d0a87a73af1946e646fdfa071b7";
	char ciphertext_string[119];
	char re_plaintext_string[119];

	int result;
	uint32_t sector_size = 32;

	printf("Key used: %s\n", key_string);
	printf("Plaintext used: %s\n", plaintext_string);

	hex_to_bytes(key_string, key, 32);
	hex_to_bytes(plaintext_string, plaintext, 59);

	printf("Sector size: %d\n", sector_size);

	result = xts_encrypt_volume(key, plaintext, ciphertext, 32, sector_size, 59);
	if (result != 0) {
		printf("Error in xts_encrypt_volume: %d\n", result);
		return -1;
	}
	bytes_to_hex(ciphertext, ciphertext_string, 59);

	printf("Ciphertext: %s\n", ciphertext_string);

	result = xts_decrypt_volume(key, ciphertext, re_plaintext, 32, sector_size, 59);;
	if (result != 0) {
		printf("Error in xts_decrypt_volume: %d\n", result);
		return -1;
	}
	bytes_to_hex(re_plaintext, re_plaintext_string, 59);

	printf("Decrypted plaintext: %s\n", re_plaintext_string);
	printf("\n");

	if (memcmp(plaintext, re_plaintext, 59) == 0) {
		printf("Roundtrip matches original plaintext\n");
	}
	else {
		printf("Roundtrip does NOT match original plaintext\n");
		return -1;
	}

	return 0;
}
