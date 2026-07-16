#ifndef TEST_UTILS_H
#define TEST_UTILS_H

#include <stddef.h>

void hex_to_bytes(const char* hex, unsigned char* out, size_t out_len);
void bytes_to_hex(const unsigned char* bytes, char* out, size_t out_len);

#endif