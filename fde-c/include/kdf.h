#ifndef KDF_H
#define KDF_H

#include "common.h"

int expand_master_key(const byte* master_key, byte* key_0, byte* key_F, byte* key_G, size_t key_length);

#endif