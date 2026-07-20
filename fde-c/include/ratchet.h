#ifndef RATCHET_H
#define RATCHET_H

#include "common.h"

struct ChainState {
	byte key[16];
	byte tweak[16];
};

enum Scope {
	SCOPE_SECTOR,
	SCOPE_GLOBAL
};

struct RatchetedFDE {
	byte key_0[16], key_F[16], key_G[16];
	uint32_t blocks_per_sector, sector_size;
	enum Scope scope;
};

void encode_lba(uint32_t lba, byte* out);

int RatchetedFDE_init(const byte* key, uint32_t key_length, uint32_t blocks_per_sector, enum Scope scope, struct RatchetedFDE* ratchet);
int ratchet_encrypt_sector(const struct RatchetedFDE* ctx, uint32_t lba, const byte* plaintext, byte* ciphertext, const struct ChainState* state_in, struct ChainState* state_out);
int ratchet_decrypt_sector(const struct RatchetedFDE* ctx, uint32_t lba, const byte* ciphertext, byte* plaintext, const struct ChainState* state_in, struct ChainState* state_out);

int ratchet_encrypt_volume(const struct RatchetedFDE* ctx, const byte* plaintext, size_t plaintext_len, byte* ciphertext);
int ratchet_decrypt_volume(const struct RatchetedFDE* ctx, const byte* ciphertext, size_t ciphertext_len, byte* plaintext);

#endif