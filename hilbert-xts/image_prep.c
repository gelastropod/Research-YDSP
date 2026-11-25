#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "image_prep.h"

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize2.h"

int image_arguments(int argc, char **argv, const char *output_name, uint32_t *target, Fit *fit,
                    PixelFormat *format, const char **input, const char **output)
{
    *target = 0;
    *fit = FIT_SHORT;
    if (format)
        *format = FORMAT_RGBA;
    int arg;
    for (arg = 1; arg + 1 < argc; arg += 2) {
        const char *value = argv[arg + 1];
        if (strcmp(argv[arg], "-s") == 0) {
            char *end;
            errno = 0;
            uintmax_t size = strtoumax(value, &end, 10);
            if (value[0] < '1' || value[0] > '9' || *end || errno ||
                size > UINT32_MAX || (size & (size - 1))) {
                fprintf(stderr, "-s requires a positive power of two\n");
                return 0;
            }
            *target = (uint32_t)size;
        } else if (strcmp(argv[arg], "--fit") == 0) {
            if (strcmp(value, "short") == 0)
                *fit = FIT_SHORT;
            else if (strcmp(value, "long") == 0)
                *fit = FIT_LONG;
            else {
                fprintf(stderr, "--fit requires short or long\n");
                return 0;
            }
        } else if (format && strcmp(argv[arg], "-q") == 0) {
            if (strcmp(value, "rgba") == 0)
                *format = FORMAT_RGBA;
            else if (strcmp(value, "bc3") == 0)
                *format = FORMAT_BC3;
            else if (strcmp(value, "ycc") == 0)
                *format = FORMAT_YCC;
            else {
                fprintf(stderr, "-q requires rgba, bc3, or ycc\n");
                return 0;
            }
        } else {
            break;
        }
    }
    if (argc - arg != 2) {
        fprintf(stderr, "Usage: %s [--fit short|long] [-s size]%s input-image %s\n",
                argv[0], format ? " [-q rgba|bc3|ycc]" : "", output_name);
        return 0;
    }
    *input = argv[arg];
    *output = argv[arg + 1];
    return 1;
}

int prepare_image(const char *path, uint32_t target, Fit fit, PreparedImage *image)
{
    int width, height;
    unsigned char *pixels = stbi_load(path, &width, &height, NULL, 4);
    if (!pixels) {
        fprintf(stderr, "%s: %s\n", path, stbi_failure_reason());
        return 0;
    }

    if (!target) {
        int short_edge = width < height ? width : height;
        int long_edge = width > height ? width : height;
        target = nearest_power_of_two((uint32_t)(fit == FIT_LONG ? long_edge : short_edge));
    }
    Layout layout;
    if (!make_layout((uint32_t)width, (uint32_t)height, target, fit, &layout)) {
        fprintf(stderr, "Resized canvas is too large; try a smaller -s\n");
        stbi_image_free(pixels);
        return 0;
    }
    if ((uint32_t)width != layout.width || (uint32_t)height != layout.height) {
        unsigned char *scaled = stbir_resize_uint8_srgb(pixels, width, height, 0, NULL,
                                                       (int)layout.width, (int)layout.height, 0, STBIR_RGBA);
        stbi_image_free(pixels);
        if (!scaled) {
            fprintf(stderr, "Could not resize image\n");
            return 0;
        }
        pixels = scaled;
    }
    *image = (PreparedImage){width, height, layout, pixels};
    return 1;
}
