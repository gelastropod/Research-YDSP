#ifndef IMAGE_IO_H
#define IMAGE_IO_H

#include <limits.h>
#include <stdint.h>

static inline int image_fits(uint64_t width, uint64_t height)
{
    return width && height && width <= (1u << 24) && height <= (1u << 24) &&
           width <= (INT_MAX / 2 - 1) / 4 &&
           height <= (uint64_t)(INT_MAX / 2) / (4 * width + 1);
}

unsigned char *load_image(const char *path, int *width, int *height, int require_png);
unsigned char *resize_image(const unsigned char *pixels, int width, int height, int new_width, int new_height);
int write_png(const char *path, const unsigned char *pixels, int width, int height);

#endif
