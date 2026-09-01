#include <stdio.h>
#include <string.h>

#include "test_utils.h"
#include "xex.h"
#include "kdf.h"

int main() {
	byte key[16], next_key[16];
	byte plaintext[16], ciphertext[16], re_plaintext[16];
	byte tweak[16], next_tweak[16];
	byte key_0[16], key_F[16], key_G[16];

	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char plaintext_string[33] = "7cda46586f7b1393c0ad428ca36712f1";
	char tweak_string[33] = "bfdb2100bbde1725423e1b6b16a672f1";
	char ciphertext_string[33];
	char re_plaintext_string[33];
	char next_key_string[33];
	char next_tweak_string[33];

	int result;

	printf("Key used: %s\n", key_string);
	printf("Plaintext used: %s\n", plaintext_string);
	printf("Tweak used: %s\n", tweak_string);

	hex_to_bytes(key_string, key, 16);
	hex_to_bytes(plaintext_string, plaintext, 16);
	hex_to_bytes(tweak_string, tweak, 16);

	result = expand_master_key(key, key_0, key_F, key_G, 16);
	if (result != 0) {
		printf("Error in expand_master_key: %d\n", result);
		return -1;
	}

	result = xex_encrypt_block(key_0, tweak, plaintext, ciphertext, 16);
	if (result != 0) {
		printf("Error in xex_encrypt_block: %d\n", result);
		return -1;
	}
	bytes_to_hex(ciphertext, ciphertext_string, 16);

	printf("Ciphertext: %s\n", ciphertext_string);

	result = xex_decrypt_block(key_0, tweak, ciphertext, re_plaintext, 16);
	if (result != 0) {
		printf("Error in xex_decrypt_block: %d\n", result);
		return -1;
	}
	bytes_to_hex(re_plaintext, re_plaintext_string, 16);

	printf("Decrypted plaintext: %s\n", re_plaintext_string);

	result = update_state(key, tweak, ciphertext, key_F, key_G, next_key, next_tweak, 16);
	if (result != 0) {
		printf("Error in update_state: %d\n", result);
		return -1;
	}
	bytes_to_hex(next_key, next_key_string, 16);
	bytes_to_hex(next_tweak, next_tweak_string, 16);

	printf("Next key: %s\n", next_key_string);
	printf("Next tweak: %s\n", next_tweak_string);
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