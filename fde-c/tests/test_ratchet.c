#include <stdio.h>
#include <string.h>

#include "ratchet.h"
#include "test_utils.h"

int main() {
	byte key[16];
	byte plaintext[64];
	byte ciphertext[64];
	byte re_plaintext[64];

	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char plaintext_string[129] = "7cda46586f7b1393c0ad428ca36712f1bfdb2100bbde1725423e1b6b16a672f18e3e72fab444339b58413b5be37d0a87a73af1946e646fdfa071b71eafa1c714";
	char ciphertext_string[129];
	char re_plaintext_string[129];

	struct RatchetedFDE ctx;
	struct ChainState final_state;

	int result;

	printf("Key used: %s\n", key_string);
	printf("Plaintext used: %s\n", plaintext_string);

	hex_to_bytes(key_string, key, 16);
	hex_to_bytes(plaintext_string, plaintext, 64);

	result = RatchetedFDE_init(key, 16, 4, SCOPE_SECTOR, &ctx);
	if (result != 0) {
		printf("Error in RatchetedFDE_init: %d\n", result);
		return -1;
	}

	printf("Sector size: %d\n", ctx.sector_size);

	uint32_t lba = 0x13;

	result = ratchet_encrypt_sector(&ctx, lba, plaintext, ciphertext, NULL, &final_state);
	if (result != 0) {
		printf("Error in ratchet_encrypt_sector: %d\n", result);
		return -1;
	}
	bytes_to_hex(ciphertext, ciphertext_string, ctx.sector_size);

	printf("Ciphertext: %s\n", ciphertext_string);

	result = ratchet_decrypt_sector(&ctx, lba, ciphertext, re_plaintext, NULL, NULL);
	if (result != 0) {
		printf("Error in ratchet_decrypt_sector: %d\n", result);
		return -1;
	}
	bytes_to_hex(re_plaintext, re_plaintext_string, ctx.sector_size);

	printf("Decrypted plaintext: %s\n", re_plaintext_string);
	printf("\n");

	if (memcmp(plaintext, re_plaintext, ctx.sector_size) == 0) {
		printf("Sector roundtrip matches original plaintext\n");
	}
	else {
		printf("Sector roundtrip does NOT match original plaintext\n");
		return -1;
	}

	return 0;
}