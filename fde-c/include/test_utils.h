#ifndef TEST_UTILS_H
#define TEST_UTILS_H

#include "common.h"

void hex_to_bytes(const char* hex, byte* out, size_t out_len);
void bytes_to_hex(const byte* bytes, char* out, size_t out_len);

#endif