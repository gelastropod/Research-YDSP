#ifndef BC3_H
#define BC3_H

#include "stream_format.h"

static inline void unpack_rgb565(const unsigned char *src, unsigned char rgb[3])
{
    unsigned code = src[0] | ((unsigned)src[1] << 8);
    unsigned r = code >> 11, g = (code >> 5) & 63, b = code & 31;
    rgb[0] = (unsigned char)((r << 3) | (r >> 2));
    rgb[1] = (unsigned char)((g << 2) | (g >> 4));
    rgb[2] = (unsigned char)((b << 3) | (b >> 2));
}

static inline void decode_bc3(const unsigned char block[BLOCK_BYTES], unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4])
{
    unsigned a = block[0], b = block[1];
    unsigned char alpha[8] = {(unsigned char)a, (unsigned char)b};
    if (a > b) {
        for (unsigned i = 1; i <= 6; ++i)
            alpha[i + 1] = (unsigned char)(((7 - i) * a + i * b) / 7);
    } else {
        for (unsigned i = 1; i <= 4; ++i)
            alpha[i + 1] = (unsigned char)(((5 - i) * a + i * b) / 5);
        alpha[6] = 0;
        alpha[7] = 255;
    }
    uint64_t alpha_bits = 0;
    for (unsigned i = 0; i < 6; ++i)
        alpha_bits |= (uint64_t)block[2 + i] << (8 * i);

    unsigned char colors[4][3];
    unpack_rgb565(block + 8, colors[0]);
    unpack_rgb565(block + 10, colors[1]);
    for (unsigned c = 0; c < 3; ++c) {
        colors[2][c] = (unsigned char)((2 * colors[0][c] + colors[1][c]) / 3);
        colors[3][c] = (unsigned char)((colors[0][c] + 2 * colors[1][c]) / 3);
    }
    for (unsigned i = 0; i < BLOCK_EDGE * BLOCK_EDGE; ++i) {
        unsigned color = (block[12 + i / 4] >> (2 * (i % 4))) & 3;
        for (unsigned c = 0; c < 3; ++c)
            rgba[4 * i + c] = colors[color][c];
        rgba[4 * i + 3] = alpha[(alpha_bits >> (3 * i)) & 7];
    }
}

#endif
