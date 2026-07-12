#include <mbedtls/aes.h>
#include <string.h>
#include <stdio.h>

void hex_to_bytes(const char *hex, unsigned char *out, size_t out_len) {
	for (size_t i = 0; i < out_len; i++) {
		sscanf(hex + 2 * i, "%2hhx", &out[i]);
	}
}

int main() {
	mbedtls_aes_context ctx;
	unsigned char key[16];
	unsigned char in[16];
	unsigned char out[16];

	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char in_string[33] = "746772676f6f6e747265617061626364";

	hex_to_bytes(key_string, key, 16);
	hex_to_bytes(in_string, in, 16);

	mbedtls_aes_init(&ctx);
	mbedtls_aes_setkey_enc(&ctx, key, 128);
	mbedtls_aes_crypt_ecb(&ctx, MBEDTLS_AES_ENCRYPT, in, out);
	mbedtls_aes_free(&ctx);

	printf("Key used: %s\n", key_string);
	printf("Input string used: %s\n", in_string);
	printf("Output string: ");
	for (int i = 0; i < 16; i++) printf("%02x", out[i]);
	printf("\n");
	return 0;
}
