#include "xex.h"

int xex_encrypt_block(const byte* key, const byte* tweak, const byte* block, byte* out, size_t length) {
	byte masked[length];
	byte core[length];

	xor_bytes(block, tweak, masked, length);
	int result = aes_block_encrypt(key, masked, core, length);
	if (result != 0) {
		return result;
	}
	xor_bytes(core, tweak, out, length);

	return 0;
}

int xex_decrypt_block(const byte* key, const byte* tweak, const byte* block, byte* out, size_t length) {
	byte masked[length];
	byte core[length];

	xor_bytes(block, tweak, masked, length);
	int result = aes_block_decrypt(key, masked, core, length);
	if (result != 0) {
		return result;
	}
	xor_bytes(core, tweak, out, length);

	return 0;
}

int update_state(const byte* key, const byte* tweak, const byte* block, const byte* key_F, const byte* key_G, byte* next_key, byte* next_tweak, size_t length) {
	byte masked[length];
	int result;
	
	result = aes_block_encrypt(key_F, block, next_tweak, length);
	if (result != 0) {
		return result;
	}
	xor_bytes(key, block, masked, length);
	result = aes_block_encrypt(key_G, masked, next_key, length);
	if (result != 0) {
		return result;
	}

	return 0;
}