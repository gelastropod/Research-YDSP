#ifndef XEX_H
#define XEX_H

#include "common.h"
#include "primitives.h"

int xex_encrypt_block(const byte* key, const byte* tweak, const byte* block, byte* out, size_t length);
int xex_decrypt_block(const byte* key, const byte* tweak, const byte* block, byte* out, size_t length);
int update_state(const byte* key, const byte* tweak, const byte* block, const byte* key_F, const byte* key_G, byte* next_key, byte* next_tweak, size_t length);

#endif