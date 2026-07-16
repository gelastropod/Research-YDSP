#include "test_utils.h"

#include <stdio.h>

void hex_to_bytes(const char* hex, unsigned char* out, size_t out_len) {
	for (size_t i = 0; i < out_len; i++) {
		sscanf(hex + 2 * i, "%2hhx", &out[i]);
	}
}

void bytes_to_hex(const unsigned char* bytes, char* out, size_t out_len) {
	for (size_t i = 0; i < out_len; i++) {
		sprintf(out + 2 * i, "%02x", bytes[i]);
	}
}