#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <openssl/evp.h>
#include "blake3.h"

#define FDE_KL 32  // 256-bit Key length (32 bytes)
#define FDE_BL 16  // 128-bit Block length (16 bytes)
#define FDE_IL 4   // Index length (4 bytes)
#define FDE_SL 8   // Sector length (8 bytes)

// =====================================================================
// AES SINGLE-BLOCK HELPERS
// =====================================================================

// AES-256 Encryption (32-byte Key)
void AES256_Enc(const uint8_t *K, const uint8_t *in_block, uint8_t *out_block) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, K, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_EncryptUpdate(ctx, out_block, &outlen, in_block, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// AES-128 Encryption (16-byte Key)
void AES128_Enc(const uint8_t *K, const uint8_t *in_block, uint8_t *out_block) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_128_ecb(), NULL, K, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_EncryptUpdate(ctx, out_block, &outlen, in_block, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// Helper: Bitwise XOR of 16-byte blocks
void xor_16bytes(uint8_t *out, const uint8_t *a, const uint8_t *b) {
    for (int i = 0; i < FDE_BL; i++) {
        out[i] = a[i] ^ b[i];
    }
}

// Helper: Pack uint32 index into a 16-byte block
void pack_index(uint32_t index_val, uint8_t *block) {
    memset(block, 0, FDE_BL);
    memcpy(block, &index_val, sizeof(index_val));
}

// =====================================================================
// VARIANT 1: Ratchet_CTR_BLAKE3
// =====================================================================

/*
 * Ratchet_CTR_BLAKE3.Enc(K0, P[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         C[j] <- P[j] ^ AES.Enc(K, I[j])
 *         K <- BLAKE3.hash(K || C[j])
 *     return C[1..n]
 */
void Ratchet_CTR_BLAKE3_Enc(const uint8_t *K0, const uint8_t *P, const uint32_t *I, uint64_t S, size_t n, uint8_t *C) {
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    // K_seed <- AES.Enc(K0, S) (16 bytes output)
    uint8_t K_seed[FDE_BL];
    AES256_Enc(K0, S_block, K_seed);

    // K (32 bytes state for BLAKE3 output / AES-256 key)
    uint8_t K[32];
    memset(K, 0, 32);
    memcpy(K, K_seed, FDE_BL); // Initialize K with initial seed

    for (size_t j = 0; j < n; j++) {
        const uint8_t *P_j = P + (j * FDE_BL);
        uint8_t *C_j = C + (j * FDE_BL);

        uint8_t I_block[FDE_BL];
        pack_index(I[j], I_block);

        // AES.Enc(K, I[j])
        uint8_t keystream[FDE_BL];
        AES256_Enc(K, I_block, keystream);

        // C[j] <- P[j] ^ keystream
        xor_16bytes(C_j, P_j, keystream);

        // K <- BLAKE3.hash(K || C[j])  (32 bytes key + 16 bytes ciphertext = 48 bytes input)
        blake3_hasher hasher;
        blake3_hasher_init(&hasher);
        blake3_hasher_update(&hasher, K, 32);
        blake3_hasher_update(&hasher, C_j, FDE_BL);
        blake3_hasher_finalize(&hasher, K, 32); // Updates K to new 32-byte hash
    }
}

/*
 * Ratchet_CTR_BLAKE3.Dec(K0, C[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         P[j] <- C[j] ^ AES.Enc(K, I[j])
 *         K <- BLAKE3.hash(K || C[j])
 *     return P[1..n]
 */
void Ratchet_CTR_BLAKE3_Dec(const uint8_t *K0, const uint8_t *C, const uint32_t *I, uint64_t S, size_t n, uint8_t *P) {
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    uint8_t K_seed[FDE_BL];
    AES256_Enc(K0, S_block, K_seed);

    uint8_t K[32];
    memset(K, 0, 32);
    memcpy(K, K_seed, FDE_BL);

    for (size_t j = 0; j < n; j++) {
        const uint8_t *C_j = C + (j * FDE_BL);
        uint8_t *P_j = P + (j * FDE_BL);

        uint8_t I_block[FDE_BL];
        pack_index(I[j], I_block);

        uint8_t keystream[FDE_BL];
        AES256_Enc(K, I_block, keystream);

        // P[j] <- C[j] ^ keystream
        xor_16bytes(P_j, C_j, keystream);

        // K <- BLAKE3.hash(K || C[j])
        blake3_hasher hasher;
        blake3_hasher_init(&hasher);
        blake3_hasher_update(&hasher, K, 32);
        blake3_hasher_update(&hasher, C_j, FDE_BL);
        blake3_hasher_finalize(&hasher, K, 32);
    }
}

// =====================================================================
// VARIANT 2: Ratchet_CTR_AES
// =====================================================================

/*
 * Ratchet_CTR_AES.Enc(K0, KG, P[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         C[j] <- P[j] ^ AES.Enc(K, I[j])
 *         K <- AES.Enc(KG, K ^ C[j])
 *     return C[1..n]
 */
void Ratchet_CTR_AES_Enc(const uint8_t *K0, const uint8_t *KG, const uint8_t *P, const uint32_t *I, uint64_t S, size_t n, uint8_t *C) {
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    uint8_t K[FDE_BL];
    AES256_Enc(K0, S_block, K); // K <- AES.Enc(K0, S)

    for (size_t j = 0; j < n; j++) {
        const uint8_t *P_j = P + (j * FDE_BL);
        uint8_t *C_j = C + (j * FDE_BL);

        uint8_t I_block[FDE_BL];
        pack_index(I[j], I_block);

        uint8_t keystream[FDE_BL];
        AES128_Enc(K, I_block, keystream);

        // C[j] <- P[j] ^ keystream
        xor_16bytes(C_j, P_j, keystream);

        // K <- AES.Enc(KG, K ^ C[j])
        uint8_t K_xor_C[FDE_BL];
        xor_16bytes(K_xor_C, K, C_j);
        AES256_Enc(KG, K_xor_C, K); // Advance ratchet state K
    }
}

/*
 * Ratchet_CTR_AES.Dec(K0, KG, C[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         P[j] <- C[j] ^ AES.Enc(K, I[j])
 *         K <- AES.Enc(KG, K ^ C[j])
 *     return P[1..n]
 */
void Ratchet_CTR_AES_Dec(const uint8_t *K0, const uint8_t *KG, const uint8_t *C, const uint32_t *I, uint64_t S, size_t n, uint8_t *P) {
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    uint8_t K[FDE_BL];
    AES256_Enc(K0, S_block, K);

    for (size_t j = 0; j < n; j++) {
        const uint8_t *C_j = C + (j * FDE_BL);
        uint8_t *P_j = P + (j * FDE_BL);

        uint8_t I_block[FDE_BL];
        pack_index(I[j], I_block);

        uint8_t keystream[FDE_BL];
        AES128_Enc(K, I_block, keystream);

        // P[j] <- C[j] ^ keystream
        xor_16bytes(P_j, C_j, keystream);

        // K <- AES.Enc(KG, K ^ C[j])
        uint8_t K_xor_C[FDE_BL];
        xor_16bytes(K_xor_C, K, C_j);
        AES256_Enc(KG, K_xor_C, K);
    }
}

// =====================================================================
// BENCHMARKING FRAMEWORK
// =====================================================================

double get_time_sec() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

void run_benchmark(size_t sector_size_bytes, int iterations) {
    size_t n = sector_size_bytes / FDE_BL;

    uint8_t K0[FDE_KL], KG[FDE_KL];
    uint8_t *P = malloc(sector_size_bytes);
    uint8_t *C = malloc(sector_size_bytes);
    uint8_t *Decrypted_P = malloc(sector_size_bytes);
    uint32_t *I = malloc(n * sizeof(uint32_t));
    uint64_t S = 9999;

    memset(K0, 0x11, FDE_KL);
    memset(KG, 0x22, FDE_KL);
    memset(P, 0x55, sector_size_bytes);
    for (size_t j = 0; j < n; j++) I[j] = (uint32_t)(j + 1);

    printf("--- Benchmarking Sector Size: %zu bytes (%zu blocks) | %d Iterations ---\n", sector_size_bytes, n, iterations);

    // 1. Correctness & Speed Test: BLAKE3 Ratchet
    Ratchet_CTR_BLAKE3_Enc(K0, P, I, S, n, C);
    Ratchet_CTR_BLAKE3_Dec(K0, C, I, S, n, Decrypted_P);
    if (memcmp(P, Decrypted_P, sector_size_bytes) != 0) {
        printf("ERROR: BLAKE3 Decryption check failed!\n");
        return;
    }

    double start_time = get_time_sec();
    for (int i = 0; i < iterations; i++) {
        Ratchet_CTR_BLAKE3_Enc(K0, P, I, S, n, C);
    }
    double elapsed_b3 = get_time_sec() - start_time;
    double mb_s_b3 = ((double)(sector_size_bytes * iterations) / (1024.0 * 1024.0)) / elapsed_b3;
    printf("[C1 - BLAKE3] Elapsed Time: %.6f s | Throughput: %.2f MB/s\n", elapsed_b3, mb_s_b3);

    // 2. Correctness & Speed Test: AES Ratchet
    Ratchet_CTR_AES_Enc(K0, KG, P, I, S, n, C);
    Ratchet_CTR_AES_Dec(K0, KG, C, I, S, n, Decrypted_P);
    if (memcmp(P, Decrypted_P, sector_size_bytes) != 0) {
        printf("ERROR: AES Decryption check failed!\n");
        return;
    }

    start_time = get_time_sec();
    for (int i = 0; i < iterations; i++) {
        Ratchet_CTR_AES_Enc(K0, KG, P, I, S, n, C);
    }
    double elapsed_aes = get_time_sec() - start_time;
    double mb_s_aes = ((double)(sector_size_bytes * iterations) / (1024.0 * 1024.0)) / elapsed_aes;
    printf("[C1 - AES   ] Elapsed Time: %.6f s | Throughput: %.2f MB/s\n\n", elapsed_aes, mb_s_aes);

    free(P);
    free(C);
    free(Decrypted_P);
    free(I);
}

int main() {
    printf("=== FDE Scheme C1 (CTR Ratcheting) Speed Test ===\n\n");

    int iterations = 10000;

    run_benchmark(512, iterations);
    run_benchmark(4096, iterations);

    return 0;
}