#include <stdio.h>
#include <string.h>

#include "test_utils.h"
#include "primitives.h"

int main() {
	byte key[16];
	byte plaintext[16];
	byte ciphertext[16];
	byte re_plaintext[16];

	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char plaintext_string[33] = "7cda46586f7b1393c0ad428ca36712f1";
	char ciphertext_string[33];
	char re_plaintext_string[33];

	int result;

	printf("Key used: %s\n", key_string);
	printf("Plaintext used: %s\n", plaintext_string);

	hex_to_bytes(key_string, key, 16);
	hex_to_bytes(plaintext_string, plaintext, 16);

	result = aes_block_encrypt(key, plaintext, ciphertext, 16);
	if (result != 0) {
		printf("Error in aes_block_encrypt: %d\n", result);
		return -1;
	}
	bytes_to_hex(ciphertext, ciphertext_string, 16);
	
	printf("Ciphertext: %s\n", ciphertext_string);

	result = aes_block_decrypt(key, ciphertext, re_plaintext, 16);
	if (result != 0) {
		printf("Error in aes_block_decrypt: %d\n", result);
		return -1;
	}
	bytes_to_hex(re_plaintext, re_plaintext_string, 16);

	printf("Decrypted plaintext: %s\n", re_plaintext_string);
	printf("\n");

	if (memcmp(plaintext, re_plaintext, 16) == 0) {
		printf("Roundtrip matches original plaintext\n");
	}
	else {
		printf("Roundtrip does NOT match original plaintext\n");
		return -1;
	}

	return 0;
}
