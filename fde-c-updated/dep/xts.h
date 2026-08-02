#ifndef XTS_H
#define XTS_H

#include "ratchet.h"

int xts_encrypt_sector_old(uint32_t lba, const byte* plaintext, uint32_t plaintext_length, byte* ciphertext, const struct ChainState* state_in, struct ChainState* state_out);
int xts_decrypt_sector_old(uint32_t lba, const byte* ciphertext, uint32_t ciphertext_length, byte* plaintext, const struct ChainState* state_in, struct ChainState* state_out);

int xts_encrypt_volume_old(const byte* plaintext, uint32_t plaintext_length, byte* ciphertext);
int xts_decrypt_volume_old(const byte* ciphertext, uint32_t ciphertext_length, byte* plaintext);

#endif
