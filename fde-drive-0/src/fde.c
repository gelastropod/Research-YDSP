#define _POSIX_C_SOURCE 200809L

#include "fde.h"
#include "blake3.h"

#include <openssl/evp.h>

#include <stdlib.h>
#include <string.h>
#include <time.h>

struct fde_worker {
    fde_keys keys;
    uint8_t xts_combined_key[2 * FDE_MASTER_KEY_BYTES];
    EVP_CIPHER_CTX *ecb_enc;
    EVP_CIPHER_CTX *ecb_dec;
    EVP_CIPHER_CTX *xts_data_enc;
    EVP_CIPHER_CTX *xts_data_dec;
    EVP_CIPHER_CTX *xts_tweak_enc;
    EVP_CIPHER_CTX *seed_enc;
    EVP_CIPHER_CTX *ratchet_enc;
    EVP_CIPHER_CTX *dynamic128_enc;
    EVP_CIPHER_CTX *dynamic128_dec;
    EVP_CIPHER_CTX *dynamic256_enc;
    EVP_CIPHER_CTX *dynamic256_dec;
    EVP_CIPHER_CTX *openssl_xts_enc;
    EVP_CIPHER_CTX *openssl_xts_dec;
};

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static void profile_reset(fde_profile *profile) {
    if (profile != NULL) {
        memset(profile, 0, sizeof(*profile));
    }
}

static void profile_add(uint64_t *field, uint64_t start) {
    if (field != NULL) {
        *field += now_ns() - start;
    }
}

static void encode_u64_le(uint64_t value, uint8_t out[16]) {
    memset(out, 0, 16);
    for (size_t i = 0; i < 8; ++i) {
        out[i] = (uint8_t)(value >> (8u * i));
    }
}

static void encode_u32_le(uint32_t value, uint8_t out[16]) {
    memset(out, 0, 16);
    for (size_t i = 0; i < 4; ++i) {
        out[i] = (uint8_t)(value >> (8u * i));
    }
}

static void xor_block(uint8_t out[16], const uint8_t a[16],
                      const uint8_t b[16]) {
    for (size_t i = 0; i < 16; ++i) {
        out[i] = (uint8_t)(a[i] ^ b[i]);
    }
}

static EVP_CIPHER_CTX *new_cipher_ctx(const EVP_CIPHER *cipher,
                                      const uint8_t *key, int encrypt) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int ok;
    if (ctx == NULL) {
        return NULL;
    }
    if (encrypt) {
        ok = EVP_EncryptInit_ex(ctx, cipher, NULL, key, NULL);
        if (ok == 1) {
            ok = EVP_CIPHER_CTX_set_padding(ctx, 0);
        }
    } else {
        ok = EVP_DecryptInit_ex(ctx, cipher, NULL, key, NULL);
        if (ok == 1) {
            ok = EVP_CIPHER_CTX_set_padding(ctx, 0);
        }
    }
    if (ok != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return NULL;
    }
    return ctx;
}

static int fixed_block(EVP_CIPHER_CTX *ctx, int encrypt,
                       const uint8_t in[16], uint8_t out[16]) {
    int written = 0;
    int ok = encrypt ? EVP_EncryptUpdate(ctx, out, &written, in, 16)
                     : EVP_DecryptUpdate(ctx, out, &written, in, 16);
    return ok == 1 && written == 16 ? 0 : -1;
}

static int dynamic_block(EVP_CIPHER_CTX *ctx, int encrypt,
                         const uint8_t *key, const uint8_t in[16],
                         uint8_t out[16]) {
    int written = 0;
    int ok;
    if (encrypt) {
        ok = EVP_EncryptInit_ex(ctx, NULL, NULL, key, NULL);
        if (ok == 1) {
            ok = EVP_EncryptUpdate(ctx, out, &written, in, 16);
        }
    } else {
        ok = EVP_DecryptInit_ex(ctx, NULL, NULL, key, NULL);
        if (ok == 1) {
            ok = EVP_DecryptUpdate(ctx, out, &written, in, 16);
        }
    }
    return ok == 1 && written == 16 ? 0 : -1;
}

const char *fde_scheme_name(fde_scheme scheme) {
    static const char *const names[FDE_SCHEME_COUNT] = {
        "AES-ECB",
        "AES-XTS-manual",
        "Ratchet-CTR-AES",
        "Ratchet-CTR-BLAKE3",
        "Ratchet-CBC-AES",
        "Ratchet-CBC-BLAKE3"
    };
    return (scheme >= 0 && scheme < FDE_SCHEME_COUNT) ? names[scheme]
                                                       : "unknown";
}

int fde_scheme_uses_indices(fde_scheme scheme) {
    return scheme == FDE_XTS || scheme == FDE_RATCHET_CTR_AES ||
           scheme == FDE_RATCHET_CTR_BLAKE3;
}

int fde_scheme_is_ratchet(fde_scheme scheme) {
    return scheme >= FDE_RATCHET_CTR_AES && scheme < FDE_SCHEME_COUNT;
}

void fde_default_keys(fde_keys *keys) {
    if (keys == NULL) {
        return;
    }
    for (size_t i = 0; i < FDE_MASTER_KEY_BYTES; ++i) {
        keys->ecb_key[i] = (uint8_t)(0x10u + i);
        keys->xts_k1[i] = (uint8_t)(0x30u + i);
        keys->xts_k2[i] = (uint8_t)(0x60u + i);
        keys->ratchet_k0[i] = (uint8_t)(0x90u + i);
        keys->ratchet_kg[i] = (uint8_t)(0xc0u + i);
    }
}

fde_worker *fde_worker_new(const fde_keys *keys) {
    static const uint8_t zero128[16] = {0};
    static const uint8_t zero256[32] = {0};
    fde_worker *worker;
    if (keys == NULL) {
        return NULL;
    }
    worker = calloc(1, sizeof(*worker));
    if (worker == NULL) {
        return NULL;
    }
    worker->keys = *keys;
    memcpy(worker->xts_combined_key, keys->xts_k1, FDE_MASTER_KEY_BYTES);
    memcpy(worker->xts_combined_key + FDE_MASTER_KEY_BYTES, keys->xts_k2,
           FDE_MASTER_KEY_BYTES);

    worker->ecb_enc = new_cipher_ctx(EVP_aes_256_ecb(), keys->ecb_key, 1);
    worker->ecb_dec = new_cipher_ctx(EVP_aes_256_ecb(), keys->ecb_key, 0);
    worker->xts_data_enc = new_cipher_ctx(EVP_aes_256_ecb(), keys->xts_k1, 1);
    worker->xts_data_dec = new_cipher_ctx(EVP_aes_256_ecb(), keys->xts_k1, 0);
    worker->xts_tweak_enc = new_cipher_ctx(EVP_aes_256_ecb(), keys->xts_k2, 1);
    worker->seed_enc = new_cipher_ctx(EVP_aes_256_ecb(), keys->ratchet_k0, 1);
    worker->ratchet_enc = new_cipher_ctx(EVP_aes_256_ecb(), keys->ratchet_kg, 1);
    worker->dynamic128_enc = new_cipher_ctx(EVP_aes_128_ecb(), zero128, 1);
    worker->dynamic128_dec = new_cipher_ctx(EVP_aes_128_ecb(), zero128, 0);
    worker->dynamic256_enc = new_cipher_ctx(EVP_aes_256_ecb(), zero256, 1);
    worker->dynamic256_dec = new_cipher_ctx(EVP_aes_256_ecb(), zero256, 0);
    worker->openssl_xts_enc = EVP_CIPHER_CTX_new();
    worker->openssl_xts_dec = EVP_CIPHER_CTX_new();

    if (worker->ecb_enc == NULL || worker->ecb_dec == NULL ||
        worker->xts_data_enc == NULL || worker->xts_data_dec == NULL ||
        worker->xts_tweak_enc == NULL || worker->seed_enc == NULL ||
        worker->ratchet_enc == NULL || worker->dynamic128_enc == NULL ||
        worker->dynamic128_dec == NULL || worker->dynamic256_enc == NULL ||
        worker->dynamic256_dec == NULL || worker->openssl_xts_enc == NULL ||
        worker->openssl_xts_dec == NULL) {
        fde_worker_free(worker);
        return NULL;
    }
    return worker;
}

void fde_worker_free(fde_worker *worker) {
    if (worker == NULL) {
        return;
    }
    EVP_CIPHER_CTX_free(worker->ecb_enc);
    EVP_CIPHER_CTX_free(worker->ecb_dec);
    EVP_CIPHER_CTX_free(worker->xts_data_enc);
    EVP_CIPHER_CTX_free(worker->xts_data_dec);
    EVP_CIPHER_CTX_free(worker->xts_tweak_enc);
    EVP_CIPHER_CTX_free(worker->seed_enc);
    EVP_CIPHER_CTX_free(worker->ratchet_enc);
    EVP_CIPHER_CTX_free(worker->dynamic128_enc);
    EVP_CIPHER_CTX_free(worker->dynamic128_dec);
    EVP_CIPHER_CTX_free(worker->dynamic256_enc);
    EVP_CIPHER_CTX_free(worker->dynamic256_dec);
    EVP_CIPHER_CTX_free(worker->openssl_xts_enc);
    EVP_CIPHER_CTX_free(worker->openssl_xts_dec);
    free(worker);
}

/* IEEE XTS little-endian polynomial convention. */
void fde_xts_mul_alpha(uint8_t tweak[16]) {
    uint8_t carry = 0;
    for (size_t i = 0; i < 16; ++i) {
        uint8_t next = (uint8_t)(tweak[i] >> 7);
        tweak[i] = (uint8_t)((tweak[i] << 1) | carry);
        carry = next;
    }
    if (carry != 0) {
        tweak[0] ^= UINT8_C(0x87);
    }
}

static int seed_state(fde_worker *worker, uint64_t sector, uint8_t state[16]) {
    uint8_t encoded[16];
    encode_u64_le(sector, encoded);
    return fixed_block(worker->seed_enc, 1, encoded, state);
}

static int xts_seed(fde_worker *worker, uint64_t sector, uint8_t tweak[16]) {
    uint8_t encoded[16];
    encode_u64_le(sector, encoded);
    return fixed_block(worker->xts_tweak_enc, 1, encoded, tweak);
}

int fde_ratchet_aes_update(fde_worker *worker, uint8_t state[16],
                           const uint8_t ciphertext[16]) {
    uint8_t input[16];
    if (worker == NULL || state == NULL || ciphertext == NULL) {
        return -1;
    }
    xor_block(input, state, ciphertext);
    return fixed_block(worker->ratchet_enc, 1, input, state);
}

void fde_ratchet_blake3_update(uint8_t state[32],
                               const uint8_t ciphertext[16]) {
    blake3_hasher hasher;
    uint8_t input[48];
    memcpy(input, state, 32);
    memcpy(input + 32, ciphertext, 16);
    blake3_hasher_init(&hasher);
    blake3_hasher_update(&hasher, input, sizeof(input));
    blake3_hasher_finalize(&hasher, state, 32);
}

static int indices_are_consecutive(const uint32_t *indices, size_t blocks) {
    if (indices == NULL || blocks < 2) {
        return 1;
    }
    for (size_t i = 1; i < blocks; ++i) {
        if (indices[i] != indices[0] + (uint32_t)i) {
            return 0;
        }
    }
    return 1;
}

static uint32_t index_at(const uint32_t *indices, size_t j) {
    return indices == NULL ? (uint32_t)j : indices[j];
}

static int ecb_crypt(fde_worker *worker, int encrypt, const uint8_t *input,
                     size_t blocks, uint8_t *output, fde_profile *profile) {
    EVP_CIPHER_CTX *ctx = encrypt ? worker->ecb_enc : worker->ecb_dec;
    for (size_t j = 0; j < blocks; ++j) {
        uint64_t start = profile == NULL ? 0 : now_ns();
        if (fixed_block(ctx, encrypt, input + 16 * j, output + 16 * j) != 0) {
            return -1;
        }
        if (profile != NULL) {
            profile_add(&profile->data_ns, start);
        }
    }
    return 0;
}

static int xts_crypt(fde_worker *worker, int encrypt, const uint8_t *input,
                     const uint32_t *indices, uint64_t sector, size_t blocks,
                     uint8_t *output, fde_profile *profile, int force_indexed) {
    uint8_t t0[16];
    int consecutive = !force_indexed && indices_are_consecutive(indices, blocks);
    uint64_t start = profile == NULL ? 0 : now_ns();
    if (xts_seed(worker, sector, t0) != 0) {
        return -1;
    }
    if (profile != NULL) {
        profile_add(&profile->seed_ns, start);
    }

    if (consecutive) {
        uint8_t tweak[16];
        memcpy(tweak, t0, 16);
        start = profile == NULL ? 0 : now_ns();
        for (uint32_t k = 0; k < index_at(indices, 0); ++k) {
            fde_xts_mul_alpha(tweak);
        }
        if (profile != NULL) {
            profile_add(&profile->evolution_ns, start);
        }
        for (size_t j = 0; j < blocks; ++j) {
            uint8_t masked[16];
            uint8_t transformed[16];
            start = profile == NULL ? 0 : now_ns();
            xor_block(masked, input + 16 * j, tweak);
            if (fixed_block(encrypt ? worker->xts_data_enc : worker->xts_data_dec,
                            encrypt, masked, transformed) != 0) {
                return -1;
            }
            xor_block(output + 16 * j, transformed, tweak);
            if (profile != NULL) {
                profile_add(&profile->data_ns, start);
            }
            if (j + 1 < blocks) {
                start = profile == NULL ? 0 : now_ns();
                fde_xts_mul_alpha(tweak);
                if (profile != NULL) {
                    profile_add(&profile->evolution_ns, start);
                }
            }
        }
        return 0;
    }

    for (size_t j = 0; j < blocks; ++j) {
        uint8_t tweak[16];
        uint8_t masked[16];
        uint8_t transformed[16];
        memcpy(tweak, t0, 16);
        start = profile == NULL ? 0 : now_ns();
        for (uint32_t k = 0; k < index_at(indices, j); ++k) {
            fde_xts_mul_alpha(tweak);
        }
        if (profile != NULL) {
            profile_add(&profile->evolution_ns, start);
        }
        start = profile == NULL ? 0 : now_ns();
        xor_block(masked, input + 16 * j, tweak);
        if (fixed_block(encrypt ? worker->xts_data_enc : worker->xts_data_dec,
                        encrypt, masked, transformed) != 0) {
            return -1;
        }
        xor_block(output + 16 * j, transformed, tweak);
        if (profile != NULL) {
            profile_add(&profile->data_ns, start);
        }
    }
    return 0;
}

static int ratchet_aes_crypt(fde_worker *worker, fde_scheme scheme, int encrypt,
                             const uint8_t *input, const uint32_t *indices,
                             uint64_t sector, size_t blocks, uint8_t *output,
                             fde_profile *profile) {
    uint8_t state[16];
    uint64_t start = profile == NULL ? 0 : now_ns();
    if (seed_state(worker, sector, state) != 0) {
        return -1;
    }
    if (profile != NULL) {
        profile_add(&profile->seed_ns, start);
    }
    for (size_t j = 0; j < blocks; ++j) {
        const uint8_t *source = input + 16 * j;
        uint8_t *destination = output + 16 * j;
        start = profile == NULL ? 0 : now_ns();
        if (scheme == FDE_RATCHET_CTR_AES) {
            uint8_t counter[16];
            uint8_t stream[16];
            encode_u32_le(index_at(indices, j), counter);
            if (dynamic_block(worker->dynamic128_enc, 1, state, counter,
                              stream) != 0) {
                return -1;
            }
            xor_block(destination, source, stream);
        } else if (dynamic_block(encrypt ? worker->dynamic128_enc
                                         : worker->dynamic128_dec,
                                 encrypt, state, source, destination) != 0) {
            return -1;
        }
        if (profile != NULL) {
            profile_add(&profile->data_ns, start);
        }
        start = profile == NULL ? 0 : now_ns();
        if (fde_ratchet_aes_update(worker, state,
                                   encrypt ? destination : source) != 0) {
            return -1;
        }
        if (profile != NULL) {
            profile_add(&profile->evolution_ns, start);
        }
    }
    return 0;
}

static int ratchet_blake3_crypt(fde_worker *worker, fde_scheme scheme,
                                int encrypt, const uint8_t *input,
                                const uint32_t *indices, uint64_t sector,
                                size_t blocks, uint8_t *output,
                                fde_profile *profile) {
    uint8_t seed[16];
    uint8_t state[32] = {0};
    uint64_t start = profile == NULL ? 0 : now_ns();
    if (seed_state(worker, sector, seed) != 0) {
        return -1;
    }
    memcpy(state, seed, 16);
    if (profile != NULL) {
        profile_add(&profile->seed_ns, start);
    }
    for (size_t j = 0; j < blocks; ++j) {
        const uint8_t *source = input + 16 * j;
        uint8_t *destination = output + 16 * j;
        start = profile == NULL ? 0 : now_ns();
        if (scheme == FDE_RATCHET_CTR_BLAKE3) {
            uint8_t counter[16];
            uint8_t stream[16];
            encode_u32_le(index_at(indices, j), counter);
            if (dynamic_block(worker->dynamic256_enc, 1, state, counter,
                              stream) != 0) {
                return -1;
            }
            xor_block(destination, source, stream);
        } else if (dynamic_block(encrypt ? worker->dynamic256_enc
                                         : worker->dynamic256_dec,
                                 encrypt, state, source, destination) != 0) {
            return -1;
        }
        if (profile != NULL) {
            profile_add(&profile->data_ns, start);
        }
        start = profile == NULL ? 0 : now_ns();
        fde_ratchet_blake3_update(state, encrypt ? destination : source);
        if (profile != NULL) {
            profile_add(&profile->evolution_ns, start);
        }
    }
    return 0;
}

static int validate_arguments(fde_worker *worker, fde_scheme scheme,
                              const uint8_t *input, size_t blocks,
                              uint8_t *output) {
    return worker != NULL && scheme >= 0 && scheme < FDE_SCHEME_COUNT &&
                   input != NULL && output != NULL && blocks > 0
               ? 0
               : -1;
}

int fde_encrypt(fde_worker *worker, fde_scheme scheme,
                const uint8_t *plaintext, const uint32_t *indices,
                uint64_t sector, size_t blocks, uint8_t *ciphertext,
                fde_profile *profile) {
    if (validate_arguments(worker, scheme, plaintext, blocks, ciphertext) != 0) {
        return -1;
    }
    profile_reset(profile);
    switch (scheme) {
    case FDE_ECB:
        return ecb_crypt(worker, 1, plaintext, blocks, ciphertext, profile);
    case FDE_XTS:
        return xts_crypt(worker, 1, plaintext, indices, sector, blocks,
                         ciphertext, profile, 0);
    case FDE_RATCHET_CTR_AES:
    case FDE_RATCHET_CBC_AES:
        return ratchet_aes_crypt(worker, scheme, 1, plaintext, indices,
                                 sector, blocks, ciphertext, profile);
    case FDE_RATCHET_CTR_BLAKE3:
    case FDE_RATCHET_CBC_BLAKE3:
        return ratchet_blake3_crypt(worker, scheme, 1, plaintext, indices,
                                    sector, blocks, ciphertext, profile);
    default:
        return -1;
    }
}

int fde_decrypt(fde_worker *worker, fde_scheme scheme,
                const uint8_t *ciphertext, const uint32_t *indices,
                uint64_t sector, size_t blocks, uint8_t *plaintext,
                fde_profile *profile) {
    if (validate_arguments(worker, scheme, ciphertext, blocks, plaintext) != 0) {
        return -1;
    }
    profile_reset(profile);
    switch (scheme) {
    case FDE_ECB:
        return ecb_crypt(worker, 0, ciphertext, blocks, plaintext, profile);
    case FDE_XTS:
        return xts_crypt(worker, 0, ciphertext, indices, sector, blocks,
                         plaintext, profile, 0);
    case FDE_RATCHET_CTR_AES:
    case FDE_RATCHET_CBC_AES:
        return ratchet_aes_crypt(worker, scheme, 0, ciphertext, indices,
                                 sector, blocks, plaintext, profile);
    case FDE_RATCHET_CTR_BLAKE3:
    case FDE_RATCHET_CBC_BLAKE3:
        return ratchet_blake3_crypt(worker, scheme, 0, ciphertext, indices,
                                    sector, blocks, plaintext, profile);
    default:
        return -1;
    }
}

int fde_xts_encrypt_indexed(fde_worker *worker, const uint8_t *plaintext,
                            const uint32_t *indices, uint64_t sector,
                            size_t blocks, uint8_t *ciphertext,
                            fde_profile *profile) {
    if (validate_arguments(worker, FDE_XTS, plaintext, blocks, ciphertext) != 0) {
        return -1;
    }
    profile_reset(profile);
    return xts_crypt(worker, 1, plaintext, indices, sector, blocks, ciphertext,
                     profile, 1);
}

int fde_xts_decrypt_indexed(fde_worker *worker, const uint8_t *ciphertext,
                            const uint32_t *indices, uint64_t sector,
                            size_t blocks, uint8_t *plaintext,
                            fde_profile *profile) {
    if (validate_arguments(worker, FDE_XTS, ciphertext, blocks, plaintext) != 0) {
        return -1;
    }
    profile_reset(profile);
    return xts_crypt(worker, 0, ciphertext, indices, sector, blocks, plaintext,
                     profile, 1);
}

static int openssl_xts_crypt(fde_worker *worker, int encrypt,
                             const uint8_t *input, uint64_t sector,
                             size_t bytes, uint8_t *output) {
    EVP_CIPHER_CTX *ctx;
    uint8_t iv[16];
    int written = 0;
    int final_written = 0;
    int ok;
    if (worker == NULL || input == NULL || output == NULL || bytes < 16 ||
        bytes > (size_t)INT32_MAX) {
        return -1;
    }
    encode_u64_le(sector, iv);
    ctx = encrypt ? worker->openssl_xts_enc : worker->openssl_xts_dec;
    if (encrypt) {
        ok = EVP_EncryptInit_ex(ctx, EVP_aes_256_xts(), NULL,
                                worker->xts_combined_key, iv);
        if (ok == 1) {
            ok = EVP_CIPHER_CTX_set_padding(ctx, 0);
        }
        if (ok == 1) {
            ok = EVP_EncryptUpdate(ctx, output, &written, input, (int)bytes);
        }
        if (ok == 1) {
            ok = EVP_EncryptFinal_ex(ctx, output + written, &final_written);
        }
    } else {
        ok = EVP_DecryptInit_ex(ctx, EVP_aes_256_xts(), NULL,
                                worker->xts_combined_key, iv);
        if (ok == 1) {
            ok = EVP_CIPHER_CTX_set_padding(ctx, 0);
        }
        if (ok == 1) {
            ok = EVP_DecryptUpdate(ctx, output, &written, input, (int)bytes);
        }
        if (ok == 1) {
            ok = EVP_DecryptFinal_ex(ctx, output + written, &final_written);
        }
    }
    return ok == 1 && (size_t)(written + final_written) == bytes ? 0 : -1;
}

int fde_xts_openssl_encrypt(fde_worker *worker, const uint8_t *plaintext,
                            uint64_t sector, size_t bytes,
                            uint8_t *ciphertext) {
    return openssl_xts_crypt(worker, 1, plaintext, sector, bytes, ciphertext);
}

int fde_xts_openssl_decrypt(fde_worker *worker, const uint8_t *ciphertext,
                            uint64_t sector, size_t bytes,
                            uint8_t *plaintext) {
    return openssl_xts_crypt(worker, 0, ciphertext, sector, bytes, plaintext);
}

int fde_decrypt_target(fde_worker *worker, fde_scheme scheme,
                       const uint8_t *ciphertext, const uint32_t *indices,
                       uint64_t sector, size_t blocks, size_t target,
                       uint8_t plaintext[16]) {
    if (worker == NULL || ciphertext == NULL || plaintext == NULL ||
        target >= blocks || scheme < 0 || scheme >= FDE_SCHEME_COUNT) {
        return -1;
    }
    if (scheme == FDE_ECB) {
        return fixed_block(worker->ecb_dec, 0, ciphertext + 16 * target,
                           plaintext);
    }
    if (scheme == FDE_XTS) {
        uint8_t tweak[16];
        uint8_t masked[16];
        uint8_t transformed[16];
        if (xts_seed(worker, sector, tweak) != 0) {
            return -1;
        }
        for (uint32_t k = 0; k < index_at(indices, target); ++k) {
            fde_xts_mul_alpha(tweak);
        }
        xor_block(masked, ciphertext + 16 * target, tweak);
        if (fixed_block(worker->xts_data_dec, 0, masked, transformed) != 0) {
            return -1;
        }
        xor_block(plaintext, transformed, tweak);
        return 0;
    }
    if (scheme == FDE_RATCHET_CTR_AES || scheme == FDE_RATCHET_CBC_AES) {
        uint8_t state[16];
        if (seed_state(worker, sector, state) != 0) {
            return -1;
        }
        for (size_t j = 0; j <= target; ++j) {
            const uint8_t *block = ciphertext + 16 * j;
            if (j == target) {
                if (scheme == FDE_RATCHET_CTR_AES) {
                    uint8_t counter[16];
                    uint8_t stream[16];
                    encode_u32_le(index_at(indices, j), counter);
                    if (dynamic_block(worker->dynamic128_enc, 1, state,
                                      counter, stream) != 0) {
                        return -1;
                    }
                    xor_block(plaintext, block, stream);
                } else if (dynamic_block(worker->dynamic128_dec, 0, state,
                                         block, plaintext) != 0) {
                    return -1;
                }
            }
            if (j < target && fde_ratchet_aes_update(worker, state, block) != 0) {
                return -1;
            }
        }
        return 0;
    }
    {
        uint8_t seed[16];
        uint8_t state[32] = {0};
        if (seed_state(worker, sector, seed) != 0) {
            return -1;
        }
        memcpy(state, seed, 16);
        for (size_t j = 0; j <= target; ++j) {
            const uint8_t *block = ciphertext + 16 * j;
            if (j == target) {
                if (scheme == FDE_RATCHET_CTR_BLAKE3) {
                    uint8_t counter[16];
                    uint8_t stream[16];
                    encode_u32_le(index_at(indices, j), counter);
                    if (dynamic_block(worker->dynamic256_enc, 1, state,
                                      counter, stream) != 0) {
                        return -1;
                    }
                    xor_block(plaintext, block, stream);
                } else if (dynamic_block(worker->dynamic256_dec, 0, state,
                                         block, plaintext) != 0) {
                    return -1;
                }
            }
            if (j < target) {
                fde_ratchet_blake3_update(state, block);
            }
        }
    }
    return 0;
}
