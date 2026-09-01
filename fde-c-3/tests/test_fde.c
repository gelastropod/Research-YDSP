#include "fde.h"
#include "blake3.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures = 0;

#define CHECK(condition, message)                                                \
    do {                                                                         \
        if (!(condition)) {                                                       \
            fprintf(stderr, "[FAIL] %s\n", (message));                         \
            ++failures;                                                          \
        } else {                                                                 \
            printf("[PASS] %s\n", (message));                                  \
        }                                                                        \
    } while (0)

static void fill_data(uint8_t *data, size_t bytes, uint32_t seed) {
    uint32_t x = seed;
    for (size_t i = 0; i < bytes; ++i) {
        x = x * UINT32_C(1664525) + UINT32_C(1013904223);
        data[i] = (uint8_t)(x >> 24);
    }
}

static void test_blake3_vector(void) {
    static const uint8_t expected[32] = {
        0xaf, 0x13, 0x49, 0xb9, 0xf5, 0xf9, 0xa1, 0xa6,
        0xa0, 0x40, 0x4d, 0xea, 0x36, 0xdc, 0xc9, 0x49,
        0x9b, 0xcb, 0x25, 0xc9, 0xad, 0xc1, 0x12, 0xb7,
        0xcc, 0x9a, 0x93, 0xca, 0xe4, 0x1f, 0x32, 0x62
    };
    uint8_t actual[32];
    blake3_hasher hasher;
    blake3_hasher_init(&hasher);
    blake3_hasher_finalize(&hasher, actual, sizeof(actual));
    CHECK(memcmp(actual, expected, sizeof(actual)) == 0,
          "vendored BLAKE3 passes the official empty-input vector");
}

static void test_roundtrips(fde_worker *worker) {
    const size_t sizes[] = {512, 4096};
    for (int scheme = 0; scheme < FDE_SCHEME_COUNT; ++scheme) {
        for (size_t s = 0; s < sizeof(sizes) / sizeof(sizes[0]); ++s) {
            size_t bytes = sizes[s];
            size_t blocks = bytes / FDE_BLOCK_BYTES;
            uint8_t *plain = malloc(bytes);
            uint8_t *cipher = malloc(bytes);
            uint8_t *recovered = malloc(bytes);
            uint32_t *indices = malloc(blocks * sizeof(*indices));
            char message[160];
            if (plain == NULL || cipher == NULL || recovered == NULL ||
                indices == NULL) {
                fprintf(stderr, "allocation failure\n");
                exit(2);
            }
            fill_data(plain, bytes, (uint32_t)(100 + 10 * scheme + s));
            for (size_t j = 0; j < blocks; ++j) {
                indices[j] = (uint32_t)j;
            }
            int ok = fde_encrypt(worker, (fde_scheme)scheme, plain, indices,
                                 UINT64_C(0x0123456789abcdef), blocks, cipher,
                                 NULL) == 0 &&
                     fde_decrypt(worker, (fde_scheme)scheme, cipher, indices,
                                 UINT64_C(0x0123456789abcdef), blocks,
                                 recovered, NULL) == 0 &&
                     memcmp(plain, recovered, bytes) == 0;
            snprintf(message, sizeof(message), "%s round-trips %zu-byte sectors",
                     fde_scheme_name((fde_scheme)scheme), bytes);
            CHECK(ok, message);
            free(plain);
            free(cipher);
            free(recovered);
            free(indices);
        }
    }
}

static void test_xts_paths(fde_worker *worker) {
    enum { BLOCKS = 32, BYTES = 32 * 16 };
    uint8_t plain[BYTES];
    uint8_t sequential[BYTES];
    uint8_t indexed[BYTES];
    uint8_t openssl[BYTES];
    uint8_t recovered[BYTES];
    uint32_t indices[BLOCKS];
    uint32_t shuffled[BLOCKS];
    fill_data(plain, sizeof(plain), 2026);
    for (size_t j = 0; j < BLOCKS; ++j) {
        indices[j] = (uint32_t)j;
        shuffled[j] = (uint32_t)((j * 11u) % BLOCKS);
    }
    CHECK(fde_encrypt(worker, FDE_XTS, plain, indices, 17, BLOCKS,
                      sequential, NULL) == 0 &&
              fde_xts_encrypt_indexed(worker, plain, indices, 17, BLOCKS,
                                      indexed, NULL) == 0 &&
              memcmp(sequential, indexed, BYTES) == 0,
          "sequential XTS recurrence matches the exact Task 9 indexed formula");

    CHECK(fde_xts_openssl_encrypt(worker, plain, 17, BYTES, openssl) == 0 &&
              memcmp(sequential, openssl, BYTES) == 0,
          "manual sequential XTS matches OpenSSL AES-256-XTS");

    CHECK(fde_xts_openssl_decrypt(worker, openssl, 17, BYTES, recovered) == 0 &&
              memcmp(plain, recovered, BYTES) == 0,
          "OpenSSL full-data-unit XTS reference round-trips");

    CHECK(fde_xts_encrypt_indexed(worker, plain, shuffled, 17, BLOCKS,
                                  indexed, NULL) == 0 &&
              fde_xts_decrypt_indexed(worker, indexed, shuffled, 17, BLOCKS,
                                      recovered, NULL) == 0 &&
              memcmp(plain, recovered, BYTES) == 0,
          "indexed XTS supports arbitrary non-duplicated index order");
}

static void test_index_semantics(fde_worker *worker) {
    enum { BLOCKS = 4, BYTES = 64 };
    uint8_t plain[BYTES];
    uint8_t a[BYTES];
    uint8_t b[BYTES];
    uint32_t first[BLOCKS] = {0, 1, 2, 3};
    uint32_t second[BLOCKS] = {0, 1, 99, 3};
    fill_data(plain, sizeof(plain), 77);

    CHECK(fde_encrypt(worker, FDE_RATCHET_CTR_AES, plain, first, 9, BLOCKS,
                      a, NULL) == 0 &&
              fde_encrypt(worker, FDE_RATCHET_CTR_AES, plain, second, 9,
                          BLOCKS, b, NULL) == 0 &&
              memcmp(a, b, BYTES) != 0,
          "CTR ratchet binds the caller-supplied I[j] value");

    CHECK(fde_encrypt(worker, FDE_RATCHET_CBC_AES, plain, first, 9, BLOCKS,
                      a, NULL) == 0 &&
              fde_encrypt(worker, FDE_RATCHET_CBC_AES, plain, second, 9,
                          BLOCKS, b, NULL) == 0 &&
              memcmp(a, b, BYTES) == 0,
          "CBC ratchet ignores I[j] exactly as Task 9 specifies");
}

static void test_target_recovery(fde_worker *worker) {
    enum { BLOCKS = 256, BYTES = 4096 };
    uint8_t plain[BYTES];
    uint8_t cipher[BYTES];
    uint8_t target[16];
    uint32_t indices[BLOCKS];
    const size_t positions[] = {0, 31, 63, 127, 191, 255};
    fill_data(plain, sizeof(plain), 9182);
    for (size_t j = 0; j < BLOCKS; ++j) {
        indices[j] = (uint32_t)j;
    }
    for (int scheme = 0; scheme < FDE_SCHEME_COUNT; ++scheme) {
        int ok = fde_encrypt(worker, (fde_scheme)scheme, plain, indices, 122,
                             BLOCKS, cipher, NULL) == 0;
        for (size_t k = 0; ok && k < sizeof(positions) / sizeof(positions[0]);
             ++k) {
            size_t target_index = positions[k];
            ok = fde_decrypt_target(worker, (fde_scheme)scheme, cipher, indices,
                                    122, BLOCKS, target_index, target) == 0 &&
                 memcmp(target, plain + 16 * target_index, 16) == 0;
        }
        char message[160];
        snprintf(message, sizeof(message), "%s recovers every RQ4 target block",
                 fde_scheme_name((fde_scheme)scheme));
        CHECK(ok, message);
    }
}

int main(void) {
    fde_keys keys;
    fde_worker *worker;
    fde_default_keys(&keys);
    worker = fde_worker_new(&keys);
    if (worker == NULL) {
        fprintf(stderr, "failed to initialise OpenSSL contexts\n");
        return 2;
    }

    test_blake3_vector();
    test_roundtrips(worker);
    test_xts_paths(worker);
    test_index_semantics(worker);
    test_target_recovery(worker);

    fde_worker_free(worker);
    if (failures != 0) {
        fprintf(stderr, "%d test(s) failed\n", failures);
        return 1;
    }
    printf("All correctness tests passed.\n");
    return 0;
}
