#include "ratchet.h"

#include <string.h>

#include "kdf.h"
#include "xex.h"
#include "primitives.h"

int RatchetedFDE_init(const byte* key, uint32_t key_length, uint32_t blocks_per_sector, enum Scope scope, struct RatchetedFDE* ratchet) {
	int result = expand_master_key(key, ratchet->key_0, ratchet->key_F, ratchet->key_G, key_length);
    if (result != 0) {
        return result;
    }
	ratchet->blocks_per_sector = blocks_per_sector;
	ratchet->sector_size = blocks_per_sector * BLOCK_SIZE;
	ratchet->scope = scope;

    return 0;
}

int ratchet_encrypt_sector(const struct RatchetedFDE* ctx, uint32_t lba, const byte* plaintext, byte* ciphertext, const struct ChainState* state_in, struct ChainState* state_out) {
    struct ChainState st;

    if (state_in == NULL) {
        encode_lba(lba, st.tweak);
        memcpy(st.key, ctx->key_0, BLOCK_SIZE);
    }
    else {
        st = *state_in;
    }

    for (size_t off = 0; off < ctx->sector_size; off += BLOCK_SIZE) {
        byte next_key[BLOCK_SIZE], next_tweak[BLOCK_SIZE];
        int result;

        result = xex_encrypt_block(st.key, st.tweak, plaintext + off, ciphertext + off, BLOCK_SIZE);
        if (result != 0) return result;

        result = update_state(st.key, st.tweak, ciphertext + off, ctx->key_F, ctx->key_G, next_key, next_tweak, BLOCK_SIZE);
        if (result != 0) return result;

        memcpy(st.key, next_key, BLOCK_SIZE);
        memcpy(st.tweak, next_tweak, BLOCK_SIZE);
    }

    if (state_out != NULL) {
        *state_out = st;
    }

    return 0;
}

int ratchet_decrypt_sector(const struct RatchetedFDE* ctx, uint32_t lba, const byte* ciphertext, byte* plaintext, const struct ChainState* state_in, struct ChainState* state_out) {
    struct ChainState st;

    if (state_in == NULL) {
        encode_lba(lba, st.tweak);
        memcpy(st.key, ctx->key_0, BLOCK_SIZE);
    }
    else {
        st = *state_in;
    }

    for (size_t off = 0; off < ctx->sector_size; off += BLOCK_SIZE) {
        byte next_key[BLOCK_SIZE], next_tweak[BLOCK_SIZE];
        int result;

        result = xex_decrypt_block(st.key, st.tweak, ciphertext + off, plaintext + off, BLOCK_SIZE);
        if (result != 0) return result;

        result = update_state(st.key, st.tweak, ciphertext + off, ctx->key_F, ctx->key_G, next_key, next_tweak, BLOCK_SIZE);
        if (result != 0) return result;

        memcpy(st.key, next_key, BLOCK_SIZE);
        memcpy(st.tweak, next_tweak, BLOCK_SIZE);
    }

    if (state_out != NULL) {
        *state_out = st;
    }

    return 0;
}

int ratchet_encrypt_volume(const struct RatchetedFDE* ctx, const byte* plaintext, uint32_t plaintext_len, byte* ciphertext) {
    struct ChainState global_state;
    int result;

    for (size_t off = 0; off < plaintext_len; off += ctx->sector_size) {
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

    return 0;
}

int ratchet_decrypt_volume(const struct RatchetedFDE* ctx, const byte* ciphertext, uint32_t ciphertext_len, byte* plaintext) {
    struct ChainState global_state;
    int result;

    for (size_t off = 0; off < ciphertext_len; off += ctx->sector_size) {
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

    return 0;
}
