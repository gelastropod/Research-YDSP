#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <openssl/evp.h>
#include "blake3.h"

#define FDE_KL 32  // Master key length (256-bit / 32 bytes)
#define FDE_BL 16  // AES Block length (128-bit / 16 bytes)

// =====================================================================
// AES SINGLE-BLOCK PRIMITIVES (ECB MODE)
// =====================================================================

// AES-256 Encryption (32-byte Key, 16-byte input/output block)
void AES256_Enc(const uint8_t *key_32B, const uint8_t *in_16B, uint8_t *out_16B) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, key_32B, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_EncryptUpdate(ctx, out_16B, &outlen, in_16B, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// AES-256 Decryption (32-byte Key, 16-byte input/output block)
void AES256_Dec(const uint8_t *key_32B, const uint8_t *in_16B, uint8_t *out_16B) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_DecryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, key_32B, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_DecryptUpdate(ctx, out_16B, &outlen, in_16B, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// =====================================================================
// SCHEME C2 (CBC RATCHET - BLAKE3 VARIANT)
// =====================================================================

/*
 * Ratchet_CBC_BLAKE3.Enc(K0, P[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         C[j] <- AES.Enc(K, P[j])
 *         K <- BLAKE3.hash(K || C[j])
 *     return C[1..n]
 */
void Ratchet_CBC_BLAKE3_Enc(const uint8_t *K0, const uint8_t *P, 
                           const uint32_t *I, uint64_t S, size_t n, uint8_t *C) {
    // 1. Pack sector index S into 16-byte block
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    // 2. K_seed <- AES256.Enc(K0, S) (16-byte initial seed)
    uint8_t K_seed[FDE_BL];
    AES256_Enc(K0, S_block, K_seed);

    // 3. Initialize 32-byte state K for BLAKE3 output / AES-256 keying
    uint8_t K[32];
    memset(K, 0, 32);
    memcpy(K, K_seed, FDE_BL);

    // 4. Ratchet Loop
    for (size_t j = 0; j < n; j++) {
        (void)I; // Index array I[1..n] unused in CBC loop as per spec
        const uint8_t *P_j = P + (j * FDE_BL);
        uint8_t *C_j = C + (j * FDE_BL);

        // C[j] <- AES256.Enc(K, P[j])
        AES256_Enc(K, P_j, C_j);

        // K <- BLAKE3.hash(K || C[j]) (32B key + 16B ciphertext = 48B input)
        blake3_hasher hasher;
        blake3_hasher_init(&hasher);
        blake3_hasher_update(&hasher, K, 32);
        blake3_hasher_update(&hasher, C_j, FDE_BL);
        blake3_hasher_finalize(&hasher, K, 32);
    }
}

/*
 * Ratchet_CBC_BLAKE3.Dec(K0, C[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         P[j] <- AES.Dec(K, C[j])
 *         K <- BLAKE3.hash(K || C[j])
 *     return P[1..n]
 */
void Ratchet_CBC_BLAKE3_Dec(const uint8_t *K0, const uint8_t *C, 
                           const uint32_t *I, uint64_t S, size_t n, uint8_t *P) {
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    uint8_t K_seed[FDE_BL];
    AES256_Enc(K0, S_block, K_seed);

    uint8_t K[32];
    memset(K, 0, 32);
    memcpy(K, K_seed, FDE_BL);

    for (size_t j = 0; j < n; j++) {
        (void)I;
        const uint8_t *C_j = C + (j * FDE_BL);
        uint8_t *P_j = P + (j * FDE_BL);

        // P[j] <- AES256.Dec(K, C[j])
        AES256_Dec(K, C_j, P_j);

        // K <- BLAKE3.hash(K || C[j])
        blake3_hasher hasher;
        blake3_hasher_init(&hasher);
        blake3_hasher_update(&hasher, K, 32);
        blake3_hasher_update(&hasher, C_j, FDE_BL);
        blake3_hasher_finalize(&hasher, K, 32);
    }
}

// =====================================================================
// BENCHMARK FRAMEWORK
// =====================================================================

double get_time_sec() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

void run_benchmark(size_t sector_size_bytes, int iterations) {
    size_t n = sector_size_bytes / FDE_BL;

    uint8_t K0[FDE_KL];
    uint8_t *P = malloc(sector_size_bytes);
    uint8_t *C = malloc(sector_size_bytes);
    uint8_t *Decrypted_P = malloc(sector_size_bytes);
    uint32_t *I = malloc(n * sizeof(uint32_t));
    uint64_t S = 9999;

    memset(K0, 0x11, FDE_KL);
    memset(P, 0x55, sector_size_bytes);
    for (size_t j = 0; j < n; j++) I[j] = (uint32_t)(j + 1);

    // 1. Correctness Verification
    Ratchet_CBC_BLAKE3_Enc(K0, P, I, S, n, C);
    Ratchet_CBC_BLAKE3_Dec(K0, C, I, S, n, Decrypted_P);

    if (memcmp(P, Decrypted_P, sector_size_bytes) != 0) {
        printf("[FAIL] Sector Size %zu: Decrypted text does not match Plaintext!\n", sector_size_bytes);
        free(P); free(C); free(Decrypted_P); free(I);
        return;
    }

    // 2. Performance Benchmark
    double start_time = get_time_sec();
    for (int i = 0; i < iterations; i++) {
        Ratchet_CBC_BLAKE3_Enc(K0, P, I, S, n, C);
    }
    double elapsed = get_time_sec() - start_time;
    double total_mb = ((double)(sector_size_bytes * iterations)) / (1024.0 * 1024.0);
    double mb_s = total_mb / elapsed;

    printf("Sector Size: %4zu bytes (%2zu blocks) | Time: %.6f s | Throughput: %8.2f MB/s [PASS]\n",
           sector_size_bytes, n, elapsed, mb_s);

    free(P);
    free(C);
    free(Decrypted_P);
    free(I);
}

int main() {
    printf("=== Scheme C2 (CBC Ratchet - BLAKE3 Variant) ===\n\n");

    int iterations = 10000;

    run_benchmark(512, iterations);
    run_benchmark(4096, iterations);

    return 0;
}