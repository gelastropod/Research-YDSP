#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

#include "test_utils.h"
#include "ratchet.h"

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

double benchmark(const struct RatchetedFDE* ctx, const byte* plaintext, uint32_t plaintext_len, int rounds) {
    byte* ciphertext = malloc(plaintext_len);
    byte* recovered = malloc(plaintext_len);

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    for (int i = 0; i < rounds; i++) {
        ratchet_encrypt_volume(ctx, plaintext, plaintext_len, ciphertext);
        ratchet_decrypt_volume(ctx, ciphertext, plaintext_len, recovered);
    }

    clock_gettime(CLOCK_MONOTONIC, &t1);

    free(ciphertext);
    free(recovered);

    double elapsed = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
    return elapsed;
}

int main() {
	uint32_t blocks_per_sector = 16;
	uint32_t num_sectors = 64;

	byte key[16];
	char key_string[33] = "e952be5248628ff1b75ddeb7a56b17ed";
	hex_to_bytes(key_string, key, 16);

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

	byte* plaintext = malloc(plaintext_len);
	make_volume(num_sectors, sector_size, plaintext);

	printf("Plaintext length: %d bytes (%d sectors x %d bytes)\n", plaintext_len, num_sectors, sector_size);

	int rounds = 10000;

	double sector_time = benchmark(&sector_ctx, plaintext, plaintext_len, rounds);
	printf("Sector scope %d encrypt+decrypt cycles: %.4f s\n", rounds, sector_time);

	double global_time = benchmark(&global_ctx, plaintext, plaintext_len, rounds);
	printf("Global scope %d encrypt+decrypt cycles: %.4f s\n", rounds, global_time);

	printf("Sector scope average per cycle: %.6f ms\n", (sector_time / rounds) * 1000);
	printf("Global scope average per cycle: %.6f ms\n", (global_time / rounds) * 1000);

	free(plaintext);

	return 0;
}