#ifndef PRIMITIVES_H
#define PRIMITIVES_H

#include "common.h"

void xor_bytes(const byte* a, const byte* b, byte* out, uint32_t length);
void encode_lba(uint32_t lba, byte* out);

int aes_block_encrypt(const byte* key, const byte* block, byte* out, uint32_t key_length);
int aes_block_decrypt(const byte* key, const byte* block, byte* out, uint32_t key_length);

int aes_encrypt_volume(const byte* key, const byte* plaintext, byte* ciphertext, uint32_t key_length, uint32_t plaintext_length);
int aes_decrypt_volume(const byte* key, const byte* ciphertext, byte* plaintext, uint32_t key_length, uint32_t ciphertext_length);

int xts_encrypt_sector(uint32_t lba, const byte* key, const byte* plaintext, byte* ciphertext, uint32_t key_length, uint32_t plaintext_length);
int xts_decrypt_sector(uint32_t lba, const byte* key, const byte* ciphertext, byte* plaintext, uint32_t key_length, uint32_t ciphertext_length);

int xts_encrypt_volume(const byte* key, const byte* plaintext, byte* ciphertext, uint32_t key_length, uint32_t sector_size, uint32_t plaintext_length);
int xts_decrypt_volume(const byte* key, const byte* ciphertext, byte* plaintext, uint32_t key_length, uint32_t sector_size, uint32_t ciphertext_length);

#endif
