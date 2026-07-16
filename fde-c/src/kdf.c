#include "kdf.h"

#include <mbedtls/hkdf.h>

void expand_master_key(const byte* master_key, byte* key_0, byte* key_F, byte* key_G, size_t key_length) {
	const mbedtls_md_info_t* sha256_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
	
	byte* expanded[48];
	mbedtls_hkdf(sha256_info, 0, 0, master_key, key_length * 8, "ratcheted-fde-demo:c:key-separation", 37, expanded, 48 * 8);

	for (size_t i = 0; i < 16; i++) {
		key_0[i] = expanded[i];
		key_F[i] = expanded[i + 16];
		key_G[i] = expanded[i + 32];
	}
}