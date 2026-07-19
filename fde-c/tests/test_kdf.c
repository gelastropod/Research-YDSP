#include <stdio.h>

#include "test_utils.h"
#include "kdf.h"

int main() {
	byte key[16];
	byte key_0[16];
	byte key_F[16];
	byte key_G[16];

	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char key_0_string[33];
	char key_F_string[33];
	char key_G_string[33];

	printf("Key used: %s\n", key_string);

	hex_to_bytes(key_string, key, 16);

	int result = expand_master_key(key, key_0, key_F, key_G, 16);
	if (result != 0) {
		printf("Error in expand_master_key: %d\n", result);
		return -1;
	}

	bytes_to_hex(key_0, key_0_string, 16);
	bytes_to_hex(key_F, key_F_string, 16);
	bytes_to_hex(key_G, key_G_string, 16);

	printf("K0: %s\n", key_0_string);
	printf("KF: %s\n", key_F_string);
	printf("KG: %s\n", key_G_string);

	return 0;
}