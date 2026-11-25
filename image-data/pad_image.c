#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "files.h"
#include "image_io.h"

static uint32_t ceil_power_of_two(uint32_t size)
{
    uint32_t power = 4;
    while (power < size)
        power *= 2;
    return power;
}

int main(int argc, char **argv)
{
    uint32_t target = 0;
    int fit_long = 0, transparent = 0, arg;
    for (arg = 1; arg < argc; ++arg) {
        if (strcmp(argv[arg], "--transparent") == 0) {
            transparent = 1;
        } else if (strcmp(argv[arg], "--fit") == 0 && arg + 1 < argc) {
            const char *value = argv[++arg];
            if (strcmp(value, "short") == 0)
                fit_long = 0;
            else if (strcmp(value, "long") == 0)
                fit_long = 1;
            else {
                fprintf(stderr, "--fit requires short or long\n");
                return EXIT_FAILURE;
            }
        } else if (strcmp(argv[arg], "-s") == 0 && arg + 1 < argc) {
            const char *value = argv[++arg];
            char *end;
            errno = 0;
            uintmax_t n = strtoumax(value, &end, 10);
            if (value[0] < '1' || value[0] > '9' || *end || errno ||
                n < 4 || n > UINT32_MAX || (n & (n - 1))) {
                fprintf(stderr, "-s requires a power of two of at least 4\n");
                return EXIT_FAILURE;
            }
            target = (uint32_t)n;
        } else {
            break;
        }
    }
    if (argc - arg != 2) {
        fprintf(stderr, "Usage: %s [--fit short|long] [-s N] [--transparent] in.png out.png\n", argv[0]);
        return EXIT_FAILURE;
    }
    const char *input = argv[arg], *output = argv[arg + 1];
    if (same_file(input, output)) {
        fprintf(stderr, "Input and output must be different files\n");
        return EXIT_FAILURE;
    }

    int width, height;
    unsigned char *pixels = load_image(input, &width, &height, 0);
    if (!pixels)
        return EXIT_FAILURE;
    if (!transparent) {
        size_t count = (size_t)width * (size_t)height;
        for (size_t i = 0; i < count; ++i) {
            unsigned char *p = pixels + 4 * i;
            unsigned a = p[3];
            p[0] = 255 - ((255 - p[0]) * a + 127) / 255;
            p[1] = 255 - ((255 - p[1]) * a + 127) / 255;
            p[2] = 255 - ((255 - p[2]) * a + 127) / 255;
            p[3] = 255;
        }
    }

    int horizontal = width >= height;
    uint32_t short_edge = (uint32_t)(horizontal ? height : width);
    uint32_t long_edge = (uint32_t)(horizontal ? width : height);
    if (!target) {
        uint32_t size = fit_long ? long_edge : short_edge;
        target = ceil_power_of_two(size);
        uint32_t lower = target / 2;
        if (lower >= 4 && size - lower < target - size)
            target = lower;
    }
    uint64_t scaled_short = target, scaled_long = target, padded_short, padded_long;
    if (fit_long) {
        scaled_short = ((uint64_t)short_edge * target + long_edge / 2) / long_edge;
        if (!scaled_short)
            scaled_short = 1;
        padded_short = ceil_power_of_two((uint32_t)scaled_short);
        padded_long = target;
    } else {
        scaled_long = ((uint64_t)long_edge * target + short_edge / 2) / short_edge;
        padded_short = target;
        padded_long = (scaled_long + target - 1) / target * target;
    }
    uint64_t canvas_width = horizontal ? padded_long : padded_short;
    uint64_t canvas_height = horizontal ? padded_short : padded_long;
    int status = EXIT_FAILURE;
    unsigned char *canvas = NULL;
    if (!image_fits(canvas_width, canvas_height)) {
        fprintf(stderr, "Resized canvas is too large; try a smaller -s\n");
        goto cleanup;
    }
    int scaled_width = (int)(horizontal ? scaled_long : scaled_short);
    int scaled_height = (int)(horizontal ? scaled_short : scaled_long);
    if (scaled_width != width || scaled_height != height) {
        unsigned char *resized = resize_image(pixels, width, height, scaled_width, scaled_height);
        if (!resized)
            goto cleanup;
        free(pixels);
        pixels = resized;
    }

    if (canvas_width != (uint64_t)scaled_width || canvas_height != (uint64_t)scaled_height) {
        size_t x = ((size_t)canvas_width - (size_t)scaled_width) / 2;
        size_t y = ((size_t)canvas_height - (size_t)scaled_height) / 2;
        size_t bytes = 4 * (size_t)canvas_width * (size_t)canvas_height;
        canvas = malloc(bytes);
        if (!canvas) {
            perror("malloc");
            goto cleanup;
        }
        memset(canvas, transparent ? 0 : 255, bytes);
        size_t stride = 4 * (size_t)scaled_width;
        for (size_t row = 0; row < (size_t)scaled_height; ++row)
            memcpy(canvas + 4 * ((y + row) * (size_t)canvas_width + x), pixels + row * stride, stride);
    }
    if (write_png(output, canvas ? canvas : pixels, (int)canvas_width, (int)canvas_height))
        status = EXIT_SUCCESS;

cleanup:
    free(canvas);
    free(pixels);
    return status;
}
