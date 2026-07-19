#include "primitives.h"

#include <mbedtls/aes.h>

void xor_bytes(const byte* a, const byte* b, byte* out, size_t length) {
	for (size_t i = 0; i < length; i++) {
		out[i] = a[i] ^ b[i];
	}
}

// Maybe inefficient to init context every time?
int aes_block_encrypt(const byte* key, const byte* block, byte* out, size_t key_length) {
	mbedtls_aes_context ctx;
	int result;

	mbedtls_aes_init(&ctx);
	result = mbedtls_aes_setkey_enc(&ctx, key, key_length * 8);
	if (result != 0) {
		return result;
	}
	result = mbedtls_aes_crypt_ecb(&ctx, MBEDTLS_AES_ENCRYPT, block, out);
	if (result != 0) {
		return result;
	}
	mbedtls_aes_free(&ctx);

	return 0;
}

int aes_block_decrypt(const byte* key, const byte* block, byte* out, size_t key_length) {
	mbedtls_aes_context ctx;
	int result;

	mbedtls_aes_init(&ctx);
	result = mbedtls_aes_setkey_dec(&ctx, key, key_length * 8);
	if (result != 0) {
		return result;
	}
	result = mbedtls_aes_crypt_ecb(&ctx, MBEDTLS_AES_DECRYPT, block, out);
	if (result != 0) {
		return result;
	}
	mbedtls_aes_free(&ctx);

	return 0;
}