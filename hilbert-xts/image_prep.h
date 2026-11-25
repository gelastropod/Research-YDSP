#ifndef IMAGE_PREP_H
#define IMAGE_PREP_H

#include <stddef.h>

#include "stream_format.h"

typedef struct {
    int width, height;
    Layout layout;
    unsigned char *pixels;
} PreparedImage;

int image_arguments(int argc, char **argv, const char *output_name, uint32_t *target, Fit *fit,
                    PixelFormat *format, const char **input, const char **output);
int prepare_image(const char *path, uint32_t target, Fit fit, PreparedImage *image);

static inline const unsigned char *prepared_pixel(const PreparedImage *image, uint32_t x, uint32_t y)
{
    static const unsigned char padding[4] = {0, 0, 0, 0};
    const Layout *layout = &image->layout;
    if (layout_contains(layout, x, y))
        return image->pixels + 4 * ((size_t)(y - layout->offset_y) * layout->width + (x - layout->offset_x));
    return padding;
}

#endif
