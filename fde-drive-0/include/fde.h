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

#define FDE_XEX_HMAC_INSTANCES(X) \
    X(SHA256,   "xex-hmac-sha256",   "Ratchet-XEX-HMAC-SHA256",   "SHA2-256") \
    X(SHA3_256, "xex-hmac-sha3-256", "Ratchet-XEX-HMAC-SHA3-256", "SHA3-256") \
    X(SHA2_224, "xex-hmac-sha2-224", "Ratchet-XEX-HMAC-SHA2-224", "SHA2-224") \
    X(SHA3_224, "xex-hmac-sha3-224", "Ratchet-XEX-HMAC-SHA3-224", "SHA3-224") \
    X(BLAKE2S_256, "xex-hmac-blake2s-256", "Ratchet-XEX-HMAC-BLAKE2S-256", "BLAKE2S-256") \
    X(SM3, "xex-hmac-sm3", "Ratchet-XEX-HMAC-SM3", "SM3") \
    X(RIPEMD160, "xex-hmac-ripemd160", "Ratchet-XEX-HMAC-RIPEMD160", "RIPEMD-160")

typedef enum {
    FDE_ECB = 0,
    FDE_XTS = 1,
    FDE_RATCHET_CTR_AES = 2,
    FDE_RATCHET_CTR_BLAKE3 = 3,
    FDE_RATCHET_CBC_AES = 4,
    FDE_RATCHET_CBC_BLAKE3 = 5,
	FDE_RATCHET_XEX_SHA3 = 6,
    FDE_RATCHET_XEX_BLAKE2B = 7,
    FDE_RATCHET_XEX_BLAKE3 = 8,
    FDE_RATCHET_XEX_SIPHASH = 9,
    FDE_RATCHET_XEX_KMAC = 10,
    FDE_RATCHET_XEX_BLAKE2S = 11,
    FDE_RATCHET_XEX_CMAC = 12,
    FDE_RATCHET_XEX_GHASH = 13,
#define FDE_XEX_HMAC_SCHEME_ENUM(ID, NAME, DISPLAY, DIGEST) \
    FDE_RATCHET_XEX_HMAC_##ID,
    FDE_XEX_HMAC_INSTANCES(FDE_XEX_HMAC_SCHEME_ENUM)
#undef FDE_XEX_HMAC_SCHEME_ENUM
    FDE_SCHEME_COUNT
} fde_scheme;

enum {
#define FDE_XEX_HMAC_INDEX(ID, NAME, DISPLAY, DIGEST) FDE_XEX_HMAC_IDX_##ID,
    FDE_XEX_HMAC_INSTANCES(FDE_XEX_HMAC_INDEX)
#undef FDE_XEX_HMAC_INDEX
    FDE_XEX_HMAC_COUNT
};

typedef struct {
    uint8_t ecb_key[FDE_MASTER_KEY_BYTES];
	uint8_t hash_key[FDE_MASTER_KEY_BYTES];
    uint8_t xts_k1[FDE_MASTER_KEY_BYTES];
    uint8_t xts_k2[FDE_MASTER_KEY_BYTES];
    uint8_t ratchet_key[FDE_MASTER_KEY_BYTES];
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

/* A 48-byte-context -> 16-byte mask function for the XEX ratchets.
 * Keyed variants read their key material from worker->keys.
 * Returns 0 on success, -1 on failure. */
typedef int (*fde_xex_hash_fn)(fde_worker *worker, const uint8_t *input,
                               size_t input_len, uint8_t out[16]);

/* Map an XEX scheme to its mask hash; NULL for non-XEX schemes. Exposed so
 * tests and benchmarks can time mask functions in isolation. */
fde_xex_hash_fn fde_xex_hash_for_scheme(fde_scheme scheme);

int fde_ratchet_xex_unkeyed_update(fde_worker *worker, uint8_t tweak[16],
                                const uint8_t sector[16],
                                const uint8_t index[16],
                                const uint8_t state[16]);
int fde_ratchet_xex_keyed_update(fde_worker *worker, uint8_t tweak[16],
                                 const uint8_t sector[16],
                                 const uint8_t index[16],
                                 const uint8_t state[16],
                                 fde_xex_hash_fn hash_fn);

/* GHASH in GCM input format (SP 800-38D §7.1): hashes
 * aad ‖ ciphertext ‖ [len(aad)]64 ‖ [len(ciphertext)]64 with bit lengths
 * encoded big-endian. Exposed for the GCM cross-check in test_fde; the XEX
 * mask uses aad = NULL and the 48-byte context as ciphertext. */
int fde_ghash(const uint8_t H[16], const uint8_t *aad, size_t aad_len,
              const uint8_t *ciphertext, size_t ciphertext_len,
              uint8_t out[16]);

/* Exposed only for independent XTS correctness tests. */
void fde_xts_mul_alpha(uint8_t tweak[16]);

#ifdef __cplusplus
}
#endif

#endif
