#ifndef KDF_H
#define KDF_H

#include "common.h"

void expand_master_key(const byte* master_key, byte* key_0, byte* key_F, byte* key_G);

#endif