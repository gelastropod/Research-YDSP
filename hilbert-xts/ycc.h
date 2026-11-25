#ifndef YCC_H
#define YCC_H

#include "stream_format.h"

typedef struct {
    int32_t r, g, b, count;
} RgbSum;

static inline unsigned char clamp_byte(int32_t value)
{
    return value < 0 ? 0 : value > 255 ? 255 : (unsigned char)value;
}

static inline unsigned char ycc_sample(RgbSum sum, int32_t r, int32_t g, int32_t b, int32_t bias)
{
    if (!sum.count)
        return (unsigned char)bias;
    int32_t scale = sum.count * 65536;
    return clamp_byte((r * sum.r + g * sum.g + b * sum.b + bias * scale + scale / 2) / scale);
}

static inline void encode_ycc(unsigned char block[BLOCK_BYTES],
                              const unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4], unsigned valid)
{
    for (unsigned half = 0; half < 2; ++half) {
        unsigned char *samples = block + 8 * half;
        RgbSum chroma[2] = {0};
        for (unsigned y = 0; y < BLOCK_EDGE; ++y) {
            RgbSum luma = {0};
            for (unsigned x = 0; x < 2; ++x) {
                unsigned i = y * BLOCK_EDGE + 2 * half + x;
                if (valid & (1u << i)) {
                    luma.r += rgba[4 * i];
                    luma.g += rgba[4 * i + 1];
                    luma.b += rgba[4 * i + 2];
                    ++luma.count;
                }
            }
            samples[y] = ycc_sample(luma, 19595, 38470, 7471, 0);
            RgbSum *sum = &chroma[y / 2];
            sum->r += luma.r;
            sum->g += luma.g;
            sum->b += luma.b;
            sum->count += luma.count;
        }
        for (unsigned y = 0; y < 2; ++y) {
            samples[4 + y] = ycc_sample(chroma[y], -11059, -21709, 32768, 128);
            samples[6 + y] = ycc_sample(chroma[y], 32768, -27439, -5329, 128);
        }
    }
}

static inline void decode_ycc(const unsigned char block[BLOCK_BYTES],
                              unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4])
{
    for (unsigned y = 0; y < BLOCK_EDGE; ++y) {
        for (unsigned x = 0; x < BLOCK_EDGE; ++x) {
            const unsigned char *samples = block + 8 * (x / 2);
            int32_t luma = samples[y] * INT32_C(65536) + 32768;
            int32_t cb = (int32_t)samples[4 + y / 2] - 128;
            int32_t cr = (int32_t)samples[6 + y / 2] - 128;
            unsigned char *pixel = rgba + 4 * (y * BLOCK_EDGE + x);
            pixel[0] = clamp_byte((luma + 91881 * cr) / 65536);
            pixel[1] = clamp_byte((luma - 22554 * cb - 46802 * cr) / 65536);
            pixel[2] = clamp_byte((luma + 116130 * cb) / 65536);
            pixel[3] = 255;
        }
    }
}

#endif
