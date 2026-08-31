#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <openssl/evp.h>

#define FDE_KL 32  // 256-bit key (32 bytes)
#define FDE_BL 16  // 128-bit block (16 bytes)
#define FDE_IL 4   // 32-bit index (4 bytes)
#define FDE_SL 8   // 64-bit sector number (8 bytes)

// =====================================================================
// AES SINGLE-BLOCK HELPERS (To make the ECB loop match pseudocode)
// =====================================================================

// AES.Enc(K, P_block)
void AES_Enc(const uint8_t *K, const uint8_t *P_block, uint8_t *C_block) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, K, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0); // No padding, exact block size
    int outlen;
    EVP_EncryptUpdate(ctx, C_block, &outlen, P_block, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// AES.Dec(K, C_block)
void AES_Dec(const uint8_t *K, const uint8_t *C_block, uint8_t *P_block) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_DecryptInit_ex(ctx, EVP_aes_256_ecb(), NULL, K, NULL);
    EVP_CIPHER_CTX_set_padding(ctx, 0); 
    int outlen;
    EVP_DecryptUpdate(ctx, P_block, &outlen, C_block, FDE_BL);
    EVP_CIPHER_CTX_free(ctx);
}

// =====================================================================
// PSEUDOCODE IMPLEMENTATION: Scheme A (AES-ECB)
// =====================================================================

/*
 * ECB.Enc(K, P[1..n], I[1..n], S):
 *     for j = 1 to n:
 *         C[j] <- AES.Enc(K, P[j])
 *     return C[1..n]
 */
void ECB_Enc(const uint8_t *K, const uint8_t *P, const uint32_t *I, uint64_t S, size_t n, uint8_t *C) {
    // In C, arrays are 0-indexed, so we loop from 0 to n-1
    for (size_t j = 0; j < n; j++) {
        // Find the start memory address of block 'j'
        const uint8_t *P_j = P + (j * FDE_BL);
        uint8_t *C_j = C + (j * FDE_BL);
        
        // C[j] <- AES.Enc(K, P[j])
        AES_Enc(K, P_j, C_j);
    }
}

/*
 * ECB.Dec(K, C[1..n], I[1..n], S):
 *     for j = 1 to n:
 *         P[j] <- AES.Dec(K, C[j])
 *     return P[1..n]
 */
void ECB_Dec(const uint8_t *K, const uint8_t *C, const uint32_t *I, uint64_t S, size_t n, uint8_t *P) {
    for (size_t j = 0; j < n; j++) {
        const uint8_t *C_j = C + (j * FDE_BL);
        uint8_t *P_j = P + (j * FDE_BL);
        
        // P[j] <- AES.Dec(K, C[j])
        AES_Dec(K, C_j, P_j);
    }
}

// =====================================================================
// BENCHMARKING FRAMEWORK
// =====================================================================

// Helper to get time in seconds from OS monotonic clock
double get_time_sec() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

void run_benchmark(size_t sector_size_bytes, int iterations) {
    size_t n = sector_size_bytes / FDE_BL; // Number of blocks (n)
    
    // Allocate memory for Key, Data, and Indices
    uint8_t K[FDE_KL];
    uint8_t *P = malloc(sector_size_bytes);
    uint8_t *C = malloc(sector_size_bytes);
    uint32_t *I = malloc(n * FDE_IL);
    uint64_t S = 9999; // Arbitrary sector number

    // Fill with arbitrary test data
    memset(K, 0xAA, FDE_KL);
    memset(P, 0xBB, sector_size_bytes);
    for(size_t i = 0; i < n; i++) I[i] = i;

    printf("Benchmarking AES-ECB: Sector Size = %zu bytes (%zu blocks) | Iterations = %d\n", sector_size_bytes, n, iterations);

    // Warm-up run (ensure correctness)
    ECB_Enc(K, P, I, S, n, C);
    
    // Timer Start
    double start_time = get_time_sec();
    
    for (int i = 0; i < iterations; i++) {
        ECB_Enc(K, P, I, S, n, C);
    }
    
    // Timer End
    double end_time = get_time_sec();
    double elapsed = end_time - start_time;
    
    // Calculate Speed
    double total_mb_processed = (double)(sector_size_bytes * iterations) / (1024.0 * 1024.0);
    double mb_per_sec = total_mb_processed / elapsed;

    printf("  Elapsed Time: %.6f seconds\n", elapsed);
    printf("  Throughput:   %.2f MB/s\n\n", mb_per_sec);

    free(P);
    free(C);
    free(I);
}

int main() {
    printf("=== FDE Scheme A (AES-ECB) Speed Test ===\n\n");

    int iterations = 10000; // Run 10,000 times to get a measurable time block

    // Benchmark 512-byte sector
    run_benchmark(512, iterations);

    // Benchmark 4096-byte sector
    run_benchmark(4096, iterations);

    return 0;
}