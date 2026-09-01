#include "xts.h"

#include <string.h>
#include <stdlib.h>

#include "xex.h"

int xts_encrypt_sector_old(uint32_t lba, const byte* plaintext, uint32_t plaintext_length, byte* ciphertext, const struct ChainState* state_in, struct ChainState* state_out) {
	struct ChainState st;
	int result;

	uint32_t excess = plaintext_length % BLOCK_SIZE;
	uint32_t end_of_xex = plaintext_length - excess;
	byte* res = (byte*)(malloc(plaintext_length));

	struct RatchetedFDE modified;
	memcpy(modified.key_0, ctx->key_0, BLOCK_SIZE);
	memcpy(modified.key_F, ctx->key_F, BLOCK_SIZE);
	memcpy(modified.key_G, ctx->key_G, BLOCK_SIZE);
	modified.sector_size = end_of_xex;
	modified.blocks_per_sector = end_of_xex / BLOCK_SIZE;
	modified.scope = ctx->scope;
	result = ratchet_encrypt_sector(&modified, lba, plaintext, res, state_in, &st);
	if (result != 0) return result;

	byte excess_plaintext[BLOCK_SIZE];
	byte excess_ciphertext[BLOCK_SIZE];

	memcpy(excess_plaintext, plaintext + end_of_xex, excess);
	memcpy(excess_plaintext + excess, res + plaintext_length - BLOCK_SIZE, BLOCK_SIZE - excess);

	byte next_key[BLOCK_SIZE], next_tweak[BLOCK_SIZE];
	
	result = xex_encrypt_block(st.key, st.tweak, excess_plaintext, excess_ciphertext, BLOCK_SIZE);
	if (result != 0) return result;

	result = update_state(st.key, st.tweak, excess_ciphertext, ctx->key_F, ctx->key_G, next_key, next_tweak, BLOCK_SIZE);
	if (result != 0) return result;

	memcpy(ciphertext, res, end_of_xex - BLOCK_SIZE);
	memcpy(ciphertext + end_of_xex, res + end_of_xex - BLOCK_SIZE, excess);
	memcpy(ciphertext + end_of_xex - BLOCK_SIZE, excess_ciphertext, BLOCK_SIZE);
	memcpy(st.key, next_key, BLOCK_SIZE);
	memcpy(st.tweak, next_tweak, BLOCK_SIZE);
	free(res);

	if (state_out != NULL) {
		*state_out = st;
	}

	return 0;
}

int xts_decrypt_sector_old(uint32_t lba, const byte* ciphertext, uint32_t ciphertext_length, byte* plaintext, const struct ChainState* state_in, struct ChainState* state_out) {
	struct ChainState st;
	int result;

	uint32_t excess = ciphertext_length % BLOCK_SIZE;
	uint32_t end_of_xex = ciphertext_length - excess;
	byte* res = (byte*)(malloc(ciphertext_length));

	struct RatchetedFDE modified;
	memcpy(modified.key_0, ctx->key_0, BLOCK_SIZE);
	memcpy(modified.key_F, ctx->key_F, BLOCK_SIZE);
	memcpy(modified.key_G, ctx->key_G, BLOCK_SIZE);
	modified.sector_size = end_of_xex;
	modified.blocks_per_sector = end_of_xex / BLOCK_SIZE;
	modified.scope = ctx->scope;
	result = ratchet_decrypt_sector(&modified, lba, ciphertext, res, state_in, &st);
	if (result != 0) return result;

	byte excess_plaintext[BLOCK_SIZE];
	byte excess_ciphertext[BLOCK_SIZE];

	memcpy(excess_ciphertext, ciphertext + end_of_xex, excess);
	memcpy(excess_ciphertext + excess, res + ciphertext_length - BLOCK_SIZE, BLOCK_SIZE - excess);

	byte next_key[BLOCK_SIZE], next_tweak[BLOCK_SIZE];
	
	result = xex_decrypt_block(st.key, st.tweak, excess_ciphertext, excess_plaintext, BLOCK_SIZE);
	if (result != 0) return result;

	result = update_state(st.key, st.tweak, excess_ciphertext, ctx->key_F, ctx->key_G, next_key, next_tweak, BLOCK_SIZE);
	if (result != 0) return result;

	memcpy(plaintext, res, end_of_xex - BLOCK_SIZE);
	memcpy(plaintext + end_of_xex, res + end_of_xex - BLOCK_SIZE, excess);
	memcpy(plaintext + end_of_xex - BLOCK_SIZE, excess_plaintext, BLOCK_SIZE);
	memcpy(st.key, next_key, BLOCK_SIZE);
	memcpy(st.tweak, next_tweak, BLOCK_SIZE);
	free(res);

	if (state_out != NULL) {
		*state_out = st;
	}

	return 0;
}

int xts_encrypt_volume_old(const byte* plaintext, uint32_t plaintext_length, byte* ciphertext) {
    struct ChainState global_state;
    int result;

	uint32_t excess = plaintext_length % ctx->sector_size;
	uint32_t end_of_xex = plaintext_length - excess;
    
	for (size_t off = 0; off < end_of_xex; off += ctx->sector_size) {
        uint32_t lba = (uint32_t)(off / ctx->sector_size);
        const byte* sector = plaintext + off;
        byte* out = ciphertext + off;

        if (ctx->scope == SCOPE_SECTOR) {
            result = ratchet_encrypt_sector(ctx, lba, sector, out, NULL, NULL);
        }
        else {
            if (lba == 0) {
                encode_lba(0, global_state.tweak);
                memcpy(global_state.key, ctx->key_0, BLOCK_SIZE);
            }
            result = ratchet_encrypt_sector(ctx, lba, sector, out, &global_state, &global_state);
        }

        if (result != 0) return result;
    }

	if (excess == 0) return 0;

	uint32_t lba = (uint32_t)(end_of_xex / ctx->sector_size);
	const byte* sector = plaintext + end_of_xex;
	byte* out = ciphertext + end_of_xex;

	if (ctx->scope == SCOPE_SECTOR) {
		result = xts_encrypt_sector_old(ctx, lba, sector, excess, out, NULL, NULL);
	}
	else {
		if (lba == 0) {
			encode_lba(0, global_state.tweak);
			memcpy(global_state.key, ctx->key_0, BLOCK_SIZE);
		}
		result = xts_encrypt_sector_old(ctx, lba, sector, excess, out, &global_state, &global_state);
	}

	if (result != 0) return result;

    return 0;
}

int xts_decrypt_volume_old(const byte* ciphertext, uint32_t ciphertext_length, byte* plaintext) {
    struct ChainState global_state;
    int result;

	uint32_t excess = ciphertext_length % ctx->sector_size;
	uint32_t end_of_xex = ciphertext_length - excess;
    
	for (size_t off = 0; off < end_of_xex; off += ctx->sector_size) {
        uint32_t lba = (uint32_t)(off / ctx->sector_size);
        const byte* sector = ciphertext + off;
        byte* out = plaintext + off;

        if (ctx->scope == SCOPE_SECTOR) {
            result = ratchet_decrypt_sector(ctx, lba, sector, out, NULL, NULL);
        }
        else {
            if (lba == 0) {
                encode_lba(0, global_state.tweak);
                memcpy(global_state.key, ctx->key_0, BLOCK_SIZE);
            }
            result = ratchet_decrypt_sector(ctx, lba, sector, out, &global_state, &global_state);
        }

        if (result != 0) return result;
    }

	if (excess == 0) return 0;

	uint32_t lba = (uint32_t)(end_of_xex / ctx->sector_size);
	const byte* sector = ciphertext + end_of_xex;
	byte* out = plaintext + end_of_xex;

	if (ctx->scope == SCOPE_SECTOR) {
		result = xts_decrypt_sector_old(ctx, lba, sector, excess, out, NULL, NULL);
	}
	else {
		if (lba == 0) {
			encode_lba(0, global_state.tweak);
			memcpy(global_state.key, ctx->key_0, BLOCK_SIZE);
		}
		result = xts_decrypt_sector_old(ctx, lba, sector, excess, out, &global_state, &global_state);
	}

	if (result != 0) return result;

    return 0;
}
