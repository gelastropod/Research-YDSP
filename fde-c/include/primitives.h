#ifndef PRIMITIVES_H
#define PRIMITIVES_H

#include <stddef.h>

#include "common.h"

void xor_bytes(const byte* a, const byte* b, byte* out, size_t length);
void aes_block_encrypt(const byte* key, const byte* block, byte* out, size_t key_length);
void aes_block_decrypt(const byte* key, const byte* block, byte* out, size_t key_length);

#endif