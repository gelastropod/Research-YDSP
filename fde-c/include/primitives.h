#ifndef PRIMITIVES_H
#define PRIMITIVES_H

#include <stddef.h>

void xor_bytes(const unsigned char* a, const unsigned char* b, unsigned char* out, size_t length);
void aes_block_encrypt(const unsigned char* key, const unsigned char* block, unsigned char* out, size_t key_length);
void aes_block_decrypt(const unsigned char* key, const unsigned char* block, unsigned char* out, size_t key_length);

#endif