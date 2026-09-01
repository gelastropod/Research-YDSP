#ifndef PRIMITIVES_H
#define PRIMITIVES_H

#include "common.h"

void xor_bytes(const byte* a, const byte* b, byte* out, uint32_t length);
int aes_block_encrypt(const byte* key, const byte* block, byte* out, uint32_t key_length);
int aes_block_decrypt(const byte* key, const byte* block, byte* out, uint32_t key_length);

#endif