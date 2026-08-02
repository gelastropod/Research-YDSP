#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

#include "test_utils.h"
#include "ratchet.h"
#include "primitives.h"

void make_sector_label(uint32_t i, size_t sector_size, byte* out) {
    char label[16];
    int label_len = snprintf(label, sizeof(label), "SECTOR-%04u|", i);

    for (uint32_t pos = 0; pos < sector_size; pos++) {
        out[pos] = (byte)label[pos % label_len];
    }
}

void make_volume(uint32_t num_sectors, uint32_t sector_size, byte* out) {
    for (uint32_t i = 0; i < num_sectors; i++) {
        make_sector_label(i, sector_size, out + i * sector_size);
    }
}

struct AES_state {
	const byte *key, *plaintext;
	byte *ciphertext, *re_plaintext;
	uint32_t key_length, plaintext_length;
};

void aes_roundtrip(void* ctx) {
	struct AES_state* state = (struct AES_state*)ctx;
	aes_encrypt_volume(state->key, state->plaintext, state->ciphertext, state->key_length, state->plaintext_length);
	aes_decrypt_volume(state->key, state->ciphertext, state->re_plaintext, state->key_length, state->plaintext_length);
}

struct XTS_state {
	const byte *key, *plaintext;
	byte *ciphertext, *re_plaintext;
	uint32_t key_length, sector_size, plaintext_length;
};

void xts_roundtrip(void* ctx) {
	struct XTS_state* state = (struct XTS_state*)ctx;
	xts_encrypt_volume(state->key, state->plaintext, state->ciphertext, state->key_length, state->sector_size, state->plaintext_length);
	xts_decrypt_volume(state->key, state->ciphertext, state->re_plaintext, state->key_length, state->sector_size, state->plaintext_length);
}

struct Ratchet_state {
	const struct RatchetedFDE* ctx;
	const byte* plaintext;
	byte *ciphertext, *re_plaintext;
	uint32_t plaintext_length;
};

void ratchet_roundtrip(void* ctx) {
	struct Ratchet_state* state = (struct Ratchet_state*)ctx;
	ratchet_encrypt_volume(state->ctx, state->plaintext, state->plaintext_length, state->ciphertext);
	ratchet_decrypt_volume(state->ctx, state->ciphertext, state->plaintext_length, state->re_plaintext);
}

double benchmark(void (*roundtrip)(void*), void* ctx, int rounds) {
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    for (int i = 0; i < rounds; i++) {
		roundtrip(ctx);
    }

    clock_gettime(CLOCK_MONOTONIC, &t1);

    double elapsed = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
    return elapsed;
}

int main() {
	uint32_t blocks_per_sector = 16;
	uint32_t num_sectors = 64;

	byte key[16], xts_key[32];
	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	char xts_key_string[65] = "e952be5248628ff1b75ddeb7a56b17edc20d645402106651d86b58391b1f4719";
	hex_to_bytes(key_string, key, 16);
	hex_to_bytes(xts_key_string, xts_key, 32);

	struct RatchetedFDE sector_ctx, global_ctx;
	int result;

	result = RatchetedFDE_init(key, 16, blocks_per_sector, SCOPE_SECTOR, &sector_ctx);
	if (result != 0) {
		printf("Error initializing sector_ctx: %d\n", result);
		return -1;
	}

	result = RatchetedFDE_init(key, 16, blocks_per_sector, SCOPE_GLOBAL, &global_ctx);
	if (result != 0) {
		printf("Error initializing global_ctx: %d\n", result);
		return -1;
	}

	uint32_t sector_size = (uint32_t)sector_ctx.sector_size;
	uint32_t plaintext_len = num_sectors * sector_size;

	byte* plaintext = (byte*)(malloc(plaintext_len));
	make_volume(num_sectors, sector_size, plaintext);

	printf("Plaintext length: %d bytes (%d sectors x %d bytes)\n", plaintext_len, num_sectors, sector_size);

	int rounds = 10000;

	struct AES_state aes_state;
	aes_state.key = key;
	aes_state.plaintext = plaintext;
	aes_state.ciphertext = (byte*)(malloc(plaintext_len));
	aes_state.re_plaintext = (byte*)(malloc(plaintext_len));
	aes_state.key_length = 16;
	aes_state.plaintext_length = plaintext_len;

	double aes_time = benchmark(aes_roundtrip, &aes_state, rounds);
	printf("AES %d encrypt+decrypt cycles: %.4f s\n", rounds, aes_time);
	free(aes_state.ciphertext);
	free(aes_state.re_plaintext);

	struct XTS_state xts_state;
	xts_state.key = xts_key;
	xts_state.plaintext = plaintext;
	xts_state.ciphertext = (byte*)(malloc(plaintext_len));
	xts_state.re_plaintext = (byte*)(malloc(plaintext_len));
	xts_state.key_length = 32;
	xts_state.sector_size = sector_size;
	xts_state.plaintext_length = plaintext_len;

	double xts_time = benchmark(xts_roundtrip, &xts_state, rounds);
	printf("AES-XTS %d encrypt+decrypt cycles: %.4f s\n", rounds, xts_time);
	free(xts_state.ciphertext);
	free(xts_state.re_plaintext);

	struct Ratchet_state sector_state;
	sector_state.ctx = &sector_ctx;
	sector_state.plaintext = plaintext;
	sector_state.ciphertext = (byte*)(malloc(plaintext_len));
	sector_state.re_plaintext = (byte*)(malloc(plaintext_len));
	sector_state.plaintext_length = plaintext_len;

	double sector_time = benchmark(ratchet_roundtrip, &sector_state, rounds);
	printf("AES-XEX Sector scope %d encrypt+decrypt cycles: %.4f s\n", rounds, sector_time);
	free(sector_state.ciphertext);
	free(sector_state.re_plaintext);

	struct Ratchet_state global_state;
	global_state.ctx = &global_ctx;
	global_state.plaintext = plaintext;
	global_state.ciphertext = (byte*)(malloc(plaintext_len));
	global_state.re_plaintext = (byte*)(malloc(plaintext_len));
	global_state.plaintext_length = plaintext_len;

	double global_time = benchmark(ratchet_roundtrip, &global_state, rounds);
	printf("AES-XEX Global scope %d encrypt+decrypt cycles: %.4f s\n", rounds, global_time);
	free(global_state.ciphertext);
	free(global_state.re_plaintext);

	printf("\n");
	printf("AES average per cycle: %.6f ms\n", (aes_time / rounds) * 1000);
	printf("AES-XTS average per cycle: %.6f ms\n", (xts_time / rounds) * 1000);
	printf("AES-XEX Sector scope average per cycle: %.6f ms\n", (sector_time / rounds) * 1000);
	printf("AES-XEX Global scope average per cycle: %.6f ms\n", (global_time / rounds) * 1000);

	free(plaintext);

	return 0;
}
