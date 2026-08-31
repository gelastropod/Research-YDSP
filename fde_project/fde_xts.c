#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <openssl/evp.h>

#define FDE_KL 32  // 256-bit Key length (32 bytes per subkey K1, K2)
#define FDE_BL 16  // 128-bit Block length (16 bytes)
#define FDE_IL 4   // Index length (4 bytes)
#define FDE_SL 8   // Sector length (8 bytes)

// =====================================================================
// AES SINGLE-BLOCK HELPERS
// =====================================================================

void AES_Enc(const uint8_t *K, const uint8_t *P_block, uint8_t *C_block) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, K, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_EncryptUpdate(ctx, C_block, &outlen, P_block, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

void AES_Dec(const uint8_t *K, const uint8_t *C_block, uint8_t *P_block) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_DecryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, K, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_DecryptUpdate(ctx, P_block, &outlen, C_block, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// Helper: Bitwise XOR of two 16-byte blocks
void xor_16bytes(uint8_t *out, const uint8_t *a, const uint8_t *b) {
    for (int i = 0; i < FDE_BL; i++) {
        out[i] = a[i] ^ b[i];
    }
}

// =====================================================================
// PSEUDOCODE HELPER: MUL_ALPHA (Galois Field Multiplication)
// =====================================================================

/*
 * MUL_ALPHA(x):
 *     p_128 <- 0x87
 *     if most_significant_bit(x) == 0:
 *         return x << 1
 *     else
 *         return (x << 1) ^ p_128
 */
void MUL_ALPHA(uint8_t *x) {
    uint8_t p_128 = 0x87;
    // Check most significant bit (bit 7 of byte 0)
    uint8_t msb = (x[0] & 0x80) ? 1 : 0;

    // Shift 128-bit array left by 1 bit across all 16 bytes
    uint8_t carry = 0;
    for (int i = FDE_BL - 1; i >= 0; i--) {
        uint8_t next_carry = (x[i] & 0x80) ? 1 : 0;
        x[i] = (x[i] << 1) | carry;
        carry = next_carry;
    }

    // XOR irreducible polynomial 0x87 onto the last byte if MSB was set
    if (msb) {
        x[FDE_BL - 1] ^= p_128;
    }
}

// =====================================================================
// PSEUDOCODE IMPLEMENTATION: Scheme B (AES-XTS)
// =====================================================================

/*
 * XTS.Enc(K1||K2, P[1..n], I[1..n], S):
 *     T0 <- AES(K2, S)
 *     for j = 1 to n:
 *         T <- T0
 *         for k = 1 to I[j]:
 *              T <- MUL_ALPHA(T)
 *         C[j] <- AES.Enc(K1, P[j] ^ T) ^ T
 *     return C[1..n]
 */
void XTS_Enc(const uint8_t *K1, const uint8_t *K2, const uint8_t *P, const uint32_t *I, uint64_t S, size_t n, uint8_t *C) {
    // Pack sector number S into 16-byte block
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    // T0 <- AES(K2, S)
    uint8_t T0[FDE_BL];
    AES_Enc(K2, S_block, T0);

    for (size_t j = 0; j < n; j++) {
        uint8_t T[FDE_BL];
        memcpy(T, T0, FDE_BL); // T <- T0

        // for k = 1 to I[j]: T <- MUL_ALPHA(T)
        for (uint32_t k = 0; k < I[j]; k++) {
            MUL_ALPHA(T);
        }

        const uint8_t *P_j = P + (j * FDE_BL);
        uint8_t *C_j = C + (j * FDE_BL);

        // C[j] <- AES.Enc(K1, P[j] ^ T) ^ T
        uint8_t P_xor_T[FDE_BL];
        uint8_t encrypted_block[FDE_BL];

        xor_16bytes(P_xor_T, P_j, T);            // P[j] ^ T
        AES_Enc(K1, P_xor_T, encrypted_block);   // AES.Enc(K1, ...)
        xor_16bytes(C_j, encrypted_block, T);    // ... ^ T
    }
}

/*
 * XTS.Dec(K1||K2, C[1..n], I[1..n], S):
 *     T0 <- AES(K2, S)
 *     for j = 1 to n:
 *         T <- T0
 *         for k = 1 to I[j]:
 *              T <- MUL_ALPHA(T)
 *         P[j] <- AES.Dec(K1, C[j] ^ T) ^ T
 *     return P[1..n]
 */
void XTS_Dec(const uint8_t *K1, const uint8_t *K2, const uint8_t *C, const uint32_t *I, uint64_t S, size_t n, uint8_t *P) {
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    uint8_t T0[FDE_BL];
    AES_Enc(K2, S_block, T0);

    for (size_t j = 0; j < n; j++) {
        uint8_t T[FDE_BL];
        memcpy(T, T0, FDE_BL);

        for (uint32_t k = 0; k < I[j]; k++) {
            MUL_ALPHA(T);
        }

        const uint8_t *C_j = C + (j * FDE_BL);
        uint8_t *P_j = P + (j * FDE_BL);

        // P[j] <- AES.Dec(K1, C[j] ^ T) ^ T
        uint8_t C_xor_T[FDE_BL];
        uint8_t decrypted_block[FDE_BL];

        xor_16bytes(C_xor_T, C_j, T);            // C[j] ^ T
        AES_Dec(K1, C_xor_T, decrypted_block);   // AES.Dec(K1, ...)
        xor_16bytes(P_j, decrypted_block, T);    // ... ^ T
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

    uint8_t K1[FDE_KL], K2[FDE_KL];
    uint8_t *P = malloc(sector_size_bytes);
    uint8_t *C = malloc(sector_size_bytes);
    uint8_t *Decrypted_P = malloc(sector_size_bytes);
    uint32_t *I = malloc(n * sizeof(uint32_t));
    uint64_t S = 9999;

    memset(K1, 0xAA, FDE_KL);
    memset(K2, 0xBB, FDE_KL);
    memset(P, 0xCC, sector_size_bytes);
    for (size_t j = 0; j < n; j++) I[j] = (uint32_t)(j + 1); // Set index values

    // Correctness Verification Test
    XTS_Enc(K1, K2, P, I, S, n, C);
    XTS_Dec(K1, K2, C, I, S, n, Decrypted_P);
    if (memcmp(P, Decrypted_P, sector_size_bytes) != 0) {
        printf("ERROR: Decryption correctness check failed!\n");
        return;
    }

    printf("Benchmarking AES-XTS: Sector Size = %zu bytes (%zu blocks) | Iterations = %d\n", sector_size_bytes, n, iterations);

    double start_time = get_time_sec();
    for (int i = 0; i < iterations; i++) {
        XTS_Enc(K1, K2, P, I, S, n, C);
    }
    double end_time = get_time_sec();

    double elapsed = end_time - start_time;
    double total_mb_processed = (double)(sector_size_bytes * iterations) / (1024.0 * 1024.0);
    double mb_per_sec = total_mb_processed / elapsed;

    printf("  Elapsed Time: %.6f seconds\n", elapsed);
    printf("  Throughput:   %.2f MB/s\n\n", mb_per_sec);

    free(P);
    free(C);
    free(Decrypted_P);
    free(I);
}

int main() {
    printf("=== FDE Scheme B (AES-XTS) Speed Test ===\n\n");

    int iterations = 10000;

    run_benchmark(512, iterations);
    run_benchmark(4096, iterations);

    return 0;
}