#include "kdf.h"

#include <mbedtls/hkdf.h>

static const unsigned char kdf_info[] = "ratcheted-fde-demo:c:key-separation";

int expand_master_key(const byte* master_key, byte* key_0, byte* key_F, byte* key_G, uint32_t key_length) {
	const mbedtls_md_info_t* sha256_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
	if (sha256_info == NULL) {
		return -1;
	}
	
	byte expanded[48];
	int result = mbedtls_hkdf(sha256_info, NULL, 0, master_key, key_length, kdf_info, sizeof(kdf_info) - 1, expanded, sizeof(expanded));
	if (result != 0) {
		return result;
	}

	for (size_t i = 0; i < 16; i++) {
		key_0[i] = expanded[i];
		key_F[i] = expanded[i + 16];
		key_G[i] = expanded[i + 32];
	}
	return 0;
}