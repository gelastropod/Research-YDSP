#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <openssl/evp.h>

#define FDE_KL 32  // Master key length (256-bit / 32 bytes)
#define FDE_BL 16  // AES Block length (128-bit / 16 bytes)

// =====================================================================
// AES SINGLE-BLOCK PRIMITIVES
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

// AES-128 Encryption (16-byte Key, 16-byte input/output block)
void AES128_Enc(const uint8_t *key_16B, const uint8_t *in_16B, uint8_t *out_16B) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_128_ecb(), NULL, key_16B, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    int outlen;
    EVP_EncryptUpdate(ctx, out_16B, &outlen, in_16B, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// Helper: Bitwise XOR of two 16-byte blocks
void xor_16bytes(uint8_t *out, const uint8_t *a, const uint8_t *b) {
    for (int i = 0; i < FDE_BL; i++) {
        out[i] = a[i] ^ b[i];
    }
}

// Helper: Pack uint32 block index into a zero-padded 16-byte block
void pack_index(uint32_t index_val, uint8_t *block) {
    memset(block, 0, FDE_BL);
    memcpy(block, &index_val, sizeof(index_val));
}

// =====================================================================
// SCHEME C1 (CTR RATCHET - AES VARIANT)
// =====================================================================

/*
 * Ratchet_CTR_AES.Enc(K0, KG, P[1..n], I[1..n], S):
 *     K <- AES.Enc(K0, S)
 *     for j = 1 to n:
 *         C[j] <- P[j] ^ AES.Enc(K, I[j])
 *         K <- AES.Enc(KG, K ^ C[j])
 *     return C[1..n]
 */
void Ratchet_CTR_AES_Enc(const uint8_t *K0, const uint8_t *KG, 
                        const uint8_t *P, const uint32_t *I, 
                        uint64_t S, size_t n, uint8_t *C) {
    // 1. Pack Sector S into 16-byte block
    uint8_t S_block[FDE_BL] = {0};
    memcpy(S_block, &S, sizeof(S));

    // 2. K <- AES256.Enc(K0, S)  (Initial 16-byte state key K)
    uint8_t K[FDE_BL];
    AES256_Enc(K0, S_block, K);

    // 3. Ratchet Loop
    for (size_t j = 0; j < n; j++) {
        const uint8_t *P_j = P + (j * FDE_BL);
        uint8_t *C_j = C + (j * FDE_BL);

        uint8_t I_block[FDE_BL];
        pack_index(I[j], I_block);

        // Keystream <- AES128.Enc(K, I[j])
        uint8_t keystream[FDE_BL];
        AES128_Enc(K, I_block, keystream);

        // C[j] <- P[j] ^ Keystream
        xor_16bytes(C_j, P_j, keystream);

        // State update: K <- AES256.Enc(KG, K ^ C[j])
        uint8_t K_xor_C[FDE_BL];
        xor_16bytes(K_xor_C, K, C_j);
        AES256_Enc(KG, K_xor_C, K);
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
void Ratchet_CTR_AES_Dec(const uint8_t *K0, const uint8_t *KG, 
                        const uint8_t *C, const uint32_t *I, 
                        uint64_t S, size_t n, uint8_t *P) {
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

        // P[j] <- C[j] ^ Keystream
        xor_16bytes(P_j, C_j, keystream);

        // State update: K <- AES256.Enc(KG, K ^ C[j])
        uint8_t K_xor_C[FDE_BL];
        xor_16bytes(K_xor_C, K, C_j);
        AES256_Enc(KG, K_xor_C, K);
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

    // 1. Correctness Verification
    Ratchet_CTR_AES_Enc(K0, KG, P, I, S, n, C);
    Ratchet_CTR_AES_Dec(K0, KG, C, I, S, n, Decrypted_P);

    if (memcmp(P, Decrypted_P, sector_size_bytes) != 0) {
        printf("[FAIL] Sector Size %zu: Decrypted text does not match Plaintext!\n", sector_size_bytes);
        free(P); free(C); free(Decrypted_P); free(I);
        return;
    }

    // 2. Performance Benchmark
    double start_time = get_time_sec();
    for (int i = 0; i < iterations; i++) {
        Ratchet_CTR_AES_Enc(K0, KG, P, I, S, n, C);
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
    printf("=== Scheme C1 (CTR Ratchet - Pure AES Variant) ===\n\n");

    int iterations = 10000;

    run_benchmark(512, iterations);
    run_benchmark(4096, iterations);

    return 0;
}