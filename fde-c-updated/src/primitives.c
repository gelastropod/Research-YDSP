#include "primitives.h"

#include <mbedtls/aes.h>
#include <string.h>

void xor_bytes(const byte* a, const byte* b, byte* out, uint32_t length) {
	for (size_t i = 0; i < length; i++) {
		out[i] = a[i] ^ b[i];
	}
}

void encode_lba(uint32_t lba, byte* out) {
    memset(out, 0, BLOCK_SIZE);

    for (int i = BLOCK_SIZE - 1; i >= 0 && lba != 0; i--) {
        out[i] = (byte)(lba & 0xFF);
        lba >>= 8;
    }
}

// Maybe inefficient to init context every time?
int aes_block_encrypt(const byte* key, const byte* block, byte* out, uint32_t key_length) {
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

int aes_block_decrypt(const byte* key, const byte* block, byte* out, uint32_t key_length) {
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

int aes_encrypt_volume(const byte* key, const byte* plaintext, byte* ciphertext, uint32_t key_length, uint32_t plaintext_length) {
	for (size_t i = 0; i < plaintext_length; i += 16) {
		int result = aes_block_encrypt(key, plaintext + i, ciphertext + i, key_length);
		if (result != 0) {
			return result;
		}
	}
	return 0;
}

int aes_decrypt_volume(const byte* key, const byte* ciphertext, byte* plaintext, uint32_t key_length, uint32_t ciphertext_length) {
	for (size_t i = 0; i < ciphertext_length; i += 16) {
		int result = aes_block_decrypt(key, ciphertext + i, plaintext + i, key_length);
		if (result != 0) {
			return result;
		}
	}
	return 0;
}

int xts_encrypt_sector(uint32_t lba, const byte* key, const byte* plaintext, byte* ciphertext, uint32_t key_length, uint32_t plaintext_length) {
	byte tweak[BLOCK_SIZE];
	encode_lba(lba, tweak);

	mbedtls_aes_xts_context ctx;
	int result;

	mbedtls_aes_xts_init(&ctx);
	result = mbedtls_aes_xts_setkey_enc(&ctx, key, key_length * 8);
	if (result != 0) {
		return result;
	}
	result = mbedtls_aes_crypt_xts(&ctx, MBEDTLS_AES_ENCRYPT, plaintext_length, tweak, plaintext, ciphertext);
	if (result != 0) {
		return result;
	}
	mbedtls_aes_xts_free(&ctx);

	return 0;
}

int xts_decrypt_sector(uint32_t lba, const byte* key, const byte* ciphertext, byte* plaintext, uint32_t key_length, uint32_t ciphertext_length) {
	byte tweak[BLOCK_SIZE];
	encode_lba(lba, tweak);

	mbedtls_aes_xts_context ctx;
	int result;

	mbedtls_aes_xts_init(&ctx);
	result = mbedtls_aes_xts_setkey_dec(&ctx, key, key_length * 8);
	if (result != 0) {
		return result;
	}
	result = mbedtls_aes_crypt_xts(&ctx, MBEDTLS_AES_DECRYPT, ciphertext_length, tweak, ciphertext, plaintext);
	if (result != 0) {
		return result;
	}
	mbedtls_aes_xts_free(&ctx);

	return 0;
}

int xts_encrypt_volume(const byte* key, const byte* plaintext, byte* ciphertext, uint32_t key_length, uint32_t sector_size, uint32_t plaintext_length) {
	int result;

	size_t off;
	for (off = 0; off < plaintext_length - sector_size; off += sector_size) {
		uint32_t lba = (uint32_t)(off / sector_size);
		result = xts_encrypt_sector(lba, key, plaintext + off, ciphertext + off, key_length, sector_size);
		if (result != 0) {
			return result;
		}
	}

	uint32_t lba = (uint32_t)(off / sector_size);
	result = xts_encrypt_sector(lba, key, plaintext + off, ciphertext + off, key_length, plaintext_length - off);

	return result;
}

int xts_decrypt_volume(const byte* key, const byte* ciphertext, byte* plaintext, uint32_t key_length, uint32_t sector_size, uint32_t ciphertext_length) {
	int result;

	size_t off;
	for (off = 0; off < ciphertext_length - sector_size; off += sector_size) {
		uint32_t lba = (uint32_t)(off / sector_size);
		result = xts_decrypt_sector(lba, key, ciphertext + off, plaintext + off, key_length, sector_size);
		if (result != 0) {
			return result;
		}
	}

	uint32_t lba = (uint32_t)(off / sector_size);
	result = xts_decrypt_sector(lba, key, ciphertext + off, plaintext + off, key_length, ciphertext_length - off);

	return result;
}

