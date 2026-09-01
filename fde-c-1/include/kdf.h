#ifndef KDF_H
#define KDF_H

#include "common.h"

int expand_master_key(const byte* master_key, byte* key_0, byte* key_F, byte* key_G, uint32_t key_length);

#endif