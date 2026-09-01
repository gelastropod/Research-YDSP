#ifndef FDE_H
#define FDE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FDE_BLOCK_BYTES 16u
#define FDE_MASTER_KEY_BYTES 32u
#define FDE_BLAKE3_STATE_BYTES 32u

typedef enum {
    FDE_ECB = 0,
    FDE_XTS = 1,
    FDE_RATCHET_CTR_AES = 2,
    FDE_RATCHET_CTR_BLAKE3 = 3,
    FDE_RATCHET_CBC_AES = 4,
    FDE_RATCHET_CBC_BLAKE3 = 5,
    FDE_SCHEME_COUNT = 6
} fde_scheme;

typedef struct {
    uint8_t ecb_key[FDE_MASTER_KEY_BYTES];
    uint8_t xts_k1[FDE_MASTER_KEY_BYTES];
    uint8_t xts_k2[FDE_MASTER_KEY_BYTES];
    uint8_t ratchet_k0[FDE_MASTER_KEY_BYTES];
    uint8_t ratchet_kg[FDE_MASTER_KEY_BYTES];
} fde_keys;

typedef struct {
    uint64_t seed_ns;
    uint64_t data_ns;
    uint64_t evolution_ns;
} fde_profile;

typedef struct fde_worker fde_worker;

const char *fde_scheme_name(fde_scheme scheme);
int fde_scheme_uses_indices(fde_scheme scheme);
int fde_scheme_is_ratchet(fde_scheme scheme);

void fde_default_keys(fde_keys *keys);
fde_worker *fde_worker_new(const fde_keys *keys);
void fde_worker_free(fde_worker *worker);

/*
 * Manual Task 9 implementation. XTS uses the efficient sequential recurrence
 * when indices are consecutive, and the indexed formula otherwise.
 */
int fde_encrypt(fde_worker *worker, fde_scheme scheme,
                const uint8_t *plaintext, const uint32_t *indices,
                uint64_t sector, size_t blocks, uint8_t *ciphertext,
                fde_profile *profile);

int fde_decrypt(fde_worker *worker, fde_scheme scheme,
                const uint8_t *ciphertext, const uint32_t *indices,
                uint64_t sector, size_t blocks, uint8_t *plaintext,
                fde_profile *profile);

/* Exact indexed XTS formula T_j = E_K2(S) * alpha^I[j]. */
int fde_xts_encrypt_indexed(fde_worker *worker, const uint8_t *plaintext,
                            const uint32_t *indices, uint64_t sector,
                            size_t blocks, uint8_t *ciphertext,
                            fde_profile *profile);

int fde_xts_decrypt_indexed(fde_worker *worker, const uint8_t *ciphertext,
                            const uint32_t *indices, uint64_t sector,
                            size_t blocks, uint8_t *plaintext,
                            fde_profile *profile);

/* Production OpenSSL XTS reference for one complete sequential data unit. */
int fde_xts_openssl_encrypt(fde_worker *worker, const uint8_t *plaintext,
                            uint64_t sector, size_t bytes,
                            uint8_t *ciphertext);

int fde_xts_openssl_decrypt(fde_worker *worker, const uint8_t *ciphertext,
                            uint64_t sector, size_t bytes,
                            uint8_t *plaintext);

/* Recover one zero-based target block. Ratchets walk the preceding state chain. */
int fde_decrypt_target(fde_worker *worker, fde_scheme scheme,
                       const uint8_t *sector_ciphertext,
                       const uint32_t *indices, uint64_t sector,
                       size_t blocks, size_t target, uint8_t plaintext[16]);

/* Isolated Task 9 state-transition controls used for RQ1/RQ3. */
int fde_ratchet_aes_update(fde_worker *worker, uint8_t state[16],
                           const uint8_t ciphertext[16]);
void fde_ratchet_blake3_update(uint8_t state[32],
                               const uint8_t ciphertext[16]);

/* Exposed only for independent XTS correctness tests. */
void fde_xts_mul_alpha(uint8_t tweak[16]);

#ifdef __cplusplus
}
#endif

#endif
