#include <stdio.h>

#include "test_utils.h"
#include "primitives.h"

int main() {
	byte key[16];
	byte in[16];
	byte out[16];
	byte re_in[16];

	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char in_string[33] = "746772676f6f6e747265617061626364";
	char out_string[33];
	char re_in_string[33];

	printf("Key used: %s\n", key_string);
	printf("Plaintext used: %s\n", in_string);

	hex_to_bytes(key_string, key, 16);
	hex_to_bytes(in_string, in, 16);

	aes_block_encrypt(key, in, out, 16);
	bytes_to_hex(out, out_string, 16);
	
	printf("Ciphertext: %s\n", out_string);

	aes_block_decrypt(key, out, re_in, 16);
	bytes_to_hex(re_in, re_in_string, 16);

	printf("Decoded plaintext: %s\n", re_in_string);

	return 0;
}
